# MuleTrace — Autonomous Agentic AML & Cross-Channel Fraud Intelligence System

> **Hackathon Problem Statement 1:** AI-Powered Suspicious Activity Detection

MuleTrace is an intelligent, **query-driven autonomous agent** that detects money laundering patterns across multi-channel banking transaction data. It combines dynamic NLP intent parsing, selective tool orchestration, PyTorch Geometric Graph Neural Networks, and Gradient×Input XAI attribution — all wrapped in an analyst-facing workbench UI.

---

## 🏗️ Architecture

```
Natural Language Analyst Query
        │
        ▼
┌───────────────────────────────────┐
│   Agent Planner (NLP Intent)      │  ← Extracts intent, filters, entities
│   backend/agent/planner.py        │
└──────────────┬────────────────────┘
               │  Dynamic Execution Plan (only needed tools)
               ▼
┌───────────────────────────────────────────────────────┐
│   Agentic Tool Registry (backend/agent/tools.py)      │
│  ┌────────────┐ ┌─────────────┐ ┌──────────────────┐ │
│  │  EDA Tool  │ │Feature Eng. │ │ Anomaly Detector │ │
│  └────────────┘ └─────────────┘ └──────────────────┘ │
│  ┌──────────────────┐ ┌──────────────────────────┐   │
│  │ Risk Classifier  │ │ XAI Explanation + SAR     │   │
│  └──────────────────┘ └──────────────────────────┘   │
└──────────────────────────┬────────────────────────────┘
                           │
                           ▼
        Structured Result: Intent · Tools Used · Risk Flags
        XAI Reasons · Escalation Action (Monitor/Review/SAR)
```

---

## 🤖 What Makes This Agentic (Hackathon Requirement)

The agent does **NOT** follow a fixed sequential pipeline. For each user query, it:

1. **Parses natural language** → extracts intent, filters, amount thresholds, entity IDs
2. **Constructs a dynamic execution plan** → decides which tools to call, in what order
3. **Invokes ONLY necessary tools** — for example:
   - `"Find structuring patterns in last 30 days"` → Skips EDA & GNN; runs Filter + Structuring Detector + XAI only
   - `"Which customers made 10+ transactions under $10,000?"` → Runs Aggregation Rule directly; skips ML
   - `"Is customer ACC-00001 suspicious?"` → Single entity lookup + on-demand XAI; no full scan

---

## 🧪 Detected AML Patterns

| Pattern | Description | Detection Method |
|---|---|---|
| **Structuring / Smurfing** | Sub-$10,000 deposits to evade regulatory reporting line | Rule-based filter + IQR anomaly |
| **Rapid Cash-Out Velocity** | UPI incoming → instant ATM withdrawal within minutes | Graph edge temporal analysis |
| **Shared Device Mule Rings** | Multiple accounts using same device IDs or IP subnets | Graph topology clustering |
| **High-Frequency Sub-Threshold** | ≥10 transactions per customer under $10,000 | Aggregation threshold rule |
| **Cross-Channel Layering** | GNN-detected high-risk clusters across UPI/ATM/Web/Mobile | GraphSAGE + GAT inference |

---

## 📂 Dataset Documentation

### Synthetic Dataset Schema

> **Why Synthetic?** Following hackathon rules permitting synthetic data when schema, assumptions, and generation logic are clearly documented. No real customer PII is used.

**Source Inspiration:**
- [Kaggle — IEEE-CIS Fraud Detection Dataset](https://www.kaggle.com/c/ieee-fraud-detection)
- [PaySim Mobile Financial Crime Benchmark](https://www.kaggle.com/datasets/ealaxi/paysim1)
- [IBM Transactions for Anti Money Laundering (AML)](https://www.kaggle.com/datasets/ealtman2019/ibm-transactions-for-anti-money-laundering-aml)
- [FATF AML Guidance — FATF-GAFI.org](https://www.fatf-gafi.org)
- [FinCEN Structuring Rules — fincen.gov](https://www.fincen.gov)

### Accounts Table (`accounts.csv`)

| Field | Type | Description |
|---|---|---|
| `account_id` | string | Unique account identifier (`ACC-XXXXX`) |
| `holder_name` | string | Synthetic customer name |
| `jurisdiction` | string | 2-letter country code (IN, US, UK, NG, RU, CN, AE, PH) |
| `jurisdiction_risk_weight` | float | FATF risk score for jurisdiction (0.1–0.6) |
| `account_type` | enum | SAVINGS / CURRENT / WALLET |
| `is_mule` | bool | Ground truth mule label (injected at generation) |

### Transactions Table (`transactions.csv`)

| Field | Type | Description |
|---|---|---|
| `transaction_id` | string | Unique transaction ID (`TX-XXXXXX`) |
| `source_account` | string | Sending account ID |
| `target_account` | string | Receiving account / `ATM-CASH-OUT` |
| `amount` | float | Transaction amount (USD) |
| `channel_type` | enum | UPI / ATM / WEB / MOBILE_APP |
| `timestamp` | ISO-8601 | Transaction datetime |
| `is_suspicious` | bool | Synthetic ground truth flag |
| `pattern_type` | string | NORMAL / STRUCTURING / RAPID_CASHOUT_DEPOSIT / RAPID_CASHOUT_ATM |

### Synthetic Injection Assumptions

- **Structuring**: 5 source accounts each make 4 transfers between $9,400–$9,950 to a single aggregation target.
- **Rapid Cash-Out**: Mule ring hub accounts receive large incoming MOBILE_APP deposits (₹15K–₹45K) and immediately withdraw 95% at ATM within 2–8 minutes.
- **Mule Rings**: 4 rings of 4–8 accounts each. Rings 0–2 are true mule rings; rings 3+ are false positives (shared expenses, corporate payroll).
- **Shared Devices/IPs**: Each mule ring shares a pool of 1–3 device IDs and IP addresses across ring members.

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| Backend / Agent API | FastAPI (Python 3.10+) |
| Agent NLP Planner | Custom rule-based intent parser (regex + keyword classification) |
| Graph Intelligence | NetworkX (Unified Entity Graph) |
| Neural Network | PyTorch Geometric — GraphSAGE + GAT hybrid |
| XAI | Gradient × Input feature attribution |
| SAR Reporting | Custom FIU-IND compliant structured report generator |
| Frontend | React 19 + Vite + Vanilla CSS (glassmorphism dark mode) |
| Graph Visualization | react-force-graph-2d |

### External Tools & AI Assistance Disclosure
- Architecture designed with assistance from Google Gemini / Anthropic Claude AI pair programming.
- All code is original, written during the hackathon window, and fully understood by the team.
- No proprietary APIs or paid services are used.

---

## 🚀 Local Setup & Run

### Prerequisites

| Tool | Version |
|---|---|
| Python | 3.10+ |
| Node.js | 18+ |
| pip | Latest |

### 1. Clone the repository

```bash
git clone https://github.com/ac265640/mule-trace.git
cd mule-trace
```

### 2. Install backend dependencies

```bash
pip install -r backend/requirements.txt
```

> ⚠️ If PyTorch Geometric fails, install PyTorch first:
> ```bash
> pip install torch --index-url https://download.pytorch.org/whl/cpu
> pip install torch-geometric
> pip install -r backend/requirements.txt
> ```

### 3. Start the backend

```bash
uvicorn backend.main:app --reload --port 8000
```

| URL | Description |
|---|---|
| `http://localhost:8000` | API root |
| `http://localhost:8000/docs` | Swagger / OpenAPI |
| `http://localhost:8000/api/agent/query` | Agent query endpoint (POST) |
| `http://localhost:8000/api/agent/preset-queries` | Benchmark queries |

### 4. Install & start the frontend

```bash
cd frontend
npm install
npm run dev
```

✅ Dashboard live at **`http://localhost:5173`**

### 5. Testing the Agent

Use the **Agent Workbench** tab or hit the API directly:

```bash
curl -X POST http://localhost:8000/api/agent/query \
  -H "Content-Type: application/json" \
  -d '{"query": "Find structuring patterns in the last 30 days"}'
```

```bash
curl -X POST http://localhost:8000/api/agent/query \
  -H "Content-Type: application/json" \
  -d '{"query": "Which customers made 10+ transactions under $10,000?"}'
```

```bash
curl -X POST http://localhost:8000/api/agent/query \
  -H "Content-Type: application/json" \
  -d '{"query": "Is customer ACC-00001 suspicious?"}'
```

---

## 📊 Agent Output Format

Every agent response includes:

```json
{
  "query": "Find structuring patterns in the last 30 days",
  "intent": "STRUCTURING_DETECTION",
  "target_entity": null,
  "filters": { "max_amount": 10000.0, "min_amount": 8000.0 },
  "execution_plan": [
    { "step": 1, "tool": "Filter_Data_Tool", "reason": "Apply $10,000 regulatory reporting filter" },
    { "step": 2, "tool": "Feature_Engineering_Tool", "reason": "Calculate sub-threshold velocity features" },
    { "step": 3, "tool": "Anomaly_Detection_Tool", "reason": "Run IQR anomaly detection on sub-threshold transfers" },
    { "step": 4, "tool": "Explanation_Tool", "reason": "Generate XAI reasons for structuring flags" }
  ],
  "execution_logs": ["..."],
  "execution_time_ms": 12.4,
  "tool_results": {
    "structuring_transactions": [...],
    "summary": "Detected sub-threshold transfers attempting regulatory evasion."
  }
}
```

---

## 📜 Regulatory Compliance

- **Reporting Threshold**: $10,000 (aligned with FinCEN CTR / RBI threshold guidance)
- **FATF Jurisdiction Weights**: Based on FATF Grey List and Black List country risk tiers
- **SAR Format**: Structured to FIU-IND Suspicious Activity Report guidelines
- **Data Privacy**: No real PII — all customer names, IDs, and transaction details are synthetically generated

---

## ⚠️ Code of Conduct Compliance

- ✅ All work is original, created during the hackathon window
- ✅ No references to any specific financial institution in the codebase
- ✅ Commit history demonstrates incremental, transparent development
- ✅ AI assistance disclosed above in Tech Stack section
