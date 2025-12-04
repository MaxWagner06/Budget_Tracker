from dataclasses import asdict
import json
import random
from domain import BudgetPeriod, Transaction
from datetime import date


# ---------- helpers for date handling ----------

def _encode_dates(d: dict) -> dict:
    """Convert any datetime.date values in a dict to ISO strings."""
    for k, v in d.items():
        if isinstance(v, date):
            d[k] = v.isoformat()
    return d


def _decode_dates(d: dict) -> dict:
    """Convert ISO date strings in a dict back to datetime.date where possible."""
    for k, v in d.items():
        if isinstance(v, str):
            try:
                d[k] = date.fromisoformat(v)
            except ValueError:
                # not a date string, leave as-is
                pass
    return d


# ---------- periods ----------

def save_periods_to_json(periods: list[BudgetPeriod], filename: str) -> None:
    data = []
    for p in periods:
        d = asdict(p)
        d = _encode_dates(d)  # handle any date fields in BudgetPeriod
        data.append(d)

    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


def load_periods_from_json(filename = "Periods.json") -> list[BudgetPeriod]:
    with open(filename, "r", encoding="utf-8") as f:
        data = json.load(f)  # json.load, not json.loads(f)

    return [BudgetPeriod(**_decode_dates(item)) for item in data]


# ---------- transactions ----------

def save_transactions_to_json(transactions: list[Transaction], filename: str) -> None:
    data = []
    for t in transactions:
        d = asdict(t)
        d = _encode_dates(d)  # handle any date fields in Transaction (e.g. "date")
        data.append(d)

    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


def load_transactions_from_json(filename = "Transactions.json") -> list[Transaction]:
    with open(filename, "r", encoding="utf-8") as f:
        data = json.load(f)

    result: list[Transaction] = []
    for item in data:
        item = _decode_dates(item)  # convert date strings back to date objects
        result.append(Transaction(**item))
    return result


# ---------- combined API ----------

def Save(
    periods: list[BudgetPeriod],
    transactions: list[Transaction],
    Pfilename: str = "Periods.json",
    Tfilename: str = "Transactions.json",
) -> None:
    save_periods_to_json(periods, Pfilename)
    save_transactions_to_json(transactions, Tfilename)




class BudgetService:
    def __init__(self, periods: list[BudgetPeriod], txs: list[Transaction]):
        self.periods = periods
        self.txs = txs
    
    def save_data(self):
        Save(self.periods,self.txs)
    
    #GETTERS    
    def get_periods(self) -> list[BudgetPeriod]:
        return self.periods
    def get_transactions(self) -> list[Transaction]:
        return self.txs
    
    #PERIOD CRUD
    def create_period(self, data : dict):
        while True:
            new_id = random.randint(10000,99999)
            is_ok = True
            for p in self.periods:
                if p.id == new_id:
                    is_ok = False
                    break
            if is_ok:
                break
        new_period = BudgetPeriod(new_id, data["name"], data["start_date"], data["end_date"], data["notes"])
        self.periods.append(new_period)
        self.period_attachment_calculate(new_period)
        self.save_data()


    def update_period(self, data: dict, period: BudgetPeriod):
        u_period = next((p for p in self.periods if p.id == period.id), None)
        index = self.periods.index(u_period)
        u_period.name = data["name"]
        u_period.start_date = data["start_date"]
        u_period.end_date = data["end_date"]
        u_period.notes = data["notes"]
        self.periods[index] = u_period
        self.period_attachment_calculate(u_period)
        self.save_data()


    def delete_period(self, period: BudgetPeriod):
        d_period = next((p for p in self.periods if p.id == period.id), None)
        self.periods.remove(d_period)
        self.save_data()


    #TRANSACTIONS CRUD
    def create_tx(self, data: dict):
        while True:
            new_id = random.randint(10000,99999)
            is_ok = True
            for p in self.periods:
                if p.id == new_id:
                    is_ok = False
                    break
            if is_ok:
                break
        new_tx = Transaction(new_id, data["type"], data["date"], data["status"], data["description"], data["amount"], data["category"], data["linked_period_id"])
        new_tx = self.tx_attachment_checker(new_tx)
        self.txs.append(new_tx)
        self.save_data()


    def update_tx(self, data: dict, tx: Transaction):
        u_tx = next((t for t in self.txs if t.id == tx.id), None)
        index = self.txs.index(u_tx)
        u_tx.type = data["type"]
        u_tx.date = data["date"]
        u_tx.status = data["status"]
        u_tx.description = data["description"]
        u_tx.amount = data["amount"]
        u_tx.category = data["category"]
        u_tx.linked_period_id = data["linked_period_id"]
        u_tx = self.tx_attachment_checker(u_tx)
        self.txs[index] = u_tx
        self.save_data()


    def delete_tx(self, ids: list[int]):
        for id in ids:
            d_tx = next((t for t in self.txs if t.id == id), None)
            self.txs.remove(d_tx)
        self.save_data()

    #PENDING TRANSACTION PROCESSES
    def mark_certain(self, pendings: list[Transaction]):
        for tx in pendings:
            m_tx = next((t for t in self.txs if tx.id == t.id), None)
            index = self.txs.index(m_tx)
            m_tx.status = "certain"
            self.txs[index] = m_tx
        self.save_data()
    
    def delete_pending(self, pendings: list[Transaction]):
        ids = []
        for tx in pendings:
            ids.append(tx.id)
        self.delete_tx(ids)

    #GENERAL ATTACHMENT CHECKER
    def recalculate_attachments(self):
        new_txs = []
        for tx in self.txs:
            td = tx.date
            for p in self.periods:
                sd = p.start_date
                ed = p.end_date
                if sd < td and td < ed:
                    tx.linked_period_id = p.id
                    break
            new_txs.append(tx)
        self.txs = new_txs
        self.save_data()



    #HELPER ATTACHMENT CHECKERS
    def period_attachment_calculate(self, period: BudgetPeriod):
        sd = period.start_date
        ed = period.end_date
        new_txs = []
        for tx in self.txs:
            if sd < tx.date and tx.date < ed:
                tx.linked_period_id = period.id
            new_txs.append(tx)
        self.txs = new_txs
        self.save_data()

    def tx_attachment_checker(self, tx: Transaction) -> Transaction:
        d = tx.date
        for p in self.periods:
            if p.start_date < d and d < p.end_date:
                tx.linked_period_id = p.id
        return tx
