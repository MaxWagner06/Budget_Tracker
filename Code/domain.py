from dataclasses import dataclass
from datetime import date
from typing import Optional, List, Callable

@dataclass
class BudgetPeriod:
    id: int
    name: str 
    start_date: date
    end_date: date
    notes: str = ""

@dataclass
class Transaction:
    id: int
    type: str         
    date: date
    status: str     
    description: str
    amount: float
    category: str = ""
    linked_period_id: Optional[int] = None  
   