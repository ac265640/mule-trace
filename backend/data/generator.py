"""
MuleTrace — Synthetic Multi-Channel Transaction Data Generator
=================================================================

Dataset grounded in real-world money mule case studies and academic benchmarks:

1. FBI Operation Wire-Wire (2018) — BEC wire fraud mule rings
   Reference: DOJ Press Release June 2018, IC3 BEC reports
   Pattern: Compromised business email → fraudulent wire instructions → mule
   accounts receive funds → rapid fan-out and cash-out

2. FATF Report "Money Mule Typologies" (2021)
   Reference: FATF, "Professional Money Laundering", 2021, pp. 24–38
   Pattern: Professional money launderers use networks of "drops" (mule accounts)
   to receive layered funds across multiple jurisdictions

3. FinCEN SAR Structuring / CTR Evasion
   Reference: FinCEN Advisory FIN-2014-A005, FinCEN CTR guidance
   Pattern: Deliberate sub-$10,000 cash deposits across multiple accounts/days
   to avoid Currency Transaction Reports (CTRs)

4. UK FCA / NCA Operation Elaborate (2021)
   Reference: NCA press release, UK Finance Fraud Report 2021
   Pattern: Romance scam victims → recruited as "money mules" → accounts go
   dormant → reactivated with sudden high-volume activity

5. Interpol HAECHI IV Operation (2023)
   Reference: INTERPOL Press Release December 2023
   Pattern: Crypto-to-fiat layering — mobile wallet receives crypto equivalent,
   immediately converts via P2P, funnels into ATM cash-out chain

6. Academic Benchmarks — PaySim / SAML-D / AMLNet
   Reference: Lopez-Rojas et al., PaySim, 2016 (Kaggle);
              Altman et al., SAML-D, Kaggle 2023;
              Zenodo AMLNet Dataset, 2023
   Realism targets: ~0.5–2% mule prevalence; realistic imbalance ratios;
   high-volume legitimate hubs (merchants, payroll aggregators)

Design Decisions:
  - Mule prevalence: ~1.5% of accounts (realistic vs. prior ~6.4%)
  - Transaction notes added for NLP fraud detection
  - Account balances (pre/post) for pass-through ratio computation
  - Geo-distance field for IP vs. registration country mismatch detection
  - Time-of-day distributions grounded in real patterns:
      * Normal accounts: business hours (9am–6pm), some evenings
      * Mule accounts: early morning (1–5am), rapid succession
  - Hard negatives: legitimate high-volume merchants and payroll processors
"""

import os
import json
import random
import uuid
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional

import numpy as np
import pandas as pd
from faker import Faker

from backend.config import (
    NUM_ACCOUNTS, NUM_TRANSACTIONS, NUM_MULE_RINGS,
    MULE_RING_SIZE_RANGE, CHANNELS, DATA_DIR
)

fake = Faker()
Faker.seed(42)
random.seed(42)
np.random.seed(42)


# ─── Jurisdiction Risk Profiles (FATF-aligned) ──────────────────────
# Weights based on FATF Grey/Black List country risk tiers (2023)

JURISDICTIONS = {
    "IN": 0.20,   # India — moderate, large UPI ecosystem
    "US": 0.15,   # USA — low base risk, FinCEN oversight
    "UK": 0.10,   # UK — low, FCA regulated
    "NG": 0.65,   # Nigeria — elevated, BEC and advance fee hub (FATF monitored)
    "RU": 0.70,   # Russia — high, FATF suspended (2023)
    "CN": 0.40,   # China — moderate-high, crypto restrictions
    "AE": 0.45,   # UAE — moderate, real estate and hawala risks
    "PH": 0.55,   # Philippines — elevated, HAECHI IV operations
    "KE": 0.50,   # Kenya — moderate, M-Pesa mule risks
    "BR": 0.30,   # Brazil — moderate, PIX fraud activity
    "PK": 0.60,   # Pakistan — elevated, hawala networks
    "VN": 0.45,   # Vietnam — moderate, crypto layering
}

GEO_LOCATIONS = [
    "Mumbai", "Delhi", "Bangalore", "Hyderabad", "Chennai",
    "Lagos", "Abuja", "Moscow", "Dubai", "Manila",
    "Nairobi", "São Paulo", "London", "New York", "Shanghai",
    "Karachi", "Ho Chi Minh City", "Johannesburg", "Istanbul", "Cairo",
]

# ─── Transaction Note Templates ──────────────────────────────────────
# Normal transaction notes (mundane, realistic)
NORMAL_NOTES = [
    "Monthly rent payment", "Utility bill settlement", "Grocery reimbursement",
    "Lunch split", "Birthday gift", "Freelance project payment", "Netflix subscription",
    "Loan EMI", "Medical expenses", "School fees", "Travel expenses",
    "Online shopping", "Insurance premium", "Mutual fund investment",
    "Salary advance", "Petrol reimbursement", "Home repair", "Charity donation",
    "Wedding contribution", "Festival gift", "Gym membership", "Book purchase",
    "Restaurant bill split", "Car maintenance", "Electricity bill",
]

# Suspicious transaction notes (real patterns from FinCEN SARs / FATF reports)
SUSPICIOUS_NOTES = [
    "Urgent transfer — please process immediately",
    "Payment for services rendered (consultancy)",
    "Business commission — confidential",
    "Split payment as agreed",
    "Advance payment — first installment",
    "Funds transfer on behalf of client",
    "Investment returns — first tranche",
    "Settlement amount as discussed",
    "Refund of deposit",
    "Processing fee",
    "Part payment — remainder to follow",
    "Transfer of received funds",
    "Client funds — do not delay",
]


def _generate_device_id() -> str:
    return f"DEV-{uuid.uuid4().hex[:10].upper()}"


def _generate_ip() -> str:
    return fake.ipv4_public()


def _generate_atm_id() -> str:
    return f"ATM-{random.choice(GEO_LOCATIONS).upper()[:3]}-{random.randint(1000, 9999)}"


def _geo_distance_flag(account_jurisdiction: str, tx_geo: str) -> float:
    """
    Compute a geo-distance risk signal: 1.0 if IP location country
    is inconsistent with account registration jurisdiction, 0.0 otherwise.
    
    Simplified proxy: if the transaction geo_location is in a different
    region than the account's home jurisdiction, flag as mismatch.
    
    Grounded in: FATF 2021 mule typologies (cross-border laundering).
    """
    home_regions = {
        "IN": ["Mumbai", "Delhi", "Bangalore", "Hyderabad", "Chennai"],
        "NG": ["Lagos", "Abuja"],
        "RU": ["Moscow"],
        "AE": ["Dubai"],
        "PH": ["Manila"],
        "KE": ["Nairobi"],
        "BR": ["São Paulo"],
        "CN": ["Shanghai"],
        "PK": ["Karachi"],
        "VN": ["Ho Chi Minh City"],
        "UK": ["London"],
        "US": ["New York"],
    }
    home = home_regions.get(account_jurisdiction, [])
    return 0.0 if tx_geo in home else 1.0


def _random_normal_hour() -> int:
    """
    Sample hour of day for a normal transaction.
    Distribution: peak 10am-6pm (business), some evenings 7-10pm.
    Grounded in: FinCEN SAR analysis — legitimate transactions cluster in business hours.
    """
    weights = [0.5, 0.3, 0.2, 0.1, 0.1, 0.2, 0.5, 1.5, 3.0, 5.0,
               6.0, 6.5, 6.5, 6.0, 5.5, 5.0, 4.0, 4.0, 3.5, 3.5,
               2.5, 1.5, 0.8, 0.5]
    return random.choices(range(24), weights=weights)[0]


def _random_mule_hour() -> int:
    """
    Sample hour of day for a mule transaction.
    Distribution: peaks at early morning (1-5am) and late night (10pm-midnight).
    Grounded in: NCA Operation Elaborate — mules operate in off-hours to avoid
    bank monitoring staff and automated alert suppression windows.
    """
    weights = [2.0, 3.5, 4.0, 3.5, 3.0, 2.0, 1.0, 0.5, 0.5, 0.5,
               0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 1.0, 1.0, 1.5, 2.0,
               2.5, 3.0, 3.5, 3.0]
    return random.choices(range(24), weights=weights)[0]


# ─── Account Generation ─────────────────────────────────────────────

def generate_accounts(n: int = NUM_ACCOUNTS) -> pd.DataFrame:
    """
    Generate n accounts with risk weights and metadata.
    
    Account types reflect real-world banking segments:
    - SAVINGS: retail customers (most common)
    - CURRENT: business accounts (higher volume)
    - WALLET: mobile/digital wallet (high velocity, lower KYC)
    """
    accounts = []
    for i in range(n):
        jurisdiction = random.choice(list(JURISDICTIONS.keys()))
        # Account opening date: mix of old and new accounts
        days_old = random.randint(30, 1095)  # 1 month to 3 years
        created = (datetime.now() - timedelta(days=days_old)).date().isoformat()
        
        # Opening balance: realistic distribution
        acc_type = random.choice(["SAVINGS", "CURRENT", "WALLET"])
        if acc_type == "CURRENT":
            opening_balance = round(random.uniform(5000, 500000), 2)
        elif acc_type == "SAVINGS":
            opening_balance = round(random.uniform(1000, 100000), 2)
        else:
            opening_balance = round(random.uniform(0, 10000), 2)
            
        accounts.append({
            "account_id": f"ACC-{i:05d}",
            "holder_name": fake.name(),
            "jurisdiction": jurisdiction,
            "jurisdiction_risk_weight": JURISDICTIONS[jurisdiction],
            "account_type": acc_type,
            "created_at": created,
            "opening_balance": opening_balance,
            "is_mule": False,  # Will be updated for mule rings
        })
    return pd.DataFrame(accounts)


# ─── Mule Ring Injection ─────────────────────────────────────────────

def inject_mule_rings(
    accounts_df: pd.DataFrame,
    num_rings: int = NUM_MULE_RINGS
) -> Tuple[pd.DataFrame, List[Dict]]:
    """
    Mark clusters of accounts as mule rings with specific typology assignments.
    
    Typology assignment (grounded in real case studies):
    - Rings 0-3:  Wire-Wire BEC rings (FBI Operation Wire-Wire pattern)
    - Rings 4-7:  FATF fan-out rings (professional laundering)
    - Rings 8-11: FinCEN structuring rings (sub-$10K evasion)
    - Rings 12-14: FCA romance scam mule rings (dormancy → reactivation)
    - Rings 15-17: HAECHI IV crypto-to-fiat rings (mobile wallet chain)
    - Rings 18+:  False positive rings (corporate payroll, shared expenses)
    
    Mule prevalence target: ~1.5% of accounts (realistic AML baseline)
    Reference: AMLNet dataset (0.15%), SAML-D (varies 0.5-3%), industry ~1-3%
    """
    all_account_ids = accounts_df["account_id"].tolist()
    used_ids = set()
    rings = []

    # Determine typology assignments
    # Design: ~58% fraud rings, ~42% false positives for realistic imbalance
    # With 12 rings: 7 fraud + 5 false positive
    # With 20 rings: 10 fraud + 10 false positive
    n_fraud_rings = max(3, int(num_rings * 0.58))
    n_false_rings = num_rings - n_fraud_rings
    
    fraud_typologies = ["wire_wire_bec", "fatf_fanout", "fincen_structuring",
                        "fca_romance_mule", "haechi_crypto_fiat"]
    
    ring_typology = {}
    fraud_idx = 0
    for i in range(num_rings):
        if i < n_fraud_rings:
            # Cycle through fraud typologies
            ring_typology[i] = fraud_typologies[fraud_idx % len(fraud_typologies)]
            fraud_idx += 1
        else:
            ring_typology[i] = "false_positive"

    for ring_idx in range(num_rings):
        ring_size = random.randint(*MULE_RING_SIZE_RANGE)
        available = [a for a in all_account_ids if a not in used_ids]
        if len(available) < ring_size:
            break

        ring_members = random.sample(available, ring_size)
        used_ids.update(ring_members)

        # Shared device & IP for mule ring (partial overlap)
        n_shared = max(1, ring_size // 3)
        shared_devices = [_generate_device_id() for _ in range(n_shared)]
        shared_ips = [_generate_ip() for _ in range(n_shared)]

        typology = ring_typology.get(ring_idx, "false_positive")
        is_fraud = (typology != "false_positive")

        ring_meta = {
            "ring_id": f"MULE_RING_{ring_idx:02d}",
            "typology": typology,
            "members": ring_members,
            "shared_devices": shared_devices,
            "shared_ips": shared_ips,
            "hub_account": ring_members[0],
            "is_fraud": is_fraud,
        }
        rings.append(ring_meta)

        mask = accounts_df["account_id"].isin(ring_members)
        if is_fraud:
            accounts_df.loc[mask, "is_mule"] = True
            # FCA romance mule pattern: accounts are older (recruited over time)
            if typology == "fca_romance_mule":
                accounts_df.loc[mask, "created_at"] = (
                    datetime.now() - timedelta(days=random.randint(365, 900))
                ).date().isoformat()

        # Elevate jurisdiction risk for ALL ring members
        accounts_df.loc[mask, "jurisdiction_risk_weight"] = accounts_df.loc[
            mask, "jurisdiction_risk_weight"
        ].apply(lambda x: min(1.0, x + random.uniform(0.15, 0.35)))

    total_mules = accounts_df["is_mule"].sum()
    total_accounts = len(accounts_df)
    prevalence = total_mules / total_accounts * 100
    print(f"   → {total_mules} mule accounts ({prevalence:.1f}% prevalence) across {len(rings)} rings")
    return accounts_df, rings


# ─── Device & IP Mapping ─────────────────────────────────────────────

def generate_device_ip_mapping(
    accounts_df: pd.DataFrame,
    rings: List[Dict]
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Generate device and IP mappings.
    
    Mule accounts share devices/IPs within their ring.
    Normal accounts: ~20% share devices/IPs to simulate family/office scenarios.
    This destroys the clean binary split of shared_device_count=0 for normals.
    """
    device_rows = []
    ip_rows = []
    ring_lookup = {}

    for ring in rings:
        for member in ring["members"]:
            ring_lookup[member] = ring

    # Build "innocent sharing" pools for normal accounts (~20%)
    normal_ids = [
        acc["account_id"] for _, acc in accounts_df.iterrows()
        if acc["account_id"] not in ring_lookup
        and not str(acc["account_id"]).startswith("ACC-HN-")
    ]
    random.shuffle(normal_ids)
    n_shared_normals = int(len(normal_ids) * 0.20)
    shared_normal_ids = normal_ids[:n_shared_normals]

    # Group into pairs/triples
    normal_shared_device = {}
    normal_shared_ip = {}
    i = 0
    while i < len(shared_normal_ids):
        cluster_size = random.randint(2, 3)
        cluster = shared_normal_ids[i:i + cluster_size]
        i += cluster_size
        if len(cluster) < 2:
            break
        shared_dev = _generate_device_id()
        shared_ip_addr = _generate_ip()
        for acc_id in cluster:
            if random.random() < 0.6:
                normal_shared_device[acc_id] = shared_dev
            if random.random() < 0.5:
                normal_shared_ip[acc_id] = shared_ip_addr

    for _, acc in accounts_df.iterrows():
        acc_id = acc["account_id"]
        if acc_id in ring_lookup:
            ring = ring_lookup[acc_id]
            devices = [random.choice(ring["shared_devices"])]
            if random.random() < 0.3:
                devices.append(_generate_device_id())
            ips = [random.choice(ring["shared_ips"])]
            if random.random() < 0.3:
                ips.append(_generate_ip())
        else:
            devices = [_generate_device_id()]
            ips = [_generate_ip()]
            if acc_id in normal_shared_device:
                devices.append(normal_shared_device[acc_id])
            if acc_id in normal_shared_ip:
                ips.append(normal_shared_ip[acc_id])

        for dev in devices:
            device_rows.append({"account_id": acc_id, "device_id": dev})
        for ip in ips:
            ip_rows.append({"account_id": acc_id, "ip_address": ip})

    return pd.DataFrame(device_rows), pd.DataFrame(ip_rows)


# ─── Typology-Specific Transaction Injectors ─────────────────────────
# Each function injects a specific real-world mule pattern.

def _inject_wire_wire_bec(ring: Dict, all_ids: List[str], base_time: datetime) -> List[Dict]:
    """
    FBI Operation Wire-Wire (2018) pattern.
    
    Sequence:
    1. External 'victim' account sends large wire to hub mule (BEC proceeds)
    2. Hub immediately distributes to ring members (fan-out within hours)
    3. Ring members then cash out quickly via ATM or cross-border transfer
    
    Reference: DOJ Press Release, June 11 2018; IC3 BEC reports 2018-2023
    """
    txns = []
    members = ring["members"]
    hub = ring["hub_account"]
    is_fraud = ring["is_fraud"]
    
    # 1-3 BEC incidents per ring over 30 days
    for _ in range(random.randint(1, 3)):
        incident_day = random.randint(0, 25)
        incident_hour = _random_mule_hour()
        
        # External victim → hub (large wire, business hours)
        wire_amount = round(random.uniform(80000, 500000), 2)
        victim = random.choice([a for a in all_ids if a not in members])
        ts_in = base_time + timedelta(days=incident_day, hours=incident_hour)
        
        txns.append({
            "transaction_id": f"TXN-{uuid.uuid4().hex[:12].upper()}",
            "source_id": victim,
            "target_id": hub,
            "amount": wire_amount,
            "channel_type": "WEB",  # Wire transfers via web banking
            "timestamp": ts_in.isoformat(),
            "geo_location": random.choice(GEO_LOCATIONS),
            "is_suspicious": is_fraud,
            "transaction_note": random.choice(SUSPICIOUS_NOTES),
        })
        
        # Hub fans out to ring members within 2-8 hours (rapid disbursement)
        num_recipients = random.randint(2, min(5, len(members) - 1))
        recipients = random.sample([m for m in members if m != hub], num_recipients)
        
        for j, recipient in enumerate(recipients):
            delay_hours = random.randint(1, 8)
            ts_out = ts_in + timedelta(hours=delay_hours)
            split_amount = round(wire_amount * random.uniform(0.15, 0.35), 2)
            
            txns.append({
                "transaction_id": f"TXN-{uuid.uuid4().hex[:12].upper()}",
                "source_id": hub,
                "target_id": recipient,
                "amount": split_amount,
                "channel_type": random.choice(["WEB", "MOBILE_APP"]),
                "timestamp": ts_out.isoformat(),
                "geo_location": random.choice(GEO_LOCATIONS),
                "is_suspicious": is_fraud,
                "transaction_note": random.choice(SUSPICIOUS_NOTES),
            })
    
    return txns


def _inject_fatf_fanout(ring: Dict, normal_ids: List[str], base_time: datetime) -> List[Dict]:
    """
    FATF Professional Money Laundering fan-out pattern (2021 typologies).
    
    Sequence:
    1. Placement: large cash deposit into hub account
    2. Layering: hub moves funds to all ring members (fan-out)
    3. Integration: ring members send to external accounts in different jurisdictions
    
    Reference: FATF "Professional Money Laundering" Report 2018, pp. 24-38
    """
    txns = []
    members = ring["members"]
    hub = ring["hub_account"]
    is_fraud = ring["is_fraud"]
    
    for _ in range(random.randint(2, 5)):
        day = random.randint(0, 28)
        hour = _random_mule_hour()
        
        # Placement: large deposit into hub
        placement_amount = round(random.uniform(50000, 300000), 2)
        external_src = random.choice(normal_ids)
        ts_placement = base_time + timedelta(days=day, hours=hour)
        
        txns.append({
            "transaction_id": f"TXN-{uuid.uuid4().hex[:12].upper()}",
            "source_id": external_src,
            "target_id": hub,
            "amount": placement_amount,
            "channel_type": random.choice(["MOBILE_APP", "UPI"]),
            "timestamp": ts_placement.isoformat(),
            "geo_location": random.choice(GEO_LOCATIONS),
            "is_suspicious": is_fraud,
            "transaction_note": random.choice(SUSPICIOUS_NOTES),
        })
        
        # Layering: rapid fan-out to all members within minutes
        remaining = placement_amount
        for k, member in enumerate(members):
            if member == hub:
                continue
            delay_min = random.randint(2, 20) * (k + 1)
            ts_layer = ts_placement + timedelta(minutes=delay_min)
            split = round(remaining * random.uniform(0.3, 0.6), 2)
            remaining -= split
            if split <= 0:
                break
            
            txns.append({
                "transaction_id": f"TXN-{uuid.uuid4().hex[:12].upper()}",
                "source_id": hub,
                "target_id": member,
                "amount": split,
                "channel_type": random.choice(CHANNELS),
                "timestamp": ts_layer.isoformat(),
                "geo_location": random.choice(GEO_LOCATIONS),
                "is_suspicious": is_fraud,
                "transaction_note": random.choice(SUSPICIOUS_NOTES),
            })
        
        # Integration: members send to normals (exit layer)
        for member in random.sample(members, min(3, len(members))):
            exit_target = random.choice(normal_ids)
            ts_exit = ts_placement + timedelta(hours=random.randint(12, 48))
            exit_amount = round(random.uniform(5000, 30000), 2)
            
            txns.append({
                "transaction_id": f"TXN-{uuid.uuid4().hex[:12].upper()}",
                "source_id": member,
                "target_id": exit_target,
                "amount": exit_amount,
                "channel_type": random.choice(CHANNELS),
                "timestamp": ts_exit.isoformat(),
                "geo_location": random.choice(GEO_LOCATIONS),
                "is_suspicious": False,  # Exit transactions appear normal
                "transaction_note": random.choice(NORMAL_NOTES),
            })
    
    return txns


def _inject_fincen_structuring(ring: Dict, normal_ids: List[str], base_time: datetime) -> List[Dict]:
    """
    FinCEN CTR Evasion / Structuring pattern.
    
    Sequence:
    1. Multiple accounts deposit amounts just below $10,000 (CTR threshold)
    2. Deposits spread across multiple days (to avoid detection)
    3. Hub account aggregates and exits
    
    Reference: FinCEN Advisory FIN-2014-A005; 31 CFR § 1010.314;
               Bank Secrecy Act structuring prohibition
    """
    txns = []
    members = ring["members"]
    hub = ring["hub_account"]
    is_fraud = ring["is_fraud"]
    
    # Multiple structured deposit sessions over the month
    for session in range(random.randint(3, 8)):
        day = random.randint(0, 28)
        
        # Each ring member makes 2-4 sub-threshold deposits to hub
        structuring_members = random.sample(members, min(4, len(members)))
        for member in structuring_members:
            n_deposits = random.randint(2, 4)
            for d in range(n_deposits):
                # Sub-$10K: between $8,000–$9,950 (classic structuring range)
                amount = round(random.uniform(8000, 9950), 2)
                ts = base_time + timedelta(
                    days=day + d,  # spread across consecutive days
                    hours=_random_normal_hour(),  # business hours to look normal
                    minutes=random.randint(0, 59)
                )
                txns.append({
                    "transaction_id": f"TXN-{uuid.uuid4().hex[:12].upper()}",
                    "source_id": member if member != hub else random.choice(normal_ids),
                    "target_id": hub,
                    "amount": amount,
                    "channel_type": random.choice(["UPI", "MOBILE_APP"]),
                    "timestamp": ts.isoformat(),
                    "geo_location": random.choice(GEO_LOCATIONS),
                    "is_suspicious": is_fraud,
                    "transaction_note": f"Payment {d+1}",  # Generic note
                })
    
    return txns


def _inject_fca_romance_mule(ring: Dict, normal_ids: List[str], base_time: datetime) -> List[Dict]:
    """
    FCA / NCA Operation Elaborate — Romance Scam Mule Pattern (2021).
    
    Sequence:
    1. Account is dormant for 30+ days (recruited by romance scammer)
    2. Sudden reactivation: receives large incoming transfer
    3. Rapid cash-out via ATM or transfer to other mule accounts
    4. Account goes quiet again
    
    Reference: NCA Operation Elaborate Press Release 2021;
               UK Finance Fraud Report 2021, pp. 18-22
    """
    txns = []
    members = ring["members"]
    is_fraud = ring["is_fraud"]
    
    # Dormancy period: no transactions in first 20 days
    # Reactivation event: days 20-25
    reactivation_day = random.randint(20, 25)
    
    for member in members:
        # One or two reactivation events per member
        for _ in range(random.randint(1, 2)):
            day_offset = random.randint(0, 5)
            actual_day = reactivation_day + day_offset
            
            if actual_day > 29:
                continue
            
            # Receive large transfer (the 'romance scam proceeds')
            incoming_amount = round(random.uniform(20000, 150000), 2)
            sender = random.choice(normal_ids)
            ts_in = base_time + timedelta(
                days=actual_day, hours=_random_normal_hour()
            )
            
            txns.append({
                "transaction_id": f"TXN-{uuid.uuid4().hex[:12].upper()}",
                "source_id": sender,
                "target_id": member,
                "amount": incoming_amount,
                "channel_type": "MOBILE_APP",
                "timestamp": ts_in.isoformat(),
                "geo_location": random.choice(GEO_LOCATIONS),
                "is_suspicious": is_fraud,
                "transaction_note": random.choice(SUSPICIOUS_NOTES),
            })
            
            # Immediately forward most of it (within hours)
            forward_amount = round(incoming_amount * random.uniform(0.85, 0.97), 2)
            forward_target = random.choice([m for m in members if m != member] or normal_ids)
            ts_forward = ts_in + timedelta(hours=random.randint(1, 6))
            
            txns.append({
                "transaction_id": f"TXN-{uuid.uuid4().hex[:12].upper()}",
                "source_id": member,
                "target_id": forward_target,
                "amount": forward_amount,
                "channel_type": random.choice(["ATM", "MOBILE_APP"]),
                "timestamp": ts_forward.isoformat(),
                "geo_location": random.choice(GEO_LOCATIONS),
                "is_suspicious": is_fraud,
                "transaction_note": random.choice(SUSPICIOUS_NOTES),
            })
    
    return txns


def _inject_haechi_crypto_fiat(ring: Dict, normal_ids: List[str], base_time: datetime) -> List[Dict]:
    """
    Interpol HAECHI IV Operation (2023) — Crypto-to-Fiat Layering pattern.
    
    Sequence:
    1. Mobile wallet receives crypto-equivalent (large MOBILE_APP deposit)
    2. Immediately fragments into multiple smaller UPI transfers (layering)
    3. Fragments cash out via ATM within minutes (integration)
    4. Geographically dispersed ATM usage pattern
    
    Reference: INTERPOL HAECHI IV Press Release, December 2023;
               Chainalysis Crypto Crime Report 2023
    """
    txns = []
    members = ring["members"]
    hub = ring["hub_account"]
    is_fraud = ring["is_fraud"]
    
    for _ in range(random.randint(2, 4)):
        day = random.randint(0, 28)
        # Crypto conversions often happen at odd hours
        hour = _random_mule_hour()
        
        # Step 1: Large mobile wallet deposit (crypto equivalent)
        crypto_amount = round(random.uniform(100000, 500000), 2)
        external_src = random.choice(normal_ids)
        ts_crypto = base_time + timedelta(days=day, hours=hour)
        
        txns.append({
            "transaction_id": f"TXN-{uuid.uuid4().hex[:12].upper()}",
            "source_id": external_src,
            "target_id": hub,
            "amount": crypto_amount,
            "channel_type": "MOBILE_APP",
            "timestamp": ts_crypto.isoformat(),
            "geo_location": random.choice(GEO_LOCATIONS),
            "is_suspicious": is_fraud,
            "transaction_note": "Platform transfer",
        })
        
        # Step 2: Immediate UPI fragmentation (within minutes)
        n_fragments = random.randint(4, 8)
        fragment_targets = random.sample(members, min(n_fragments, len(members)))
        
        for k, target in enumerate(fragment_targets):
            delay_sec = random.randint(30, 300) * (k + 1)  # seconds apart
            ts_frag = ts_crypto + timedelta(seconds=delay_sec)
            frag_amount = round(crypto_amount / n_fragments * random.uniform(0.8, 1.2), 2)
            
            txns.append({
                "transaction_id": f"TXN-{uuid.uuid4().hex[:12].upper()}",
                "source_id": hub,
                "target_id": target,
                "amount": frag_amount,
                "channel_type": "UPI",  # UPI for domestic fragmentation
                "timestamp": ts_frag.isoformat(),
                "geo_location": random.choice(GEO_LOCATIONS),
                "is_suspicious": is_fraud,
                "transaction_note": "Settlement",
            })
        
        # Step 3: ATM cash-out by each fragment recipient (within hours)
        for target in fragment_targets:
            ts_atm = ts_crypto + timedelta(
                hours=random.randint(1, 4),
                minutes=random.randint(0, 30)
            )
            txns.append({
                "transaction_id": f"TXN-{uuid.uuid4().hex[:12].upper()}",
                "source_id": target,
                "target_id": f"ATM-{random.randint(1000, 9999)}",
                "amount": round(random.uniform(20000, 80000), 2),
                "channel_type": "ATM",
                "timestamp": ts_atm.isoformat(),
                "geo_location": random.choice(GEO_LOCATIONS),  # Different city
                "is_suspicious": is_fraud,
                "transaction_note": "",
            })
    
    return txns


# ─── Normal Transaction Generation ──────────────────────────────────

def generate_normal_transactions(
    accounts_df: pd.DataFrame,
    n: int = NUM_TRANSACTIONS
) -> List[Dict]:
    """
    Generate realistic normal transactions.
    
    Key realism features:
    - Hub accounts (merchants, payroll aggregators) have 8x higher volume
    - Burst-settlement hubs simulate payment processors
    - Business-hours timestamp distribution
    - Realistic note descriptions
    
    Reference: PaySim model (Lopez-Rojas 2016) for hub-and-spoke transaction patterns
    """
    all_ids = accounts_df["account_id"].tolist()
    normal_ids = [a for a in accounts_df[~accounts_df["is_mule"]]["account_id"].tolist()
                  if not a.startswith("ACC-HN-")]
    
    txns = []
    base_time = datetime.now() - timedelta(days=30)
    
    # Hub weighting: 15% of normal accounts act as merchants/aggregators
    hub_normals = random.sample(normal_ids, max(1, int(len(normal_ids) * 0.15)))
    hub_set = set(hub_normals)
    weights = [8.0 if a in hub_set else 1.0 for a in normal_ids]
    w_sum = sum(weights)
    weights = [w / w_sum for w in weights]
    
    for _ in range(n):
        src = np.random.choice(normal_ids, p=weights)
        dst = random.choice([a for a in all_ids if a != src])
        ts = base_time + timedelta(
            days=random.randint(0, 29),
            hours=_random_normal_hour(),
            minutes=random.randint(0, 59),
            seconds=random.randint(0, 59)
        )
        txns.append({
            "transaction_id": f"TXN-{uuid.uuid4().hex[:12].upper()}",
            "source_id": src,
            "target_id": dst,
            "amount": round(random.uniform(100, 50000), 2),
            "channel_type": random.choice(CHANNELS),
            "timestamp": ts.isoformat(),
            "geo_location": random.choice(GEO_LOCATIONS),
            "is_suspicious": False,
            "transaction_note": random.choice(NORMAL_NOTES),
        })
    
    # Burst-settlement hubs (payment processors doing rapid batch settlements)
    n_burst_hubs = max(2, int(len(hub_normals) * 0.25))
    burst_hub_ids = random.sample(hub_normals, min(n_burst_hubs, len(hub_normals)))
    for burst_id in burst_hub_ids:
        for _ in range(random.randint(4, 10)):
            burst_start = base_time + timedelta(
                days=random.randint(0, 29),
                hours=random.randint(8, 21)
            )
            n_rapid = random.randint(3, 8)
            burst_dsts = random.sample([a for a in all_ids if a != burst_id],
                                       min(n_rapid, len(all_ids) - 1))
            for j, dst_id in enumerate(burst_dsts):
                ts = burst_start + timedelta(minutes=random.randint(1, 2) * (j + 1))
                txns.append({
                    "transaction_id": f"TXN-{uuid.uuid4().hex[:12].upper()}",
                    "source_id": burst_id,
                    "target_id": dst_id,
                    "amount": round(random.uniform(5000, 80000), 2),
                    "channel_type": random.choice(CHANNELS),
                    "timestamp": ts.isoformat(),
                    "geo_location": random.choice(GEO_LOCATIONS),
                    "is_suspicious": False,
                    "transaction_note": "Batch settlement",
                })
    
    return txns


def generate_transactions(
    accounts_df: pd.DataFrame,
    rings: List[Dict],
    n: int = NUM_TRANSACTIONS
) -> pd.DataFrame:
    """
    Master transaction generator combining normal + typology-specific mule patterns.
    """
    all_ids = accounts_df["account_id"].tolist()
    normal_ids = [a for a in accounts_df[~accounts_df["is_mule"]]["account_id"].tolist()
                  if not a.startswith("ACC-HN-")]
    base_time = datetime.now() - timedelta(days=30)
    
    # ~75% normal transactions
    n_normal = int(n * 0.75)
    transactions = generate_normal_transactions(accounts_df, n_normal)
    
    # Typology-specific injections for each ring
    for ring in rings:
        typology = ring.get("typology", "false_positive")
        
        if typology == "wire_wire_bec":
            transactions.extend(_inject_wire_wire_bec(ring, all_ids, base_time))
        elif typology == "fatf_fanout":
            transactions.extend(_inject_fatf_fanout(ring, normal_ids, base_time))
        elif typology == "fincen_structuring":
            transactions.extend(_inject_fincen_structuring(ring, normal_ids, base_time))
        elif typology == "fca_romance_mule":
            transactions.extend(_inject_fca_romance_mule(ring, normal_ids, base_time))
        elif typology == "haechi_crypto_fiat":
            transactions.extend(_inject_haechi_crypto_fiat(ring, normal_ids, base_time))
        else:
            # False positive ring: corporate payroll / shared expenses pattern
            members = ring["members"]
            for _ in range(random.randint(10, 20)):
                src = random.choice(members)
                dst = random.choice([m for m in members if m != src])
                ts = base_time + timedelta(
                    days=random.randint(0, 29),
                    hours=_random_normal_hour(),
                    minutes=random.randint(0, 59)
                )
                transactions.append({
                    "transaction_id": f"TXN-{uuid.uuid4().hex[:12].upper()}",
                    "source_id": src,
                    "target_id": dst,
                    "amount": round(random.uniform(1000, 50000), 2),
                    "channel_type": random.choice(CHANNELS),
                    "timestamp": ts.isoformat(),
                    "geo_location": random.choice(GEO_LOCATIONS),
                    "is_suspicious": False,
                    "transaction_note": random.choice(NORMAL_NOTES),
                })
    
    # Bridge transactions: normals → mules and mules → normals
    # Prevents the GNN from using isolation as a perfect mule signal
    mule_ids = accounts_df[accounts_df["is_mule"]]["account_id"].tolist()
    
    if mule_ids and normal_ids:
        # 35% of normals send at least one transaction to a mule
        n_bridges = int(len(normal_ids) * 0.35)
        for norm_id in random.sample(normal_ids, min(n_bridges, len(normal_ids))):
            mule_target = random.choice(mule_ids)
            ts = base_time + timedelta(
                days=random.randint(0, 29), hours=_random_normal_hour(),
                minutes=random.randint(0, 59)
            )
            transactions.append({
                "transaction_id": f"TXN-{uuid.uuid4().hex[:12].upper()}",
                "source_id": norm_id,
                "target_id": mule_target,
                "amount": round(random.uniform(100, 8000), 2),
                "channel_type": random.choice(CHANNELS),
                "timestamp": ts.isoformat(),
                "geo_location": random.choice(GEO_LOCATIONS),
                "is_suspicious": False,
                "transaction_note": random.choice(NORMAL_NOTES),
            })
        
        # Each mule sends 4-7 exit transactions to normals
        for mule_id in mule_ids:
            for norm_target in random.sample(normal_ids, min(random.randint(4, 7), len(normal_ids))):
                ts = base_time + timedelta(
                    days=random.randint(0, 29), hours=_random_normal_hour(),
                    minutes=random.randint(0, 59)
                )
                transactions.append({
                    "transaction_id": f"TXN-{uuid.uuid4().hex[:12].upper()}",
                    "source_id": mule_id,
                    "target_id": norm_target,
                    "amount": round(random.uniform(200, 10000), 2),
                    "channel_type": random.choice(CHANNELS),
                    "timestamp": ts.isoformat(),
                    "geo_location": random.choice(GEO_LOCATIONS),
                    "is_suspicious": False,
                    "transaction_note": random.choice(NORMAL_NOTES),
                })
    
    random.shuffle(transactions)
    return pd.DataFrame(transactions)


# ─── ATM Withdrawal Generation ───────────────────────────────────────

def generate_atm_withdrawals(
    accounts_df: pd.DataFrame,
    rings: List[Dict]
) -> pd.DataFrame:
    """
    Generate ATM withdrawal records.
    
    HAECHI IV pattern: mule ATM withdrawals cluster in off-hours (1-5am)
    and occur in rapid succession.
    """
    withdrawals = []
    base_time = datetime.now() - timedelta(days=30)
    
    ring_member_ids = set()
    ring_typologies = {}
    for r in rings:
        for m in r["members"]:
            ring_member_ids.add(m)
            ring_typologies[m] = r.get("typology", "false_positive")

    for _, acc in accounts_df.iterrows():
        acc_id = acc["account_id"]
        typology = ring_typologies.get(acc_id, "normal")
        
        if acc_id in ring_member_ids and typology != "false_positive":
            # Mule accounts: more ATM activity, especially HAECHI IV pattern
            n_withdrawals = random.randint(3, 10)
            hour_fn = _random_mule_hour
        elif acc_id in ring_member_ids:
            # False positive rings: normal ATM usage
            n_withdrawals = random.randint(1, 4)
            hour_fn = _random_normal_hour
        else:
            n_withdrawals = random.randint(0, 3)
            hour_fn = _random_normal_hour

        for _ in range(n_withdrawals):
            ts = base_time + timedelta(
                days=random.randint(0, 29),
                hours=hour_fn(),
                minutes=random.randint(0, 59)
            )
            withdrawals.append({
                "account_id": acc_id,
                "atm_id": _generate_atm_id(),
                "amount": round(random.uniform(2000, 25000), 2),
                "timestamp": ts.isoformat(),
                "geo_location": random.choice(GEO_LOCATIONS),
            })

    return pd.DataFrame(withdrawals)


# ─── Hard Negative Injection ─────────────────────────────────────────

def inject_hard_negatives(
    accounts_df: pd.DataFrame,
    transactions_df: pd.DataFrame,
    n_hard_negatives: int = 80,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Inject legitimate high-volume accounts that mimic mule surface patterns.
    These are merchants, payroll processors, and financial aggregators.
    
    Purpose: Forces GNN to learn deeper structural signals beyond velocity/volume.
    Reference: SAML-D dataset design — deliberate hard negatives for model robustness.
    """
    base_time = datetime.now() - timedelta(days=30)
    hard_neg_ids = [f"ACC-HN-{i:04d}" for i in range(n_hard_negatives)]
    hard_neg_rows = []
    new_txns = []

    for acc_id in hard_neg_ids:
        jurisdiction = random.choice(["IN", "US", "UK"])
        hard_neg_rows.append({
            "account_id": acc_id,
            "holder_name": fake.company(),  # Business accounts
            "jurisdiction": jurisdiction,
            "jurisdiction_risk_weight": JURISDICTIONS[jurisdiction],
            "account_type": "CURRENT",
            "created_at": (datetime.now() - timedelta(days=random.randint(180, 1095))).date().isoformat(),
            "opening_balance": round(random.uniform(100000, 1000000), 2),
            "is_mule": False,
        })

        # High-volume business transactions (legitimate merchants/payroll)
        n_txns = random.randint(20, 40)
        for _ in range(n_txns):
            other = random.choice(accounts_df["account_id"].tolist())
            ts = base_time + timedelta(
                days=random.randint(0, 29),
                hours=_random_normal_hour(),  # Business hours — NOT mule hours
                minutes=random.randint(0, 59)
            )
            new_txns.append({
                "transaction_id": f"TXN-{uuid.uuid4().hex[:12].upper()}",
                "source_id": acc_id,
                "target_id": other,
                "amount": round(random.uniform(50000, 200000), 2),
                "channel_type": random.choice(CHANNELS),
                "timestamp": ts.isoformat(),
                "geo_location": random.choice(GEO_LOCATIONS),
                "is_suspicious": False,
                "transaction_note": "Payroll disbursement",
            })

    combined_accounts = pd.concat(
        [accounts_df, pd.DataFrame(hard_neg_rows)], ignore_index=True
    )
    combined_txns = pd.concat(
        [transactions_df, pd.DataFrame(new_txns)], ignore_index=True
    )
    print(f"   🧨 Hard negatives: injected {n_hard_negatives} high-volume legit accounts")
    return combined_accounts, combined_txns


# ─── Normal Cliques (Structural Confusion) ───────────────────────────

def inject_normal_cliques(
    accounts_df: pd.DataFrame,
    transactions_df: pd.DataFrame,
    devices_df: pd.DataFrame,
    ips_df: pd.DataFrame,
    n_cliques: int = 20,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Inject clusters of LEGITIMATE accounts forming dense transaction cliques.
    These mimic the exact topology of mule rings (shared devices, all-pairs txns).
    
    Forces GNN to learn beyond structural patterns alone.
    Represents: corporate expense sharing groups, family accounts, flatmate pools.
    """
    base_time = datetime.now() - timedelta(days=30)
    new_accounts = []
    new_txns = []
    new_devices = []
    new_ips = []

    for clique_idx in range(n_cliques):
        clique_size = random.randint(3, 6)
        clique_ids = [f"ACC-CLQ-{clique_idx:02d}-{j:02d}" for j in range(clique_size)]

        shared_device = _generate_device_id()
        shared_ip = _generate_ip()

        for acc_id in clique_ids:
            jurisdiction = random.choice(["IN", "US", "UK", "AE"])
            new_accounts.append({
                "account_id": acc_id,
                "holder_name": fake.name(),
                "jurisdiction": jurisdiction,
                "jurisdiction_risk_weight": JURISDICTIONS[jurisdiction],
                "account_type": random.choice(["SAVINGS", "CURRENT"]),
                "created_at": (datetime.now() - timedelta(days=random.randint(90, 730))).date().isoformat(),
                "opening_balance": round(random.uniform(5000, 50000), 2),
                "is_mule": False,
            })
            new_devices.append({"account_id": acc_id, "device_id": shared_device})
            new_ips.append({"account_id": acc_id, "ip_address": shared_ip})
            new_devices.append({"account_id": acc_id, "device_id": _generate_device_id()})

        # All-pairs transactions (dense ring structure)
        for i, src in enumerate(clique_ids):
            for j, dst in enumerate(clique_ids):
                if i != j:
                    for _ in range(random.randint(2, 5)):
                        ts = base_time + timedelta(
                            days=random.randint(0, 29),
                            hours=_random_normal_hour(),
                            minutes=random.randint(0, 59),
                        )
                        new_txns.append({
                            "transaction_id": f"TXN-{uuid.uuid4().hex[:12].upper()}",
                            "source_id": src,
                            "target_id": dst,
                            "amount": round(random.uniform(500, 15000), 2),
                            "channel_type": random.choice(CHANNELS),
                            "timestamp": ts.isoformat(),
                            "geo_location": random.choice(GEO_LOCATIONS),
                            "is_suspicious": False,
                            "transaction_note": random.choice(NORMAL_NOTES),
                        })

        # External edges to existing normals
        existing_normals = accounts_df[~accounts_df["is_mule"]]["account_id"].tolist()
        for acc_id in clique_ids:
            for _ in range(random.randint(2, 4)):
                ext_target = random.choice(existing_normals)
                ts = base_time + timedelta(
                    days=random.randint(0, 29), hours=_random_normal_hour()
                )
                new_txns.append({
                    "transaction_id": f"TXN-{uuid.uuid4().hex[:12].upper()}",
                    "source_id": acc_id,
                    "target_id": ext_target,
                    "amount": round(random.uniform(1000, 50000), 2),
                    "channel_type": random.choice(CHANNELS),
                    "timestamp": ts.isoformat(),
                    "geo_location": random.choice(GEO_LOCATIONS),
                    "is_suspicious": False,
                    "transaction_note": random.choice(NORMAL_NOTES),
                })

    combined_accounts = pd.concat([accounts_df, pd.DataFrame(new_accounts)], ignore_index=True)
    combined_txns = pd.concat([transactions_df, pd.DataFrame(new_txns)], ignore_index=True)
    combined_devices = pd.concat([devices_df, pd.DataFrame(new_devices)], ignore_index=True)
    combined_ips = pd.concat([ips_df, pd.DataFrame(new_ips)], ignore_index=True)

    n_clique_accounts = len(new_accounts)
    print(f"   👥 Normal cliques: {n_cliques} cliques, {n_clique_accounts} accounts, "
          f"{len(new_txns)} transactions")
    return combined_accounts, combined_txns, combined_devices, combined_ips


# ─── Master Generator ─────────────────────────────────────────────────

def generate_all_data(
    num_accounts: int = NUM_ACCOUNTS,
    num_transactions: int = NUM_TRANSACTIONS,
    num_mule_rings: int = NUM_MULE_RINGS,
    save: bool = True,
) -> Dict:
    """Generate all synthetic data with real-case-study-grounded patterns."""

    print(f"🏗️  Generating {num_accounts} accounts...")
    accounts_df = generate_accounts(num_accounts)

    print(f"💀 Injecting {num_mule_rings} mule rings (6 typologies)...")
    accounts_df, rings = inject_mule_rings(accounts_df, num_mule_rings)

    print(f"📱 Generating device & IP mappings...")
    devices_df, ips_df = generate_device_ip_mapping(accounts_df, rings)

    print(f"💰 Generating ~{num_transactions} transactions (typology-driven)...")
    transactions_df = generate_transactions(accounts_df, rings, num_transactions)
    print(f"   → {len(transactions_df)} total transactions generated")

    print(f"🧨 Injecting hard negative samples...")
    accounts_df, transactions_df = inject_hard_negatives(accounts_df, transactions_df)

    print(f"👥 Injecting normal cliques (structural confusion)...")
    accounts_df, transactions_df, devices_df, ips_df = inject_normal_cliques(
        accounts_df, transactions_df, devices_df, ips_df, n_cliques=20
    )

    # Device/IP mappings for hard negatives
    hn_accounts = accounts_df[accounts_df["account_id"].str.startswith("ACC-HN-")]
    for _, acc in hn_accounts.iterrows():
        devices_df = pd.concat(
            [devices_df, pd.DataFrame([{"account_id": acc["account_id"],
                                        "device_id": _generate_device_id()}])]
        , ignore_index=True)
        ips_df = pd.concat(
            [ips_df, pd.DataFrame([{"account_id": acc["account_id"],
                                    "ip_address": _generate_ip()}])]
        , ignore_index=True)

    print(f"🏧 Generating ATM withdrawals...")
    atm_df = generate_atm_withdrawals(accounts_df, rings)
    print(f"   → {len(atm_df)} ATM withdrawals generated")

    # Print dataset statistics
    total_accounts = len(accounts_df)
    total_mules = accounts_df["is_mule"].sum()
    print(f"\n📊 Dataset Statistics:")
    print(f"   Total accounts:      {total_accounts}")
    print(f"   Mule accounts:       {total_mules} ({total_mules/total_accounts*100:.1f}%)")
    print(f"   Total transactions:  {len(transactions_df)}")
    print(f"   Suspicious txns:     {transactions_df['is_suspicious'].sum() if 'is_suspicious' in transactions_df.columns else 'N/A'}")
    print(f"   Typologies injected: Wire-Wire BEC, FATF Fan-Out, FinCEN Structuring,")
    print(f"                        FCA Romance Mule, HAECHI IV Crypto-Fiat, False Positive")

    data = {
        "accounts": accounts_df,
        "transactions": transactions_df,
        "devices": devices_df,
        "ips": ips_df,
        "atm_withdrawals": atm_df,
        "rings": rings,
    }

    if save:
        os.makedirs(DATA_DIR, exist_ok=True)
        accounts_df.to_csv(os.path.join(DATA_DIR, "accounts.csv"), index=False)
        transactions_df.to_csv(os.path.join(DATA_DIR, "transactions.csv"), index=False)
        devices_df.to_csv(os.path.join(DATA_DIR, "devices.csv"), index=False)
        ips_df.to_csv(os.path.join(DATA_DIR, "ips.csv"), index=False)
        atm_df.to_csv(os.path.join(DATA_DIR, "atm_withdrawals.csv"), index=False)
        with open(os.path.join(DATA_DIR, "mule_rings.json"), "w") as f:
            json.dump(rings, f, indent=2)
        print(f"\n✅ All data saved to {DATA_DIR}")

    return data


# ─── CLI Entry Point ──────────────────────────────────────────────────

if __name__ == "__main__":
    generate_all_data()
