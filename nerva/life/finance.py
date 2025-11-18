"""Personal finance + life management stubs."""
from __future__ import annotations

import csv
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional


@dataclass
class BudgetEntry:
    category: str
    amount: float
    date: str = field(default_factory=lambda: datetime.utcnow().date().isoformat())
    description: Optional[str] = None


class FinanceLedger:
    """
    Lightweight CSV-backed ledger for expenses/income/SaaS tracking.
    """

    def __init__(self, csv_path: Optional[Path] = None) -> None:
        self.csv_path = csv_path or Path.home() / ".nerva" / "finance.csv"
        self.csv_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.csv_path.exists():
            self.csv_path.write_text("date,category,amount,description\n")

    def add_entry(self, entry: BudgetEntry) -> None:
        with self.csv_path.open("a", newline="") as fp:
            writer = csv.writer(fp)
            writer.writerow([entry.date, entry.category, entry.amount, entry.description or ""])

    def summarize(self) -> Dict[str, float]:
        summaries: Dict[str, float] = {}
        with self.csv_path.open() as fp:
            reader = csv.DictReader(fp)
            for row in reader:
                category = row["category"]
                amount = float(row["amount"])
                summaries[category] = summaries.get(category, 0.0) + amount
        return summaries

    def export(self) -> List[BudgetEntry]:
        entries: List[BudgetEntry] = []
        with self.csv_path.open() as fp:
            reader = csv.DictReader(fp)
            for row in reader:
                entries.append(
                    BudgetEntry(
                        category=row["category"],
                        amount=float(row["amount"]),
                        date=row["date"],
                        description=row.get("description") or None,
                    )
                )
        return entries
