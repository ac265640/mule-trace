"""
MuleTrace — Master Agent Orchestrator

Coordinates user query parsing, dynamic tool invocation, execution timing,
and structured result synthesis for compliance analysts.

Every answer passes through the guardrail pipeline:

    input guard ─► plan ─► pre-generation decline ─► tools
        ─► cited narrative ─► citation enforcement ─► output guard

Any gate can stop the pipeline, in which case the agent returns a refusal
(status="refused") explaining why, instead of an unverifiable answer.
"""

import time
from typing import Any, Dict, List, Optional, Tuple

from backend.agent.citation import CitationEnforcer, EvidenceRegistry
from backend.agent.guardrails import build_refusal, run_input_guards, run_output_guards, should_decline
from backend.agent.planner import AgentPlanner
from backend.agent.tools import AgentToolRegistry

STRUCTURING_MIN = 8000.0
CTR_THRESHOLD = 10000.0
CASHOUT_WINDOW_MIN = 60
CASHOUT_MIN_RATIO = 0.5
EVIDENCE_SAMPLE = 5


class AgentOrchestrator:
    def __init__(self, data: Dict[str, Any] = None, G = None, risk_scores: List[Dict] = None):
        self.data = data
        self.G = G
        self.risk_scores = risk_scores or []
        self.planner = AgentPlanner()
        self.tools = AgentToolRegistry(data, G, risk_scores)
        self.enforcer = CitationEnforcer()

    def process_query(self, user_query: str, strategy: str = None) -> Dict[str, Any]:
        """Process natural language query and return dynamic execution plan & results."""
        start_time = time.time()
        guardrails: Dict[str, Any] = {}

        # Gate 1: Input guard (safety before scope)
        refusal, input_checks = run_input_guards(user_query)
        guardrails["input"] = {"passed": refusal is None, "checks": input_checks}
        if refusal:
            return self._refused(user_query, start_time, refusal, guardrails, intent="DECLINED")

        # Step 1: Parse Query Intent & Filters with optional strategy override
        parsed_plan = self.planner.parse_query(user_query, strategy=strategy)
        intent = parsed_plan["detected_intent"]
        filters = parsed_plan["filters"]
        target_entity = parsed_plan["target_entity"]
        plan_steps = parsed_plan["plan_steps"]

        # Gate 2: Pre-generation decline (is there anything to ground an answer in?)
        refusal = should_decline(intent, target_entity, self.data, self.risk_scores, self.G)
        guardrails["pre_generation"] = {"passed": refusal is None}
        if refusal:
            return self._refused(user_query, start_time, refusal, guardrails, intent, target_entity, filters, plan_steps)

        # Step 2: Dynamically execute ONLY the required tools, registering evidence as we go
        registry = EvidenceRegistry()
        handler = {
            "STRUCTURING_DETECTION": self._structuring,
            "AGGREGATION_THRESHOLD": self._aggregation,
            "SINGLE_ENTITY_LOOKUP": self._single_entity,
            "BROAD_EDA_EXPLORATION": self._eda,
            "RAPID_CASHOUT_VELOCITY": self._rapid_cashout,
        }.get(intent, self._hybrid)
        execution_logs, tool_results, narrative, confidence, confidence_basis = handler(
            registry, filters, target_entity
        )

        # Gate 3: Citation enforcement
        enforcement = self.enforcer.enforce(narrative, confidence, registry)
        guardrails["citation_enforcement"] = enforcement.to_dict()
        execution_logs.append(
            f"Citation enforcement: {enforcement.valid_citation_count}/{enforcement.total_citation_count} citations valid, "
            f"{enforcement.claims_checked} numeric claims checked."
        )
        if not enforcement.is_valid:
            low_confidence = any(e.startswith("Confidence") for e in enforcement.errors)
            refusal = build_refusal(
                "LOW_CONFIDENCE" if low_confidence and len(enforcement.errors) == 1 else "CITATION_ENFORCEMENT_FAILED",
                (f"The evidence is too inconclusive to answer reliably ({confidence_basis})."
                 if low_confidence and len(enforcement.errors) == 1
                 else "I couldn't verify every claim in my answer against the evidence, so I'm withholding it."),
                enforcement.errors,
                suggestions=[],
            )
            if target_entity:
                refusal["next_step"] = f"Review {target_entity} manually in the XAI Auditor tab."
            return self._refused(
                user_query, start_time, refusal, guardrails, intent, target_entity, filters, plan_steps,
                execution_logs=execution_logs, evidence=registry.to_list(),
            )

        # Gate 4: Output guard (PII scrub + disclaimer)
        holder_names = self.data["accounts"]["holder_name"].dropna().tolist() if "holder_name" in self.data["accounts"] else []
        output = run_output_guards(narrative, holder_names)
        guardrails["output"] = {"redactions": output["redactions"], "disclaimer_added": True}

        confidence_label = f"{confidence_basis} ({confidence:.0%})"
        tool_results.update({
            "narrative_summary": output["text"],
            "confidence": confidence_label,
        })

        return {
            "query": user_query,
            "status": "answered",
            "intent": intent,
            "target_entity": target_entity,
            "filters": filters,
            "execution_plan": plan_steps,
            "execution_logs": execution_logs,
            "execution_time_ms": round((time.time() - start_time) * 1000, 2),
            "answer": {
                "text": output["text"],
                "confidence": round(confidence, 4),
                "confidence_label": confidence_label,
                "disclaimer": output["disclaimer"],
            },
            "evidence": registry.to_list(),
            "refusal": None,
            "guardrails": guardrails,
            "tool_results": tool_results,
        }

    # ── Refusal response ─────────────────────────────────────────────────────

    def _refused(self, query, start_time, refusal, guardrails, intent, target_entity=None, filters=None,
                 plan_steps=None, execution_logs=None, evidence=None) -> Dict[str, Any]:
        return {
            "query": query,
            "status": "refused",
            "intent": intent,
            "target_entity": target_entity,
            "filters": filters or {},
            "execution_plan": plan_steps or [],
            "execution_logs": (execution_logs or []) + [f"Refused: {refusal['category']}"],
            "execution_time_ms": round((time.time() - start_time) * 1000, 2),
            "answer": None,
            "evidence": evidence or [],
            "refusal": refusal,
            "guardrails": guardrails,
            "tool_results": {},
        }

    # ── Shared evidence ──────────────────────────────────────────────────────

    def _dataset_evidence(self, registry: EvidenceRegistry) -> str:
        tx = self.data["transactions"]
        return registry.add("aggregate", "transactions.csv", "Transactions scanned", {
            "transactions_scanned": len(tx),
            "accounts": len(self.data["accounts"]),
        })

    # ── Intent handlers: (logs, tool_results, narrative, confidence, basis) ──

    def _structuring(self, registry, filters, _target) -> Tuple[List[str], Dict, str, float, str]:
        lo = filters.get("min_amount", STRUCTURING_MIN)
        hi = filters.get("max_amount", CTR_THRESHOLD)
        logs = [
            f"Scanning transactions in the ${lo:,.0f}–${hi:,.0f} band below the reporting threshold...",
            "Aggregating sub-threshold transfers by source account...",
        ]
        txs = self.tools.run_structuring_tool(hi)
        n = len(txs)
        total = sum(t["amount"] for t in txs)
        sources = len({t["source_account"] for t in txs})

        e_rule = registry.add("rule", "AML rule set", "Structuring band", {
            "band_min_usd": lo, "band_max_usd": hi, "ctr_threshold_usd": CTR_THRESHOLD,
        })
        e_scan = self._dataset_evidence(registry)
        e_result = registry.add("aggregate", "Structuring_Tool", "Transactions in band", {
            "matching_transactions": n, "total_amount_usd": round(total, 2), "distinct_source_accounts": sources,
        })

        narrative = (
            f"I scanned {len(self.data['transactions']):,} transactions [{e_scan}] for amounts between "
            f"${lo:,.0f} and ${hi:,.0f}, just under the ${CTR_THRESHOLD:,.0f} reporting threshold [{e_rule}]. "
        )
        if n:
            top = max(txs, key=lambda t: t["amount"])
            e_top = [registry.add("transaction", "transactions.csv", t["transaction_id"], {
                "transaction_id": t["transaction_id"], "source_account": t["source_account"],
                "target_account": t["target_account"], "amount_usd": t["amount"], "channel": t["channel"],
            }) for t in sorted(txs, key=lambda t: -t["amount"])[:EVIDENCE_SAMPLE]][0]
            narrative += (
                f"{n:,} transactions fall in that band, totalling ${total:,.2f} from {sources:,} source accounts [{e_result}]. "
                f"The largest is {top['transaction_id']} for ${top['amount']:,.2f} from {top['source_account']} [{e_top}]."
            )
        else:
            narrative += f"No transactions fall in that band [{e_result}]."

        results = {
            "structuring_transactions": txs,
            "summary": f"{n} transactions in the structuring band.",
            "recommended_action": "Review the cited transactions and consider a SAR for CTR evasion." if n else None,
        }
        return logs, results, narrative, 1.0, "Deterministic rule"

    def _aggregation(self, registry, filters, _target):
        threshold = filters.get("threshold_amount", CTR_THRESHOLD)
        min_count = filters.get("min_count", 10)
        logs = [
            f"Applying aggregation rule (≥{min_count} transactions under ${threshold:,.0f} per account)...",
            "Bypassing full GNN inference (deterministic threshold rule applied directly)...",
        ]
        customers = sorted(self.tools.run_aggregation_rule_tool(threshold, min_count),
                           key=lambda c: -c["sub_10k_tx_count"])
        n = len(customers)

        e_rule = registry.add("rule", "AML rule set", "Frequency threshold rule", {
            "min_transactions": min_count, "amount_threshold_usd": threshold,
        })
        e_scan = self._dataset_evidence(registry)
        e_result = registry.add("aggregate", "Aggregation_Rule_Tool", "Accounts breaching rule", {"accounts_flagged": n})

        narrative = (
            f"I applied the rule of {min_count} or more transactions under ${threshold:,.0f} per sending account [{e_rule}] "
            f"across {len(self.data['transactions']):,} transactions [{e_scan}]. "
        )
        if n:
            e_top = [registry.add("account", "Aggregation_Rule_Tool", c["account_id"], {
                "account_id": c["account_id"], "sub_threshold_tx_count": c["sub_10k_tx_count"],
                "total_volume_usd": round(c["total_volume"], 2),
            }) for c in customers[:EVIDENCE_SAMPLE]][0]
            top = customers[0]
            narrative += (
                f"{n:,} accounts breach it [{e_result}]. The heaviest is {top['account_id']} with "
                f"{top['sub_10k_tx_count']} sub-threshold transactions totalling ${top['total_volume']:,.2f} [{e_top}]."
            )
        else:
            narrative += f"No accounts breach it [{e_result}]."

        results = {
            "flagged_customers": customers,
            "summary": f"{n} accounts breach the frequency rule.",
            "recommended_action": "Escalate the cited accounts to Level 2 compliance review." if n else None,
        }
        return logs, results, narrative, 1.0, "Deterministic rule"

    def _single_entity(self, registry, _filters, target):
        logs = [
            f"Retrieving model risk score and graph topology for {target}...",
        ]
        entity = self.tools.run_single_entity_lookup(target)
        p = entity["mule_probability"]
        e_score = registry.add("model_score", "GNN risk engine (GraphSAGE + GAT)", target, {
            "account_id": target, "mule_probability": round(p, 4),
            "risk_tier": entity["risk_tier"], "recommended_action": entity["recommended_action"],
        })
        narrative = (
            f"{target} has a GNN mule probability of {p:.1%}, which puts it in the {entity['risk_tier']} risk tier "
            f"with a recommended action of {entity['recommended_action']} [{e_score}]."
        )
        if entity.get("graph_degree") is not None:
            e_graph = registry.add("graph", "Unified entity graph", f"{target} neighbourhood", {
                "account_id": target, "connected_entities": entity["graph_degree"],
            })
            narrative += f" In the entity graph it connects to {entity['graph_degree']} devices, IPs and counterparties [{e_graph}]."

        # Certainty: how far the model is from a coin flip. p≈0.5 means the model can't tell.
        certainty = abs(p - 0.5) * 2
        results = {
            "single_entity": entity,
            "summary": f"{target}: {entity['risk_tier']} risk ({p:.1%}).",
            "recommended_action": entity["recommended_action"],
        }
        return logs, results, narrative, certainty, "Model certainty"

    def _eda(self, registry, _filters, _target):
        logs = ["Profiling transaction amounts, volumes, and channel distributions..."]
        eda = self.tools.run_eda_tool()
        e_totals = registry.add("aggregate", "EDA_Tool", "Dataset totals", {
            "total_customers": eda["total_customers"], "total_transactions": eda["total_transactions"],
            "total_volume_usd": round(eda["total_volume_usd"], 2),
            "average_transaction_usd": round(eda["average_transaction_amount"], 2),
        })
        e_channels = registry.add("aggregate", "EDA_Tool", "Channel breakdown", eda["channel_breakdown"])
        channels = ", ".join(f"{k} {v:,}" for k, v in sorted(eda["channel_breakdown"].items(), key=lambda kv: -kv[1]))
        narrative = (
            f"The dataset holds {eda['total_customers']:,} accounts and {eda['total_transactions']:,} transactions "
            f"worth ${eda['total_volume_usd']:,.2f} in total, averaging ${eda['average_transaction_amount']:,.2f} each [{e_totals}]. "
            f"By channel: {channels} [{e_channels}]."
        )
        if eda.get("mule_prevalence"):
            mp = eda["mule_prevalence"]
            e_mule = registry.add("aggregate", "accounts.csv", "Labelled mule accounts", mp)
            narrative += f" {mp['mule_accounts']:,} accounts ({mp['prevalence_pct']}%) carry the mule label [{e_mule}]."
        results = {
            "eda_metrics": eda,
            "summary": "Exploratory profile of the dataset.",
            "recommended_action": "Use the channel breakdown to calibrate risk thresholds.",
        }
        return logs, results, narrative, 1.0, "Descriptive statistics"

    def _rapid_cashout(self, registry, _filters, _target):
        logs = [f"Pairing inbound transfers with ATM withdrawals within {CASHOUT_WINDOW_MIN} minutes..."]
        pairs = self.tools.run_rapid_cashout_tool(CASHOUT_WINDOW_MIN, CASHOUT_MIN_RATIO)
        n, accounts = len(pairs), len({p["account_id"] for p in pairs})

        e_rule = registry.add("rule", "AML rule set", "Rapid cash-out rule", {
            "window_minutes": CASHOUT_WINDOW_MIN, "min_cashout_ratio": CASHOUT_MIN_RATIO,
        })
        e_scan = self._dataset_evidence(registry)
        e_result = registry.add("aggregate", "Rapid_Cashout_Tool", "Cash-out sequences", {
            "sequences": n, "accounts": accounts,
        })
        narrative = (
            f"I looked for accounts that withdrew at least {CASHOUT_MIN_RATIO:.0%} of an incoming transfer at an ATM "
            f"within {CASHOUT_WINDOW_MIN} minutes [{e_rule}], across {len(self.data['transactions']):,} transactions [{e_scan}]. "
        )
        if n:
            e_top = [registry.add("transaction", "transactions.csv", f"{p['inbound_transaction_id']} → {p['atm_transaction_id']}", p)
                     for p in pairs[:EVIDENCE_SAMPLE]][0]
            fastest = pairs[0]
            narrative += (
                f"I found {n:,} such sequences across {accounts:,} accounts [{e_result}]. The fastest: {fastest['account_id']} "
                f"received ${fastest['inbound_amount']:,.2f} and withdrew ${fastest['atm_amount']:,.2f} at an ATM "
                f"{fastest['minutes_to_cashout']} minutes later [{e_top}]."
            )
        else:
            narrative += f"No sequences match [{e_result}]."
        results = {
            "rapid_cashout_sequences": pairs,
            "summary": f"{n} rapid cash-out sequences.",
            "recommended_action": "Review the cited accounts for mule cash-out activity." if n else None,
        }
        return logs, results, narrative, 1.0, "Deterministic rule"

    def _hybrid(self, registry, _filters, _target):
        logs = ["Reading GNN (GraphSAGE + GAT) risk scores for all accounts..."]
        scores = sorted(self.risk_scores, key=lambda r: -r.get("mule_probability", 0))
        escalate = sum(1 for r in scores if r.get("recommended_action") in ("Escalate", "Freeze"))
        e_summary = registry.add("model_score", "GNN risk engine (GraphSAGE + GAT)", "Portfolio summary", {
            "accounts_scored": len(scores), "escalate_or_freeze": escalate,
        })
        top = scores[:3]
        top_ids = [registry.add("model_score", "GNN risk engine (GraphSAGE + GAT)", r["account_id"], {
            "account_id": r["account_id"], "mule_probability": round(r.get("mule_probability", 0), 4),
            "recommended_action": r.get("recommended_action"),
        }) for r in top]

        narrative = (
            f"The GNN risk engine scored {len(scores):,} accounts, and {escalate:,} of them are recommended "
            f"for Escalate or Freeze [{e_summary}]."
        )
        if top:
            ranked = ", ".join(f"{r['account_id']} ({r.get('mule_probability', 0):.1%}) [{eid}]" for r, eid in zip(top, top_ids))
            narrative += f" The highest-risk accounts are {ranked}."

        top10 = scores[:10]
        certainty = sum(abs(r.get("mule_probability", 0.5) - 0.5) * 2 for r in top10) / max(len(top10), 1)
        results = {
            "risk_scores": top10,
            "summary": f"{escalate} accounts recommended for escalation.",
            "recommended_action": "Examine the cited accounts in the Account Risk panel.",
        }
        return logs, results, narrative, certainty, "Model certainty (top 10)"
