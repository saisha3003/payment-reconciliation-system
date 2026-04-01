"""
==============================================================================
  PAYMENT PLATFORM ↔ BANK RECONCILIATION SYSTEM
  Assessment Simulation | Fully Runnable | Python 3.8+
==============================================================================

ASSUMPTIONS
-----------
1. The payments platform records transactions instantly (T+0).
2. The bank settles transactions with a 1–2 business day delay (T+1 or T+2).
3. Both datasets cover the same calendar month (June 2024).
4. Transaction IDs are unique on the platform side; the bank echoes the
   platform's txn_id for matching.
5. Amounts are in INR, stored as floats; rounding differences <= 0.05 are
   treated as acceptable (configurable via ROUNDING_TOLERANCE).
6. Duplicates on the bank side represent double-settlement errors.
7. A platform transaction with no matching bank settlement = "unsettled".
8. A bank entry with no matching platform transaction = "phantom".
9. Currency conversion is out of scope; all amounts are in INR.
10. Refunds are treated as negative-amount transactions.

==============================================================================
"""

import csv
import io
import random
from datetime import date, timedelta
from collections import defaultdict
from dataclasses import dataclass, field
from typing import List, Dict

ROUNDING_TOLERANCE = 0.05
SETTLEMENT_DELAY_DAYS = (1, 2)
random.seed(42)

# ─────────────────────────────────────────────
#  DATA STRUCTURES
# ─────────────────────────────────────────────
@dataclass
class PlatformTransaction:
    txn_id: str
    merchant_id: str
    amount: float
    currency: str
    status: str        # SUCCESS, FAILED, REFUND
    created_at: date

@dataclass
class BankSettlement:
    bank_ref: str
    txn_id: str
    settled_amount: float
    settlement_date: date
    settlement_status: str

@dataclass
class ReconciliationResult:
    matched: List[dict] = field(default_factory=list)
    unmatched_platform: List[dict] = field(default_factory=list)
    unmatched_bank: List[dict] = field(default_factory=list)
    amount_mismatches: List[dict] = field(default_factory=list)
    duplicates: List[dict] = field(default_factory=list)
    rounding_differences: List[dict] = field(default_factory=list)


# ─────────────────────────────────────────────
#  DATA GENERATION
# ─────────────────────────────────────────────
MERCHANTS = ["M001", "M002", "M003", "M004", "M005"]

def random_date_in_june() -> date:
    return date(2024, 6, random.randint(1, 27))

def settle_date(txn_date: date) -> date:
    return txn_date + timedelta(days=random.choice(SETTLEMENT_DELAY_DAYS))

def generate_platform_transactions(n: int = 30) -> List[PlatformTransaction]:
    txns = []
    for i in range(1, n + 1):
        txn_date = random_date_in_june()
        status = random.choices(
            ["SUCCESS", "SUCCESS", "SUCCESS", "FAILED", "REFUND"],
            weights=[60, 60, 60, 10, 10]
        )[0]
        amount = round(random.uniform(500, 50000), 2)
        if status == "REFUND":
            amount = -round(random.uniform(200, 5000), 2)
        txns.append(PlatformTransaction(
            txn_id=f"TXN{i:04d}",
            merchant_id=random.choice(MERCHANTS),
            amount=amount,
            currency="INR",
            status=status,
            created_at=txn_date
        ))
    return txns

def generate_bank_settlements(platform_txns: List[PlatformTransaction]) -> List[BankSettlement]:
    """
    Generates bank settlements with deliberate real-world anomalies:
      ① Normal settlements
      ② Missing settlements (platform has record, bank does not)
      ③ Duplicate settlements (bank settled twice)
      ④ Rounding differences (paise-level)
      ⑤ Amount mismatches (significant discrepancy)
      ⑥ Phantom bank entries (no matching platform transaction)
    """
    settlements = []
    ref = 1
    successful = [t for t in platform_txns if t.status in ("SUCCESS", "REFUND")]
    random.shuffle(successful)
    n = len(successful)

    missing_idx   = set(random.sample(range(n), 2))
    duplicate_idx = set(random.sample(range(n), 2))
    rounding_idx  = set(random.sample(range(n), 3))
    mismatch_idx  = set(random.sample(range(n), 2))

    for idx, txn in enumerate(successful):
        if idx in missing_idx:
            continue  # ② intentionally skip

        amt = txn.amount
        if idx in mismatch_idx:
            amt = round(txn.amount + random.choice([-1, 1]) * random.uniform(50, 200), 2)  # ⑤
        elif idx in rounding_idx:
            amt = round(txn.amount + random.choice([-1, 1]) * round(random.uniform(0.01, 0.04), 2), 2)  # ④

        settlements.append(BankSettlement(
            bank_ref=f"BANK{ref:05d}", txn_id=txn.txn_id,
            settled_amount=amt, settlement_date=settle_date(txn.created_at),
            settlement_status="SETTLED"
        ))
        ref += 1

        if idx in duplicate_idx:  # ③
            settlements.append(BankSettlement(
                bank_ref=f"BANK{ref:05d}", txn_id=txn.txn_id,
                settled_amount=txn.amount, settlement_date=settle_date(txn.created_at),
                settlement_status="SETTLED"
            ))
            ref += 1

    for _ in range(2):  # ⑥ phantoms
        settlements.append(BankSettlement(
            bank_ref=f"BANK{ref:05d}", txn_id=f"TXN_PHANTOM_{ref}",
            settled_amount=round(random.uniform(1000, 20000), 2),
            settlement_date=random_date_in_june() + timedelta(days=2),
            settlement_status="SETTLED"
        ))
        ref += 1

    return settlements


# ─────────────────────────────────────────────
#  RECONCILIATION ENGINE
# ─────────────────────────────────────────────
def reconcile(
    platform_txns: List[PlatformTransaction],
    bank_settlements: List[BankSettlement],
    tolerance: float = ROUNDING_TOLERANCE
) -> ReconciliationResult:
    result = ReconciliationResult()
    eligible = {t.txn_id: t for t in platform_txns if t.status in ("SUCCESS", "REFUND")}

    bank_by_txn: Dict[str, List[BankSettlement]] = defaultdict(list)
    for s in bank_settlements:
        bank_by_txn[s.txn_id].append(s)

    matched_refs = set()

    for txn_id, txn in eligible.items():
        records = bank_by_txn.get(txn_id, [])

        if not records:
            result.unmatched_platform.append({
                "txn_id": txn_id, "merchant_id": txn.merchant_id,
                "platform_amount": txn.amount, "platform_date": str(txn.created_at),
                "issue": "No bank settlement found"
            })
            continue

        if len(records) > 1:
            for r in records:
                matched_refs.add(r.bank_ref)
            result.duplicates.append({
                "txn_id": txn_id, "merchant_id": txn.merchant_id,
                "platform_amount": txn.amount,
                "settlement_count": len(records),
                "bank_refs": ", ".join(r.bank_ref for r in records),
                "total_settled": round(sum(r.settled_amount for r in records), 2),
                "issue": f"Settled {len(records)}x by bank"
            })
            continue

        bank = records[0]
        matched_refs.add(bank.bank_ref)
        diff = round(abs(txn.amount - bank.settled_amount), 4)

        if diff == 0:
            result.matched.append({
                "txn_id": txn_id, "merchant_id": txn.merchant_id,
                "platform_amount": txn.amount, "settled_amount": bank.settled_amount,
                "platform_date": str(txn.created_at),
                "settlement_date": str(bank.settlement_date), "bank_ref": bank.bank_ref
            })
        elif diff <= tolerance:
            result.rounding_differences.append({
                "txn_id": txn_id, "merchant_id": txn.merchant_id,
                "platform_amount": txn.amount, "settled_amount": bank.settled_amount,
                "difference": diff, "bank_ref": bank.bank_ref,
                "issue": f"Rounding diff Rs.{diff}"
            })
        else:
            result.amount_mismatches.append({
                "txn_id": txn_id, "merchant_id": txn.merchant_id,
                "platform_amount": txn.amount, "settled_amount": bank.settled_amount,
                "difference": round(txn.amount - bank.settled_amount, 2),
                "bank_ref": bank.bank_ref,
                "issue": f"Mismatch Rs.{round(txn.amount - bank.settled_amount, 2)}"
            })

    # Phantom bank entries
    phantom_map = {s.bank_ref: s for s in bank_settlements}
    for ref in sorted(set(phantom_map) - matched_refs):
        s = phantom_map[ref]
        result.unmatched_bank.append({
            "bank_ref": s.bank_ref, "txn_id": s.txn_id,
            "settled_amount": s.settled_amount,
            "settlement_date": str(s.settlement_date),
            "issue": "No matching platform transaction"
        })

    return result


# ─────────────────────────────────────────────
#  REPORTING
# ─────────────────────────────────────────────
def print_sep(c="─", w=72): print(c * w)

def print_table(title, rows, cols):
    print(f"\n  {title}  ({len(rows)} record{'s' if len(rows) != 1 else ''})")
    print_sep("·")
    if not rows:
        print("  (none)")
        return
    cw = {c: max(len(c), max(len(str(r.get(c,""))) for r in rows))+2 for c in cols}
    print("  " + "".join(c.ljust(cw[c]) for c in cols))
    print("  " + "".join("-"*cw[c] for c in cols))
    for row in rows:
        print("  " + "".join(str(row.get(c,"")).ljust(cw[c]) for c in cols))

def print_report(result, platform_txns, bank_settlements):
    eligible = [t for t in platform_txns if t.status in ("SUCCESS","REFUND")]
    failed   = [t for t in platform_txns if t.status == "FAILED"]
    plat_amt = round(sum(t.amount for t in eligible), 2)
    bank_amt = round(sum(s.settled_amount for s in bank_settlements
                         if not s.txn_id.startswith("TXN_PHANTOM")), 2)

    print("\n"); print_sep("═")
    print("  PAYMENT RECONCILIATION REPORT  —  June 2024")
    print_sep("═")
    print(f"""
  SUMMARY
  {"─"*45}
  Platform transactions (total)        : {len(platform_txns)}
    Eligible (SUCCESS + REFUND)        : {len(eligible)}
    Failed (excluded from recon)       : {len(failed)}
  Bank settlement records              : {len(bank_settlements)}

  Platform eligible amount             : Rs.{plat_amt:>12,.2f}
  Total bank settled amount            : Rs.{bank_amt:>12,.2f}
  Net difference                       : Rs.{round(plat_amt - bank_amt, 2):>12,.2f}

  RECONCILIATION BREAKDOWN
  {"─"*45}
  Matched (exact)                      : {len(result.matched)}
  Rounding differences (within 0.05)   : {len(result.rounding_differences)}
  Amount mismatches                    : {len(result.amount_mismatches)}
  Unsettled (platform only)            : {len(result.unmatched_platform)}
  Phantom entries (bank only)          : {len(result.unmatched_bank)}
  Duplicate settlements                : {len(result.duplicates)}
""")
    print_table("MATCHED", result.matched,
        ["txn_id","merchant_id","platform_amount","settled_amount","platform_date","settlement_date"])
    print_table("UNSETTLED PLATFORM TRANSACTIONS", result.unmatched_platform,
        ["txn_id","merchant_id","platform_amount","platform_date","issue"])
    print_table("PHANTOM BANK ENTRIES", result.unmatched_bank,
        ["bank_ref","txn_id","settled_amount","settlement_date","issue"])
    print_table("AMOUNT MISMATCHES", result.amount_mismatches,
        ["txn_id","merchant_id","platform_amount","settled_amount","difference","issue"])
    print_table("ROUNDING DIFFERENCES", result.rounding_differences,
        ["txn_id","merchant_id","platform_amount","settled_amount","difference"])
    print_table("DUPLICATE SETTLEMENTS", result.duplicates,
        ["txn_id","merchant_id","platform_amount","settlement_count","total_settled","issue"])
    print("\n"); print_sep("═")
    print("  END OF REPORT"); print_sep("═"); print()


# ─────────────────────────────────────────────
#  TEST CASES
# ─────────────────────────────────────────────
def run_tests():
    print("\n" + "═"*72)
    print("  TEST SUITE")
    print("═"*72)
    passed = failed = 0
    today = date(2024, 6, 15)

    def chk(name, cond, detail=""):
        nonlocal passed, failed
        if cond: print(f"  PASS  {name}"); passed += 1
        else:    print(f"  FAIL  {name}  <- {detail}"); failed += 1

    # T1: perfect match
    r = reconcile(
        [PlatformTransaction("T001","M1",1000.0,"INR","SUCCESS",today)],
        [BankSettlement("B001","T001",1000.0,today+timedelta(1),"SETTLED")])
    chk("T1  Perfect match -> 1 matched, 0 issues",
        len(r.matched)==1 and not r.unmatched_platform and not r.amount_mismatches)

    # T2: missing settlement
    r = reconcile([PlatformTransaction("T002","M1",2000.0,"INR","SUCCESS",today)],[])
    chk("T2  Missing settlement -> 1 unmatched_platform", len(r.unmatched_platform)==1)

    # T3: phantom bank entry
    r = reconcile([],[BankSettlement("B099","T999",5000.0,today,"SETTLED")])
    chk("T3  Phantom bank entry -> 1 unmatched_bank", len(r.unmatched_bank)==1)

    # T4: rounding within tolerance
    r = reconcile(
        [PlatformTransaction("T004","M2",1500.0,"INR","SUCCESS",today)],
        [BankSettlement("B004","T004",1500.03,today+timedelta(1),"SETTLED")])
    chk("T4  Rounding diff 0.03 -> rounding_differences, not mismatch",
        len(r.rounding_differences)==1 and not r.amount_mismatches)

    # T5: real amount mismatch
    r = reconcile(
        [PlatformTransaction("T005","M2",1500.0,"INR","SUCCESS",today)],
        [BankSettlement("B005","T005",1400.0,today+timedelta(1),"SETTLED")])
    chk("T5  Amount mismatch Rs.100 -> amount_mismatches",
        len(r.amount_mismatches)==1 and r.amount_mismatches[0]["difference"]==100.0)

    # T6: duplicate settlement
    r = reconcile(
        [PlatformTransaction("T006","M3",800.0,"INR","SUCCESS",today)],
        [BankSettlement("B006a","T006",800.0,today+timedelta(1),"SETTLED"),
         BankSettlement("B006b","T006",800.0,today+timedelta(2),"SETTLED")])
    chk("T6  Duplicate settlement -> 1 duplicate, 0 matched",
        len(r.duplicates)==1 and r.duplicates[0]["settlement_count"]==2)

    # T7: FAILED txn excluded
    r = reconcile([PlatformTransaction("T007","M1",3000.0,"INR","FAILED",today)],[])
    chk("T7  FAILED txn excluded from reconciliation",
        not r.unmatched_platform and not r.matched)

    # T8: refund (negative)
    r = reconcile(
        [PlatformTransaction("T008","M4",-500.0,"INR","REFUND",today)],
        [BankSettlement("B008","T008",-500.0,today+timedelta(1),"SETTLED")])
    chk("T8  Refund (negative amount) matches correctly", len(r.matched)==1)

    # T9: mixed scenario
    p9 = [
        PlatformTransaction("TA01","M1",1000.0,"INR","SUCCESS",today),
        PlatformTransaction("TA02","M1",2000.0,"INR","SUCCESS",today),  # unsettled
        PlatformTransaction("TA03","M2",3000.0,"INR","SUCCESS",today),  # mismatch
        PlatformTransaction("TA04","M3",4000.0,"INR","FAILED",today),   # excluded
    ]
    b9 = [
        BankSettlement("BA01","TA01",1000.0,today+timedelta(1),"SETTLED"),
        BankSettlement("BA03","TA03",2900.0,today+timedelta(1),"SETTLED"),
        BankSettlement("BPHANT","TXPHANT",999.0,today+timedelta(2),"SETTLED"),
    ]
    r = reconcile(p9, b9)
    chk("T9  Mixed: 1 match + 1 unsettled + 1 mismatch + 1 phantom",
        len(r.matched)==1 and len(r.unmatched_platform)==1 and
        len(r.amount_mismatches)==1 and len(r.unmatched_bank)==1)

    print(f"\n  {passed} passed, {failed} failed  ({passed+failed} total)")
    print("═"*72)
    return failed == 0


# ─────────────────────────────────────────────
#  LIMITATIONS
# ─────────────────────────────────────────────
LIMITATIONS = """
LIMITATIONS IN A REAL PRODUCTION SYSTEM
────────────────────────────────────────
1. SCALABILITY         — In-memory processing won't scale to millions of rows.
                         Production needs DB-backed matching, chunked I/O,
                         and parallel workers.

2. REAL-TIME vs BATCH  — This is end-of-month batch recon. Production systems
                         need intraday or near-real-time reconciliation with
                         event streaming (e.g. Kafka).

3. PARTIAL SETTLEMENTS — A single platform transaction may map to multiple
                         bank entries (split settlements). This engine assumes
                         a strict 1:1 match.

4. MULTI-CURRENCY      — FX rate snapshots are needed for cross-currency
                         reconciliation. Not handled here.

5. TIMEZONE HANDLING   — Timestamps (not just dates) matter. Settlement
                         cutoffs vary by bank and timezone.

6. CHARGEBACKS         — Bank-initiated reversals and chargebacks require
                         separate matching flows beyond amount comparison.

7. DATA FORMAT / EDI   — Real bank files arrive in MT940, BAI2, or SWIFT
                         formats. Parsing them is a significant extra step.

8. IDEMPOTENCY         — Re-running on partially processed data can produce
                         false duplicates. Production systems need state
                         tracking and idempotency keys.
"""


# ─────────────────────────────────────────────
#  MAIN
# ─────────────────────────────────────────────
def main():
    print("\n" + "═"*72)
    print("  STEP 1  Generating sample data")
    print("═"*72)
    txns = generate_platform_transactions(30)
    settlements = generate_bank_settlements(txns)
    eligible = [t for t in txns if t.status in ("SUCCESS","REFUND")]
    failed   = [t for t in txns if t.status == "FAILED"]
    print(f"  Platform transactions   : {len(txns)}"
          f"  (eligible: {len(eligible)}, failed: {len(failed)})")
    print(f"  Bank settlement records : {len(settlements)}")

    print("\n" + "═"*72)
    print("  STEP 2  Running reconciliation")
    print("═"*72)
    result = reconcile(txns, settlements)

    print("\n" + "═"*72)
    print("  STEP 3  Report")
    print("═"*72)
    print_report(result, txns, settlements)

    print("═"*72)
    print("  STEP 4  Test suite")
    print("═"*72)
    run_tests()

    print(LIMITATIONS)

if __name__ == "__main__":
    main()
