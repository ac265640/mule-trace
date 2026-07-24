"""
MuleTrace — Multi-Pattern Synthetic Data Generator

Generates realistic banking transactions with:
  1. Structuring / Smurfing ($9,000–$9,950 sub-threshold transfers)
  2. Rapid Cash-Out (UPI incoming -> instant ATM cash-out)
  3. Cross-Channel Mule Rings (shared devices & IPs across accounts)
  4. High-velocity & Layering patterns
"""

import os
import json
import random
import uuid
from datetime import datetime, timedelta
from typing import List, Dict, Tuple

import numpy as np
import pandas as pd

from backend.config import DATA_DIR, STRUCTURING_MAX_AMOUNT

random.seed(42)
np.random.seed(42)

JURISDICTIONS = {
    "IN": 0.2, "US": 0.15, "UK": 0.1, "NG": 0.6,
    "RU": 0.55, "CN": 0.4, "AE": 0.35, "PH": 0.5
}

CHANNELS = ["UPI", "ATM", "WEB", "MOBILE_APP"]


def _generate_device_id() -> str:
    return f"DEV-{uuid.uuid4().hex[:10].upper()}"


def _generate_ip() -> str:
    return f"{random.randint(1,254)}.{random.randint(1,254)}.{random.randint(1,254)}.{random.randint(1,254)}"


def generate_all_data(
    num_accounts: int = 500,
    num_transactions: int = 2500,
    num_mule_rings: int = 4
) -> Dict[str, pd.DataFrame]:
    """
    Generate synthetic banking dataset with accounts, transactions, device mappings,
    IP mappings, ATM withdrawals, and structuring/mule ring metadata.
    """
    # 1. Accounts
    accounts = []
    for i in range(num_accounts):
        jur = random.choice(list(JURISDICTIONS.keys()))
        accounts.append({
            "account_id": f"ACC-{i:05d}",
            "holder_name": f"Customer_{i:05d}",
            "jurisdiction": jur,
            "jurisdiction_risk_weight": JURISDICTIONS[jur],
            "account_type": random.choice(["SAVINGS", "CURRENT", "WALLET"]),
            "is_mule": False,
        })
    accounts_df = pd.DataFrame(accounts)

    # 2. Inject Mule Rings & Structuring Entities
    used_ids = set()
    rings = []
    for r_idx in range(num_mule_rings):
        ring_size = random.randint(4, 8)
        avail = [a for a in accounts_df["account_id"] if a not in used_ids]
        if len(avail) < ring_size:
            break
        members = random.sample(avail, ring_size)
        used_ids.update(members)

        shared_dev = [_generate_device_id() for _ in range(max(1, ring_size // 3))]
        shared_ips = [_generate_ip() for _ in range(max(1, ring_size // 3))]
        is_fraud = (r_idx < num_mule_rings // 2 + 1)

        ring_meta = {
            "ring_id": f"MULE_RING_{r_idx:02d}",
            "members": members,
            "hub_account": members[0],
            "shared_devices": shared_dev,
            "shared_ips": shared_ips,
            "is_fraud": is_fraud
        }
        rings.append(ring_meta)
        if is_fraud:
            accounts_df.loc[accounts_df["account_id"].isin(members), "is_mule"] = True

    # 3. Devices & IPs
    device_rows = []
    ip_rows = []
    all_devs = [_generate_device_id() for _ in range(num_accounts // 2)]
    all_ips = [_generate_ip() for _ in range(num_accounts // 2)]

    for _, row in accounts_df.iterrows():
        acc_id = row["account_id"]
        # check if in ring
        ring_match = [r for r in rings if acc_id in r["members"]]
        if ring_match:
            r = ring_match[0]
            dev = random.choice(r["shared_devices"])
            ip = random.choice(r["shared_ips"])
        else:
            dev = random.choice(all_devs)
            ip = random.choice(all_ips)

        device_rows.append({"account_id": acc_id, "device_id": dev})
        ip_rows.append({"account_id": acc_id, "ip_address": ip})

    devices_df = pd.DataFrame(device_rows)
    ips_df = pd.DataFrame(ip_rows)

    # 4. Transactions Generation
    tx_list = []
    base_time = datetime.now() - timedelta(days=60)

    account_ids = accounts_df["account_id"].tolist()

    # Normal Transactions
    for t_idx in range(num_transactions - 300):
        src, dst = random.sample(account_ids, 2)
        amount = round(random.uniform(50, 5000), 2)
        ch = random.choice(CHANNELS)
        ts = base_time + timedelta(minutes=random.randint(0, 60 * 24 * 60))
        tx_list.append({
            "transaction_id": f"TX-{t_idx:06d}",
            "source_account": src,
            "target_account": dst,
            "amount": amount,
            "channel_type": ch,
            "timestamp": ts.isoformat(),
            "is_suspicious": False,
            "pattern_type": "NORMAL",
        })

    # Structuring Transactions (Sub-$10k smurfing)
    structuring_sources = random.sample(account_ids, 5)
    structuring_target = random.choice(account_ids)
    t_cnt = num_transactions - 300

    for s_src in structuring_sources:
        for _ in range(4):  # 4 transfers under $10k
            amt = round(random.uniform(9400, 9950), 2)
            ts = base_time + timedelta(days=random.randint(1, 30), minutes=random.randint(0, 120))
            tx_list.append({
                "transaction_id": f"TX-{t_cnt:06d}",
                "source_account": s_src,
                "target_account": structuring_target,
                "amount": amt,
                "channel_type": "UPI",
                "timestamp": ts.isoformat(),
                "is_suspicious": True,
                "pattern_type": "STRUCTURING",
            })
            t_cnt += 1

    # Rapid Cash-Out (Velocity Anomaly)
    cashout_mules = [r["members"] for r in rings if r["is_fraud"]]
    if cashout_mules:
        mule_accs = cashout_mules[0]
        for m_acc in mule_accs[1:]:
            # Rapid deposits
            amt = round(random.uniform(15000, 45000), 2)
            ts_dep = base_time + timedelta(days=random.randint(1, 40))
            tx_list.append({
                "transaction_id": f"TX-{t_cnt:06d}",
                "source_account": m_acc,
                "target_account": mule_accs[0],  # Hub account
                "amount": amt,
                "channel_type": "MOBILE_APP",
                "timestamp": ts_dep.isoformat(),
                "is_suspicious": True,
                "pattern_type": "RAPID_CASHOUT_DEPOSIT",
            })
            t_cnt += 1

            # Instant ATM withdrawal (5 mins later)
            tx_list.append({
                "transaction_id": f"TX-{t_cnt:06d}",
                "source_account": mule_accs[0],
                "target_account": "ATM-CASH-OUT",
                "amount": amt * 0.95,
                "channel_type": "ATM",
                "timestamp": (ts_dep + timedelta(minutes=random.randint(2, 8))).isoformat(),
                "is_suspicious": True,
                "pattern_type": "RAPID_CASHOUT_ATM",
            })
            t_cnt += 1

    transactions_df = pd.DataFrame(tx_list)

    # Save CSV files to DATA_DIR
    accounts_df.to_csv(os.path.join(DATA_DIR, "accounts.csv"), index=False)
    transactions_df.to_csv(os.path.join(DATA_DIR, "transactions.csv"), index=False)
    devices_df.to_csv(os.path.join(DATA_DIR, "devices.csv"), index=False)
    ips_df.to_csv(os.path.join(DATA_DIR, "ips.csv"), index=False)

    return {
        "accounts": accounts_df,
        "transactions": transactions_df,
        "devices": devices_df,
        "ips": ips_df,
        "rings": rings
    }
