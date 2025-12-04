# Budget Tracker (PyQt6)

A desktop budget tracking application built with Python and PyQt6.  
It helps you manage budget periods, track income and expenses, and keep an eye on pending (uncertain) transactions — all with a clean, table-based UI.

---

## Features

- **Budget Periods**
  - Create, edit, and delete budget periods.
  - See start/end dates, total income, total outgoing, net value, and pending count per period.
  - Filter periods by name or show only periods that are active “today”.
  - Detailed view of a selected period, including attached income and outgoing transactions.

- **Transactions**
  - Global view of all transactions (income & outgoing).
  - Double-click to edit transactions via a dialog.
  - Filter by:
    - Type (Income / Outgoing / All)
    - Status (Certain / Pending / All)
    - Attachment (Attached to a period / Unattached / All)
    - Date range
    - Text search on description & category
  - Delete selected transactions.
  - Automatic summary of visible transactions (count, visible income, visible outgoing).

- **Pending Transactions**
  - Dedicated page for **pending** incomes and outgoings.
  - Separate tabs for pending incomes and pending outgoings.
  - Filter by date range, attachment state, and search text.
  - Mark selected pending transactions as **certain**.
  - Delete selected pending transactions.

- **Consistent Data Refresh**
  - All pages reload data from the backend when:
    - The application starts.
    - You switch pages using the left navigation.
    - You create new periods or transactions via the toolbar.

---

## Tech Stack

- **Language:** Python 3.11+ (3.10+ should also work)
- **GUI Toolkit:** [PyQt6](https://pypi.org/project/PyQt6/)
- **Architecture:**
  - Domain layer: `BudgetPeriod`, `Transaction` dataclasses.
  - Service layer: `BudgetService` abstraction (you implement storage/persistence).
  - UI layer: `QAbstractTableModel` models + Qt widgets and pages.

---

## Project Structure

A typical layout for this project looks like:

```text
.
├─ domain.py          # BudgetPeriod, Transaction dataclasses
├─ service.py         # BudgetService interface + your implementation
├─ UI.py              # MainWindow, pages, dialogs, table models, filters (the large file you see here)
├─ APP.py            # App entry point that wires the service into the UI

