"""
MuleTrace — Configuration Settings
"""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = Path(__file__).resolve().parent
DATA_DIR = BACKEND_DIR / "data" / "sample_data"
MODEL_DIR = BACKEND_DIR / "gnn" / "saved_models"

# Create directories if they do not exist
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(MODEL_DIR, exist_ok=True)

# Risk Thresholds
HIGH_RISK_THRESHOLD = 0.75
MEDIUM_RISK_THRESHOLD = 0.40

# Pattern Detection Thresholds
STRUCTURING_MAX_AMOUNT = 10000.0  # Regulatory reporting threshold
STRUCTURING_MIN_TX_COUNT = 3      # Minimum sub-threshold transfers
RAPID_CASHOUT_WINDOW_MINUTES = 30  # Window for velocity spike to ATM
