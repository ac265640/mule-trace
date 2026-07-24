"""
MuleTrace — FastAPI Backend Server & Agentic AML API
"""

import os
import json
from pathlib import Path
from typing import Optional, Dict, Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles

from backend.config import DATA_DIR
from backend.data.generator import generate_all_data
from backend.graph.builder import GraphBuilder
from backend.gnn.dataset import nx_to_pyg
from backend.gnn.train import Trainer
from backend.gnn.predict import predict_scores
from backend.risk.engine import RiskIntelligenceEngine
from backend.risk.sanctions import SanctionsScreener
from backend.xai.explainer import MuleExplainer
from backend.xai.report import AuditReportGenerator
from backend.agent.orchestrator import AgentOrchestrator

app = FastAPI(
    title="MuleTrace API",
    description="Autonomous Agentic AML & Cross-Channel Fraud Intelligence System",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global Application State
state = {
    "data": None,
    "graph_builder": None,
    "G": None,
    "pyg_data": None,
    "node_mapping": None,
    "account_ids": None,
    "trainer": None,
    "risk_scores": [],
    "risk_summary": None,
    "orchestrator": None,
}

FRONTEND_DIST = Path(__file__).parent.parent / "frontend" / "dist"

if FRONTEND_DIST.exists():
    app.mount("/assets", StaticFiles(directory=str(FRONTEND_DIST / "assets")), name="assets")


@app.on_event("startup")
async def startup_event():
    """Initialize system on startup: generate data, build graph, train model."""
    print("🚀 Initializing MuleTrace System...")
    data = generate_all_data()
    state["data"] = data

    builder = GraphBuilder()
    G = builder.build(data)
    state["graph_builder"] = builder
    state["G"] = G

    pyg_data, node_mapping, account_ids = nx_to_pyg(G)
    state["pyg_data"] = pyg_data
    state["node_mapping"] = node_mapping
    state["account_ids"] = account_ids

    trainer = Trainer(pyg_data)
    trainer.train(epochs=20)
    state["trainer"] = trainer

    risk_scores = predict_scores(trainer.model, pyg_data, account_ids)
    state["risk_scores"] = risk_scores

    engine = RiskIntelligenceEngine(G, risk_scores)
    state["risk_summary"] = engine.analyze()

    state["orchestrator"] = AgentOrchestrator(data, G, risk_scores)
    print("✅ MuleTrace Agent ready!")


@app.get("/health")
async def health():
    return {"status": "healthy", "system": "MuleTrace Agent"}


@app.get("/api/status")
async def api_status():
    return {
        "name": "MuleTrace API",
        "graph_loaded": state["G"] is not None,
        "model_trained": state["trainer"] is not None,
        "total_accounts": len(state["risk_scores"]),
    }


# ─── Agentic Query Endpoint ───────────────────────────────────

@app.post("/api/agent/query")
async def agent_query(payload: Dict[str, Any]):
    """Execute dynamic agentic natural language query."""
    query = payload.get("query", "")
    if not query:
        raise HTTPException(status_code=400, detail="Query string is required.")

    if not state["orchestrator"]:
        state["orchestrator"] = AgentOrchestrator(state["data"], state["G"], state["risk_scores"])

    res = state["orchestrator"].process_query(query)
    return res


@app.get("/api/agent/preset-queries")
async def preset_queries():
    """Return benchmark queries for hackathon judges."""
    return {
        "queries": [
            "Find structuring patterns in the last 30 days",
            "Which customers made 10+ transactions under $10,000?",
            "Is customer ID ACC-00001 suspicious?",
            "Perform automated EDA on high-volume transactions",
            "Scan for rapid cash-out velocity anomalies"
        ]
    }


# ─── Data & Graph Endpoints ────────────────────────────────────

@app.get("/api/graph/stats")
async def graph_stats():
    if not state["graph_builder"]:
        raise HTTPException(status_code=400, detail="Graph not initialized.")
    return state["graph_builder"].get_stats()


@app.get("/api/accounts")
async def list_accounts():
    return {"accounts": state["risk_scores"][:50]}


@app.get("/api/report/sar")
async def get_sar_report():
    if not state["risk_summary"]:
        raise HTTPException(status_code=400, detail="Risk engine not run.")
    generator = AuditReportGenerator()
    return generator.generate_sar_report(state["risk_summary"])


@app.get("/{full_path:path}")
async def spa_fallback(full_path: str):
    index_file = FRONTEND_DIST / "index.html"
    if index_file.exists():
        return FileResponse(str(index_file))
    return {"status": "MuleTrace backend online"}
