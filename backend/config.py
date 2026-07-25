"""
MuleTrace — Configuration & Database Connection Settings

Dataset design decisions:
- NUM_ACCOUNTS: 1200 accounts
- NUM_MULE_RINGS: 25 rings (18 fraud + 7 false positive)
  → At ring size 5-8, this yields ~125-200 mule accounts (~10-15% prevalence)
  → Higher prevalence = more training signal = better AP on balanced test set
- GNN_EPOCHS: 200 with early stopping (patience=25)
"""
import os

# ─── Neo4j Configuration ────────────────────────────────────────────
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "chainvigil")

# ─── Data Generation Defaults ───────────────────────────────────────
NUM_ACCOUNTS = int(os.getenv("NUM_ACCOUNTS", "1200"))
NUM_TRANSACTIONS = int(os.getenv("NUM_TRANSACTIONS", "6000"))
# 25 rings: 18 fraud typologies + 7 false positives
# Ring size 5-8 → ~125-200 true mule accounts (~10-15% of 1200 base accounts)
# Higher mule prevalence = more positive training examples = better AP
NUM_MULE_RINGS = int(os.getenv("NUM_MULE_RINGS", "25"))
MULE_RING_SIZE_RANGE = (5, 8)   # Larger rings for more training signal

# ─── Channels ───────────────────────────────────────────────────────
CHANNELS = ["UPI", "ATM", "WEB", "MOBILE_APP"]

# ─── GNN Configuration ─────────────────────────────────────────────
GNN_HIDDEN_DIM = 64    # kept lean for fast training (<30s)
GNN_NUM_LAYERS = 3     # 3-hop aggregation for ring detection
GNN_LEARNING_RATE = 0.003
GNN_EPOCHS = 60        # fast: ~22s; early stopping at patience=25
GNN_DROPOUT = 0.2      # lower dropout improves precision
RISK_THRESHOLD = 0.50  # balanced threshold

# ─── Paths ──────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data", "sample_data")
MODEL_DIR = os.path.join(BASE_DIR, "gnn", "saved_models")

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(MODEL_DIR, exist_ok=True)
