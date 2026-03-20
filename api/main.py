from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, date
from uuid import uuid4
from enum import Enum
import math

app = FastAPI(title="Transaction Reconciliation API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Enums & Models ──────────────────────────────────────────────────────────

class TxStatus(str, Enum):
    PENDING    = "pending"
    MATCHED    = "matched"
    UNMATCHED  = "unmatched"
    DUPLICATE  = "duplicate"
    EXCEPTION  = "exception"

class TxSource(str, Enum):
    BANK       = "bank"
    INTERNAL   = "internal"

class Transaction(BaseModel):
    id: str
    date: str
    description: str
    amount: float
    currency: str = "INR"
    reference: Optional[str] = None
    source: TxSource
    status: TxStatus = TxStatus.PENDING
    matched_id: Optional[str] = None
    category: Optional[str] = None
    note: Optional[str] = None
    created_at: str

class TransactionInput(BaseModel):
    date: str
    description: str
    amount: float
    currency: str = "INR"
    reference: Optional[str] = None
    source: TxSource
    category: Optional[str] = None
    note: Optional[str] = None
    reference: Optional[str] = None
    source: TxSource
    category: Optional[str] = None
    note: Optional[str] = None

class LedgerEntry(BaseModel):
    id: str
    date: str
    description: str
    debit: Optional[float] = None
    credit: Optional[float] = None
    balance: float
    status: TxStatus
    reference: Optional[str] = None
    category: Optional[str] = None
    matched_id: Optional[str] = None

class ReconcileResponse(BaseModel):
    matched: int
    unmatched: int
    duplicates: int
    exceptions: int
    details: List[dict]

# ── In-Memory Store ─────────────────────────────────────────────────────────

transactions: List[Transaction] = []

def seed_data():
    """Seed realistic demo transactions."""
    raw = [
        # Bank-side
        ("2025-01-03", "NEFT/AIRTEL BROADBAND/REF8821", -1499.00, "bank", "REF8821", "Utilities"),
        ("2025-01-05", "UPI/ZOMATO ORDER/TXN7734",     -645.00,  "bank", "TXN7734", "Food"),
        ("2025-01-07", "SALARY CREDIT/ACME CORP",      85000.00, "bank", "SAL001",  "Income"),
        ("2025-01-09", "ATM WDL/CONNAUGHT PLACE",      -5000.00, "bank", None,      "Cash"),
        ("2025-01-11", "NEFT/LIC PREMIUM/POL9921",     -12500.00,"bank", "POL9921", "Insurance"),
        ("2025-01-14", "UPI/SWIGGY/TXN2291",           -380.00,  "bank", "TXN2291", "Food"),
        ("2025-01-15", "IMPS/RENT/LANDLORD",           -22000.00,"bank", "RENT01",  "Housing"),
        ("2025-01-18", "UPI/PAYTM WALLET/TOP3391",     -2000.00, "bank", "TOP3391", "Wallet"),
        ("2025-01-20", "NEFT/FREELANCE CLIENT A",       35000.00,"bank", "FREQ01",  "Income"),
        ("2025-01-22", "UPI/AMAZON/ORD998811",         -3299.00, "bank", "ORD9988", "Shopping"),
        # Internal-side (should match most bank entries)
        ("2025-01-03", "Airtel Broadband Bill",        -1499.00, "internal", "REF8821", "Utilities"),
        ("2025-01-05", "Zomato Food Order",            -645.00,  "internal", "TXN7734", "Food"),
        ("2025-01-07", "Acme Corp Salary",              85000.00,"internal", "SAL001",  "Income"),
        ("2025-01-11", "LIC Premium Payment",          -12500.00,"internal", "POL9921", "Insurance"),
        ("2025-01-14", "Swiggy Food Order",            -380.00,  "internal", "TXN2291", "Food"),
        ("2025-01-15", "Monthly Rent",                 -22000.00,"internal", "RENT01",  "Housing"),
        ("2025-01-20", "Freelance Invoice A",           35000.00,"internal", "FREQ01",  "Income"),
        ("2025-01-22", "Amazon Purchase",              -3299.00, "internal", "ORD9988", "Shopping"),
        # Unmatched / exception cases
        ("2025-01-25", "MYSTERY DEBIT/REF0099",        -750.00,  "bank", "REF0099", None),
        ("2025-01-28", "Gym Membership",               -1800.00, "internal", "GYM001", "Health"),
    ]
    for (dt, desc, amt, src, ref, cat) in raw:
        tx = Transaction(
            id=str(uuid4()),
            date=dt,
            description=desc,
            amount=amt,
            source=TxSource(src),
            reference=ref,
            category=cat,
            created_at=datetime.utcnow().isoformat(),
            status=TxStatus.PENDING,
        )
        transactions.append(tx)

seed_data()

# ── Reconciliation Engine ────────────────────────────────────────────────────

def run_reconciliation() -> ReconcileResponse:
    """
    Match bank ↔ internal transactions by:
    1. Exact reference match
    2. Amount + date proximity (±2 days)
    3. Flag duplicates (same ref used twice)
    4. Mark rest as unmatched / exception
    """
    # Reset statuses
    for tx in transactions:
        tx.status = TxStatus.PENDING
        tx.matched_id = None

    bank_txs     = [t for t in transactions if t.source == TxSource.BANK]
    internal_txs = [t for t in transactions if t.source == TxSource.INTERNAL]

    used_internal = set()
    used_bank     = set()
    details       = []
    ref_seen      = {}

    # Pass 1 — exact reference match
    for btx in bank_txs:
        if not btx.reference:
            continue
        if btx.reference in ref_seen:
            btx.status = TxStatus.DUPLICATE
            details.append({"id": btx.id, "rule": "duplicate_ref", "ref": btx.reference})
            continue
        ref_seen[btx.reference] = btx.id
        for itx in internal_txs:
            if itx.id in used_internal:
                continue
            if itx.reference == btx.reference and math.isclose(itx.amount, btx.amount, rel_tol=0.001):
                btx.status  = TxStatus.MATCHED
                itx.status  = TxStatus.MATCHED
                btx.matched_id = itx.id
                itx.matched_id = btx.id
                used_internal.add(itx.id)
                used_bank.add(btx.id)
                details.append({"id": btx.id, "matched": itx.id, "rule": "exact_ref"})
                break

    # Pass 2 — amount + date fuzzy match
    for btx in bank_txs:
        if btx.id in used_bank:
            continue
        bdate = datetime.strptime(btx.date, "%Y-%m-%d")
        for itx in internal_txs:
            if itx.id in used_internal:
                continue
            idate = datetime.strptime(itx.date, "%Y-%m-%d")
            if math.isclose(itx.amount, btx.amount, rel_tol=0.001) and abs((bdate - idate).days) <= 2:
                btx.status  = TxStatus.MATCHED
                itx.status  = TxStatus.MATCHED
                btx.matched_id = itx.id
                itx.matched_id = btx.id
                used_internal.add(itx.id)
                used_bank.add(btx.id)
                details.append({"id": btx.id, "matched": itx.id, "rule": "fuzzy_amount_date"})
                break

    # Pass 3 — flag unmatched
    for tx in transactions:
        if tx.status == TxStatus.PENDING:
            tx.status = TxStatus.UNMATCHED if tx.reference else TxStatus.EXCEPTION

    matched   = sum(1 for t in transactions if t.status == TxStatus.MATCHED)
    unmatched = sum(1 for t in transactions if t.status == TxStatus.UNMATCHED)
    dupes     = sum(1 for t in transactions if t.status == TxStatus.DUPLICATE)
    exc       = sum(1 for t in transactions if t.status == TxStatus.EXCEPTION)

    return ReconcileResponse(matched=matched, unmatched=unmatched, duplicates=dupes, exceptions=exc, details=details)


# ── Ledger Builder ───────────────────────────────────────────────────────────

def build_ledger(source: TxSource = TxSource.BANK) -> List[LedgerEntry]:
    txs = sorted([t for t in transactions if t.source == source], key=lambda x: x.date)
    entries, balance = [], 0.0
    for tx in txs:
        balance += tx.amount
        entries.append(LedgerEntry(
            id=tx.id,
            date=tx.date,
            description=tx.description,
            debit=abs(tx.amount) if tx.amount < 0 else None,
            credit=tx.amount if tx.amount > 0 else None,
            balance=round(balance, 2),
            status=tx.status,
            reference=tx.reference,
            category=tx.category,
            matched_id=tx.matched_id,
        ))
    return entries


# ── Routes ───────────────────────────────────────────────────────────────────

@app.get("/")
def root():
    return {"service": "Transaction Reconciliation API", "version": "1.0.0", "docs": "/docs"}

@app.get("/transactions", response_model=List[Transaction])
def list_transactions(source: Optional[TxSource] = None, status: Optional[TxStatus] = None):
    result = transactions
    if source: result = [t for t in result if t.source == source]
    if status: result = [t for t in result if t.status == status]
    return result

@app.post("/transactions", response_model=Transaction)
def add_transaction(data: TransactionInput):
    tx = Transaction(
        id=str(uuid4()),
        date=data.date,
        description=data.description,
        amount=data.amount,
        currency=data.currency,
        reference=data.reference,
        source=data.source,
        category=data.category,
        note=data.note,
        created_at=datetime.utcnow().isoformat(),
        status=TxStatus.PENDING,
    )
    transactions.append(tx)
    return tx

@app.post("/reconcile", response_model=ReconcileResponse)
def reconcile():
    return run_reconciliation()

@app.get("/ledger", response_model=List[LedgerEntry])
def get_ledger(source: TxSource = TxSource.BANK):
    return build_ledger(source)

@app.get("/summary")
def summary():
    bank_total     = sum(t.amount for t in transactions if t.source == TxSource.BANK)
    internal_total = sum(t.amount for t in transactions if t.source == TxSource.INTERNAL)
    by_status      = {}
    for s in TxStatus:
        by_status[s.value] = sum(1 for t in transactions if t.status == s)
    by_category = {}
    for t in transactions:
        if t.category:
            by_category.setdefault(t.category, {"count": 0, "total": 0.0})
            by_category[t.category]["count"] += 1
            by_category[t.category]["total"] = round(by_category[t.category]["total"] + t.amount, 2)
    return {
        "total_transactions": len(transactions),
        "bank_balance": round(bank_total, 2),
        "internal_balance": round(internal_total, 2),
        "variance": round(bank_total - internal_total, 2),
        "by_status": by_status,
        "by_category": by_category,
    }

@app.delete("/transactions/{tx_id}")
def delete_transaction(tx_id: str):
    global transactions
    before = len(transactions)
    transactions = [t for t in transactions if t.id != tx_id]
    if len(transactions) == before:
        raise HTTPException(404, "Transaction not found")
    return {"deleted": tx_id}

@app.post("/reset")
def reset():
    global transactions
    transactions = []
    seed_data()
    return {"message": "Store reset to demo data"}
