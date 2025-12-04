from __future__ import annotations

import sys
from domain import Transaction, BudgetPeriod
from service import BudgetService
from dataclasses import dataclass
from datetime import date
from typing import Optional, List, Callable


from PyQt6.QtCore import (
    Qt,
    QSize,
    QAbstractTableModel,
    QModelIndex,
    QSortFilterProxyModel,
)
from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QStackedWidget,
    QListWidget,
    QListWidgetItem,
    QToolBar,
    QStatusBar,
    QTableView,
    QLineEdit,
    QLabel,
    QPushButton,
    QComboBox,
    QDateEdit,
    QGroupBox,
    QGridLayout,
    QTabWidget,
    QPlainTextEdit,
    QDoubleSpinBox,
    QDialog,
    QDialogButtonBox,
    QAbstractItemView,
)


# ---------------------------------------------------------------------------
# Table models (UI models, NO backend logic)
# ---------------------------------------------------------------------------

class BudgetPeriodTableModel(QAbstractTableModel):
    """
    Table model for budget periods.

    You must feed data from your backend by calling:
        set_periods(periods: List[BudgetPeriod])
        set_transactions(transactions: List[Transaction])

    Columns:
        0 Name
        1 Start
        2 End
        3 Income (computed from transactions)
        4 Outgoing (computed from transactions)
        5 Net
        6 Pending count
    """

    COL_NAME = 0
    COL_START = 1
    COL_END = 2
    COL_INC = 3
    COL_OUT = 4
    COL_NET = 5
    COL_PENDING = 6

    def __init__(
        self,
        periods: Optional[List[BudgetPeriod]] = None,
        transactions: Optional[List[Transaction]] = None,
    ):
        super().__init__()
        self._periods: List[BudgetPeriod] = periods or []
        self._transactions: List[Transaction] = transactions or []

    # --------- backend integration API ---------

    def set_periods(self, periods: List[BudgetPeriod]):
        """Replace the list of periods from backend."""
        self.beginResetModel()
        self._periods = periods
        self.endResetModel()

    def set_transactions(self, transactions: List[Transaction]):
        """
        Provide the current list of all transactions from backend so that
        totals per period can be computed.
        """
        self._transactions = transactions
        self.layoutChanged.emit()

    @property
    def periods(self) -> List[BudgetPeriod]:
        return self._periods

    @property
    def transactions(self) -> List[Transaction]:
        return self._transactions

    # --------- model implementation ---------

    def rowCount(self, parent=QModelIndex()) -> int:
        return len(self._periods)

    def columnCount(self, parent=QModelIndex()) -> int:
        return 7

    def headerData(self, section: int, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if orientation == Qt.Orientation.Horizontal:
            headers = [
                "Name",
                "Start",
                "End",
                "Income",
                "Outgoing",
                "Net",
                "Pending",
            ]
            if 0 <= section < len(headers):
                return headers[section]
        return None

    def data(self, index: QModelIndex, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        row = index.row()
        col = index.column()
        if row < 0 or row >= len(self._periods):
            return None
        period = self._periods[row]

        if role == Qt.ItemDataRole.DisplayRole:
            if col == self.COL_NAME:
                return period.name
            elif col == self.COL_START:
                return period.start_date.isoformat()
            elif col == self.COL_END:
                return period.end_date.isoformat()
            else:
                inc, out, pending_count = self._compute_totals(period)
                if col == self.COL_INC:
                    return f"{inc:.2f}"
                elif col == self.COL_OUT:
                    return f"{out:.2f}"
                elif col == self.COL_NET:
                    return f"{(inc - out):.2f}"
                elif col == self.COL_PENDING:
                    return pending_count
        elif role == Qt.ItemDataRole.UserRole:
            # Underlying BudgetPeriod object
            return period
        return None

    def _compute_totals(self, period: BudgetPeriod):
        inc = 0.0
        out = 0.0
        pending_count = 0
        for tx in self._transactions:
            if tx.linked_period_id == period.id:
                if tx.status == "pending":
                    pending_count += 1
                if tx.status != "certain":
                    continue
                if tx.type == "income":
                    inc += tx.amount
                elif tx.type == "outgoing":
                    out += tx.amount
        return inc, out, pending_count

    def refresh(self):
        """Call to force a UI refresh if backend changed period objects in place."""
        self.layoutChanged.emit()


class TransactionTableModel(QAbstractTableModel):
    """
    Table model for transactions.

    You must feed data from your backend by calling:
        set_transactions(transactions: List[Transaction])

    Optionally you can provide a period resolver callback so the model
    can show period names for each transaction:

        set_period_resolver(lambda pid: BudgetPeriod | None)
    """

    COL_STATUS = 0
    COL_TYPE = 1
    COL_DATE = 2
    COL_DESC = 3
    COL_AMOUNT = 4
    COL_CAT = 5
    COL_PERIOD = 6

    def __init__(
        self,
        transactions: Optional[List[Transaction]] = None,
        period_resolver: Optional[Callable[[Optional[int]], Optional[BudgetPeriod]]] = None,
    ):
        super().__init__()
        self._transactions: List[Transaction] = transactions or []
        self._period_resolver = period_resolver

    # --------- backend integration API ---------

    def set_transactions(self, transactions: List[Transaction]):
        """Replace the list of transactions from backend."""
        self.beginResetModel()
        self._transactions = transactions
        self.endResetModel()

    def set_period_resolver(
        self,
        resolver: Optional[Callable[[Optional[int]], Optional[BudgetPeriod]]],
    ):
        """
        Provide a function that takes linked_period_id and returns a BudgetPeriod
        (or None). E.g. backend can pass a lookup function.
        """
        self._period_resolver = resolver
        self.layoutChanged.emit()

    @property
    def transactions(self) -> List[Transaction]:
        return self._transactions

    # --------- model implementation ---------

    def rowCount(self, parent=QModelIndex()) -> int:
        return len(self._transactions)

    def columnCount(self, parent=QModelIndex()) -> int:
        return 7

    def headerData(self, section: int, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if orientation == Qt.Orientation.Horizontal:
            headers = [
                "Status",
                "Type",
                "Date",
                "Description",
                "Amount",
                "Category",
                "Budget Period",
            ]
            if 0 <= section < len(headers):
                return headers[section]
        return None

    def data(self, index: QModelIndex, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        row = index.row()
        col = index.column()
        if row < 0 or row >= len(self._transactions):
            return None
        tx = self._transactions[row]

        if role == Qt.ItemDataRole.DisplayRole:
            if col == self.COL_STATUS:
                return tx.status.capitalize()
            elif col == self.COL_TYPE:
                return tx.type.capitalize()
            elif col == self.COL_DATE:
                return tx.date.isoformat()
            elif col == self.COL_DESC:
                return tx.description
            elif col == self.COL_AMOUNT:
                return f"{tx.amount:.2f}"
            elif col == self.COL_CAT:
                return tx.category
            elif col == self.COL_PERIOD:
                if tx.linked_period_id is None or self._period_resolver is None:
                    return "—"
                period = self._period_resolver(tx.linked_period_id)
                return period.name if period else "—"
        elif role == Qt.ItemDataRole.UserRole:
            # Underlying Transaction object
            return tx
        return None

    def refresh(self):
        """Call to force a UI refresh if backend changed transaction objects in place."""
        self.layoutChanged.emit()


# ---------------------------------------------------------------------------
# Filter proxy models (pure UI logic)
# ---------------------------------------------------------------------------

class BudgetPeriodFilterProxyModel(QSortFilterProxyModel):
    """
    Filters periods by name and optionally only those 'active today'.

    Uses BudgetPeriodTableModel as source, reading UserRole for objects.
    """

    def __init__(self):
        super().__init__()
        self._name_filter = ""
        self._active_only = False

    def set_name_filter(self, text: str):
        self._name_filter = text.lower()
        self.invalidateFilter()

    def set_active_only(self, active_only: bool):
        self._active_only = active_only
        self.invalidateFilter()

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:
        model: BudgetPeriodTableModel = self.sourceModel()  # type: ignore
        idx = model.index(source_row, 0, source_parent)
        period: BudgetPeriod = model.data(idx, Qt.ItemDataRole.UserRole)
        if period is None:
            return False

        if self._name_filter:
            if self._name_filter not in period.name.lower():
                return False

        if self._active_only:
            today = date.today()
            if not (period.start_date <= today <= period.end_date):
                return False

        return True


class TransactionsFilterProxyModel(QSortFilterProxyModel):
    """
    Global filter for transactions. All filtering/search logic lives here,
    independent from backend.
    """

    def __init__(self):
        super().__init__()
        self.type_filter = "all"          # 'all', 'income', 'outgoing'
        self.status_filter = "all"        # 'all', 'certain', 'pending'
        self.attachment_filter = "all"    # 'all', 'attached', 'unattached'
        self.date_from: Optional[date] = None
        self.date_to: Optional[date] = None
        self.search_text: str = ""
        self.linked_period_id: Optional[int] = None  # when used for attached list

    # --------- filter configuration ---------

    def set_type_filter(self, value: str):
        self.type_filter = value
        self.invalidateFilter()

    def set_status_filter(self, value: str):
        self.status_filter = value
        self.invalidateFilter()

    def set_attachment_filter(self, value: str):
        self.attachment_filter = value
        self.invalidateFilter()

    def set_date_from(self, d: Optional[date]):
        self.date_from = d
        self.invalidateFilter()

    def set_date_to(self, d: Optional[date]):
        self.date_to = d
        self.invalidateFilter()

    def set_search_text(self, text: str):
        self.search_text = text.lower()
        self.invalidateFilter()

    def set_linked_period_id(self, pid: Optional[int]):
        self.linked_period_id = pid
        self.invalidateFilter()

    # --------- filter logic ---------

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:
        model: TransactionTableModel = self.sourceModel()  # type: ignore
        idx = model.index(source_row, 0, source_parent)
        tx: Transaction = model.data(idx, Qt.ItemDataRole.UserRole)
        if tx is None:
            return False

        if self.type_filter in ("income", "outgoing") and tx.type != self.type_filter:
            return False

        if self.status_filter in ("pending", "certain") and tx.status != self.status_filter:
            return False

        if self.attachment_filter == "attached" and tx.linked_period_id is None:
            return False
        if self.attachment_filter == "unattached" and tx.linked_period_id is not None:
            return False

        if self.linked_period_id is not None and tx.linked_period_id != self.linked_period_id:
            return False

        if self.date_from is not None and tx.date < self.date_from:
            return False
        if self.date_to is not None and tx.date > self.date_to:
            return False

        if self.search_text:
            text = f"{tx.description} {tx.category}".lower()
            if self.search_text not in text:
                return False

        return True

    def visible_totals(self):
        """
        Compute totals (certain only) for currently visible rows.

        Returns (count, income_total, outgoing_total)
        """
        count = 0
        inc = 0.0
        out = 0.0
        model: TransactionTableModel = self.sourceModel()  # type: ignore
        for row in range(self.rowCount()):
            idx = self.index(row, 0)
            tx: Transaction = self.data(idx, Qt.ItemDataRole.UserRole)
            if tx is None:
                continue
            count += 1
            if tx.status != "certain":
                continue
            if tx.type == "income":
                inc += tx.amount
            elif tx.type == "outgoing":
                out += tx.amount
        return count, inc, out

    def data(self, index: QModelIndex, role=Qt.ItemDataRole.DisplayRole):
        return super().data(index, role)


# ---------------------------------------------------------------------------
# Dialogs (UI only)
# ---------------------------------------------------------------------------

class PeriodDialog(QDialog):
    """
    Dialog to create or edit a budget period.

    Use get_period_data() to fetch:
        {
            "name": str,
            "start_date": date,
            "end_date": date,
            "notes": str,
        }
    """

    def __init__(self, parent: Optional[QWidget] = None, period: Optional[BudgetPeriod] = None):
        super().__init__(parent)
        self.setWindowTitle("Budget Period")
        self.setMinimumWidth(400)
        self._period = period

        from PyQt6.QtCore import QDate

        main_layout = QVBoxLayout(self)
        form_layout = QGridLayout()

        self.name_edit = QLineEdit()
        self.start_date_edit = QDateEdit()
        self.start_date_edit.setCalendarPopup(True)
        self.end_date_edit = QDateEdit()
        self.end_date_edit.setCalendarPopup(True)
        self.notes_edit = QPlainTextEdit()

        row = 0
        form_layout.addWidget(QLabel("Name:"), row, 0)
        form_layout.addWidget(self.name_edit, row, 1)
        row += 1

        form_layout.addWidget(QLabel("Start date:"), row, 0)
        form_layout.addWidget(self.start_date_edit, row, 1)
        row += 1

        form_layout.addWidget(QLabel("End date:"), row, 0)
        form_layout.addWidget(self.end_date_edit, row, 1)
        row += 1

        form_layout.addWidget(QLabel("Notes:"), row, 0)
        form_layout.addWidget(self.notes_edit, row, 1)
        row += 1

        main_layout.addLayout(form_layout)

        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        main_layout.addWidget(button_box)

        today = QDate.currentDate()
        self.start_date_edit.setDate(today)
        self.end_date_edit.setDate(today)

        if period is not None:
            self._load_from_period(period)

    def _load_from_period(self, period: BudgetPeriod):
        from PyQt6.QtCore import QDate

        self.name_edit.setText(period.name)
        self.notes_edit.setPlainText(period.notes)
        self.start_date_edit.setDate(QDate(period.start_date.year, period.start_date.month, period.start_date.day))
        self.end_date_edit.setDate(QDate(period.end_date.year, period.end_date.month, period.end_date.day))

    def get_period_data(self) -> dict:
        from PyQt6.QtCore import QDate

        sd_q: QDate = self.start_date_edit.date()
        ed_q: QDate = self.end_date_edit.date()
        sd = date(sd_q.year(), sd_q.month(), sd_q.day())
        ed = date(ed_q.year(), ed_q.month(), ed_q.day())
        return {
            "name": self.name_edit.text(),
            "start_date": sd,
            "end_date": ed,
            "notes": self.notes_edit.toPlainText(),
        }


class TransactionDialog(QDialog):
    """
    Dialog to create or edit a transaction.

    You pass in:
        - tx: existing Transaction (for editing) or None (for new)
        - periods: optional list[BudgetPeriod] to populate period combo

    Use get_transaction_data() to fetch:
        {
            "type": "income"/"outgoing",
            "date": date,
            "status": "pending"/"certain",
            "description": str,
            "amount": float,
            "category": str,
            "linked_period_id": Optional[int],
        }
    """

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        tx: Optional[Transaction] = None,
        periods: Optional[List[BudgetPeriod]] = None,
        categories: Optional[List[str]] = None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Transaction")
        self.setMinimumWidth(400)
        self.tx = tx
        self._periods = periods or []
        self._categories = categories or []

        from PyQt6.QtCore import QDate

        main_layout = QVBoxLayout(self)
        form_layout = QGridLayout()

        self.type_combo = QComboBox()
        self.type_combo.addItems(["Income", "Outgoing"])

        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)

        self.status_combo = QComboBox()
        self.status_combo.addItems(["Pending", "Certain"])

        self.description_edit = QLineEdit()

        self.amount_spin = QDoubleSpinBox()
        self.amount_spin.setMaximum(1_000_000_000)
        self.amount_spin.setDecimals(2)

        self.category_combo = QComboBox()
        self.category_combo.setEditable(True)
        if self._categories:
            self.category_combo.addItems(self._categories)

        self.period_combo = QComboBox()
        self.period_combo.setEditable(False)
        self.period_combo.addItem("Auto (let backend choose)", userData=None)
        for p in self._periods:
            self.period_combo.addItem(p.name, userData=p.id)

        row = 0
        form_layout.addWidget(QLabel("Type:"), row, 0)
        form_layout.addWidget(self.type_combo, row, 1)
        row += 1

        form_layout.addWidget(QLabel("Date:"), row, 0)
        form_layout.addWidget(self.date_edit, row, 1)
        row += 1

        form_layout.addWidget(QLabel("Status:"), row, 0)
        form_layout.addWidget(self.status_combo, row, 1)
        row += 1

        form_layout.addWidget(QLabel("Description:"), row, 0)
        form_layout.addWidget(self.description_edit, row, 1)
        row += 1

        form_layout.addWidget(QLabel("Amount:"), row, 0)
        form_layout.addWidget(self.amount_spin, row, 1)
        row += 1

        form_layout.addWidget(QLabel("Category:"), row, 0)
        form_layout.addWidget(self.category_combo, row, 1)
        row += 1

        form_layout.addWidget(QLabel("Linked Period:"), row, 0)
        form_layout.addWidget(self.period_combo, row, 1)
        row += 1

        main_layout.addLayout(form_layout)

        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        main_layout.addWidget(button_box)

        today_qdate = QDate.currentDate()
        self.date_edit.setDate(today_qdate)

        if tx is not None:
            self._load_from_transaction(tx)

    def _load_from_transaction(self, tx: Transaction):
        from PyQt6.QtCore import QDate

        self.type_combo.setCurrentText(tx.type.capitalize())
        self.status_combo.setCurrentText(tx.status.capitalize())
        self.description_edit.setText(tx.description)
        self.amount_spin.setValue(tx.amount)
        self.category_combo.setCurrentText(tx.category)
        self.date_edit.setDate(QDate(tx.date.year, tx.date.month, tx.date.day))

        if tx.linked_period_id is not None:
            idx = self.period_combo.findData(tx.linked_period_id)
            if idx >= 0:
                self.period_combo.setCurrentIndex(idx)
        else:
            self.period_combo.setCurrentIndex(0)

    def get_transaction_data(self) -> dict:
        from PyQt6.QtCore import QDate

        qd: QDate = self.date_edit.date()
        d = date(qd.year(), qd.month(), qd.day())
        linked_data = self.period_combo.currentData()
        return {
            "type": self.type_combo.currentText().lower(),
            "date": d,
            "status": self.status_combo.currentText().lower(),
            "description": self.description_edit.text(),
            "amount": float(self.amount_spin.value()),
            "category": self.category_combo.currentText(),
            "linked_period_id": linked_data,  # None = let backend decide/link later
        }


# ---------------------------------------------------------------------------
# Budget Periods Page (pure UI, no backend mutations)
# ---------------------------------------------------------------------------

class BudgetPeriodsPage(QWidget):
    """
    Left: list of budget periods
    Right: detail of selected period + attached incomes/outgoings (view only).

    You must:
      - Provide data to the models from backend.
      - React to dialog results in the  BACKEND sections.
    """

    def __init__(
        self,
        periods_model: BudgetPeriodTableModel,
        transactions_model: TransactionTableModel,
        periods_proxy: BudgetPeriodFilterProxyModel,
        service: BudgetService,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.periods_model = periods_model
        self.transactions_model = transactions_model
        self.periods_proxy = periods_proxy
        self.service = service

        main_layout = QHBoxLayout(self)

        # Left side: Period list + filters
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)

        filter_layout = QHBoxLayout()
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search periods by name...")
        filter_layout.addWidget(self.search_edit)

        self.active_only_combo = QComboBox()
        self.active_only_combo.addItems(["All periods", "Active today only"])
        filter_layout.addWidget(self.active_only_combo)

        left_layout.addLayout(filter_layout)

        self.periods_table = QTableView()
        self.periods_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.periods_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.periods_table.setAlternatingRowColors(True)
        self.periods_table.setModel(self.periods_proxy)
        left_layout.addWidget(self.periods_table)

        sel_model = self.periods_table.selectionModel()
        if sel_model is not None:
            sel_model.selectionChanged.connect(self.on_period_selection_changed)

        btn_layout = QHBoxLayout()
        self.new_period_btn = QPushButton("New")
        self.edit_period_btn = QPushButton("Edit")
        self.delete_period_btn = QPushButton("Delete")
        btn_layout.addWidget(self.new_period_btn)
        btn_layout.addWidget(self.edit_period_btn)
        btn_layout.addWidget(self.delete_period_btn)
        left_layout.addLayout(btn_layout)

        # Right side: detail
        self.detail_widget = QWidget()
        detail_layout = QVBoxLayout(self.detail_widget)

        info_group = QGroupBox("Period Info")
        info_layout = QGridLayout(info_group)

        self.period_name_edit = QLineEdit()
        self.period_start_date = QDateEdit()
        self.period_start_date.setCalendarPopup(True)
        self.period_end_date = QDateEdit()
        self.period_end_date.setCalendarPopup(True)
        self.period_notes_edit = QPlainTextEdit()

        row = 0
        info_layout.addWidget(QLabel("Name:"), row, 0)
        info_layout.addWidget(self.period_name_edit, row, 1)
        row += 1

        info_layout.addWidget(QLabel("Start date:"), row, 0)
        info_layout.addWidget(self.period_start_date, row, 1)
        row += 1

        info_layout.addWidget(QLabel("End date:"), row, 0)
        info_layout.addWidget(self.period_end_date, row, 1)
        row += 1

        info_layout.addWidget(QLabel("Notes:"), row, 0)
        info_layout.addWidget(self.period_notes_edit, row, 1)
        row += 1

        info_btn_layout = QHBoxLayout()
        self.save_period_btn = QPushButton("Save changes")
        self.recalc_links_btn = QPushButton("Recalculate links")
        info_btn_layout.addWidget(self.save_period_btn)
        info_btn_layout.addWidget(self.recalc_links_btn)
        info_layout.addLayout(info_btn_layout, row, 0, 1, 2)

        detail_layout.addWidget(info_group)

        summary_group = QGroupBox("Summary")
        summary_layout = QGridLayout(summary_group)

        self.include_pending_checkbox = QPushButton("Include pending in totals")
        self.include_pending_checkbox.setCheckable(True)
        self.total_income_label = QLabel("Total income (certain): 0")
        self.total_outgoing_label = QLabel("Total outgoing (certain): 0")
        self.net_label = QLabel("Net (certain): 0")
        self.pending_income_label = QLabel("Pending income: 0")
        self.pending_outgoing_label = QLabel("Pending outgoing: 0")

        row = 0
        summary_layout.addWidget(self.total_income_label, row, 0)
        summary_layout.addWidget(self.total_outgoing_label, row, 1)
        row += 1
        summary_layout.addWidget(self.net_label, row, 0)
        row += 1
        summary_layout.addWidget(self.pending_income_label, row, 0)
        summary_layout.addWidget(self.pending_outgoing_label, row, 1)
        row += 1
        summary_layout.addWidget(self.include_pending_checkbox, row, 0, 1, 2)

        detail_layout.addWidget(summary_group)

        # Attached transactions tabs
        self.transactions_tabs = QTabWidget()

        # Income tab
        income_tab = QWidget()
        income_layout = QVBoxLayout(income_tab)
        income_filter_layout = QHBoxLayout()
        self.income_status_filter = QComboBox()
        self.income_status_filter.addItems(["All", "Certain", "Pending"])
        income_filter_layout.addWidget(QLabel("Status:"))
        income_filter_layout.addWidget(self.income_status_filter)
        income_layout.addLayout(income_filter_layout)

        self.income_table = QTableView()
        self.income_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.income_table.setAlternatingRowColors(True)
        income_layout.addWidget(self.income_table)
        self.transactions_tabs.addTab(income_tab, "Incomes")

        # Outgoing tab
        outgoing_tab = QWidget()
        outgoing_layout = QVBoxLayout(outgoing_tab)
        outgoing_filter_layout = QHBoxLayout()
        self.outgoing_status_filter = QComboBox()
        self.outgoing_status_filter.addItems(["All", "Certain", "Pending"])
        outgoing_filter_layout.addWidget(QLabel("Status:"))
        outgoing_filter_layout.addWidget(self.outgoing_status_filter)
        outgoing_layout.addLayout(outgoing_filter_layout)

        self.outgoing_table = QTableView()
        self.outgoing_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.outgoing_table.setAlternatingRowColors(True)
        outgoing_layout.addWidget(self.outgoing_table)
        self.transactions_tabs.addTab(outgoing_tab, "Outgoings")

        detail_layout.addWidget(self.transactions_tabs)

        # Proxies for attached transactions
        self.income_proxy = TransactionsFilterProxyModel()
        self.income_proxy.setSourceModel(self.transactions_model)
        self.income_proxy.set_type_filter("income")

        self.outgoing_proxy = TransactionsFilterProxyModel()
        self.outgoing_proxy.setSourceModel(self.transactions_model)
        self.outgoing_proxy.set_type_filter("outgoing")

        self.income_table.setModel(self.income_proxy)
        self.outgoing_table.setModel(self.outgoing_proxy)

        main_layout.addWidget(left_widget, stretch=1)
        main_layout.addWidget(self.detail_widget, stretch=2)

        # Connections
        self.search_edit.textChanged.connect(self.on_period_filter_changed)
        self.active_only_combo.currentIndexChanged.connect(self.on_period_filter_changed)
        self.new_period_btn.clicked.connect(self.on_new_period_clicked)
        self.edit_period_btn.clicked.connect(self.on_edit_period_clicked)
        self.delete_period_btn.clicked.connect(self.on_delete_period_clicked)
        self.save_period_btn.clicked.connect(self.on_save_period_clicked)
        self.recalc_links_btn.clicked.connect(self.on_recalc_links_clicked)
        self.include_pending_checkbox.toggled.connect(self.on_include_pending_toggled)

        self.income_status_filter.currentIndexChanged.connect(
            self.on_attached_income_filter_changed
        )
        self.outgoing_status_filter.currentIndexChanged.connect(
            self.on_attached_outgoing_filter_changed
        )

        # Initial load for this page from backend
        periods = self.service.get_periods()
        txs = self.service.get_transactions()
        self.periods_model.set_periods(periods)
        self.periods_model.set_transactions(txs)
        self.transactions_model.set_transactions(txs)

    # --------- helpers ---------

    def _get_selected_period(self) -> Optional[BudgetPeriod]:
        idxs = self.periods_table.selectionModel().selectedRows()
        if not idxs:
            return None
        proxy_index = idxs[0]
        source_index = self.periods_proxy.mapToSource(proxy_index)
        period: BudgetPeriod = self.periods_model.data(source_index, Qt.ItemDataRole.UserRole)
        return period

    def _update_detail_for_period(self, period: Optional[BudgetPeriod]):
        from PyQt6.QtCore import QDate

        if period is None:
            self.period_name_edit.setText("")
            self.period_notes_edit.setPlainText("")
            today = QDate.currentDate()
            self.period_start_date.setDate(today)
            self.period_end_date.setDate(today)
            self.income_proxy.set_linked_period_id(None)
            self.outgoing_proxy.set_linked_period_id(None)
            self._update_summary_labels(None)
            return

        self.period_name_edit.setText(period.name)
        self.period_notes_edit.setPlainText(period.notes)
        self.period_start_date.setDate(QDate(period.start_date.year, period.start_date.month, period.start_date.day))
        self.period_end_date.setDate(QDate(period.end_date.year, period.end_date.month, period.end_date.day))

        self.income_proxy.set_linked_period_id(period.id)
        self.outgoing_proxy.set_linked_period_id(period.id)

        self._update_summary_labels(period)

    def _update_summary_labels(self, period: Optional[BudgetPeriod]):
        if period is None:
            self.total_income_label.setText("Total income (certain): 0")
            self.total_outgoing_label.setText("Total outgoing (certain): 0")
            self.net_label.setText("Net (certain): 0")
            self.pending_income_label.setText("Pending income: 0")
            self.pending_outgoing_label.setText("Pending outgoing: 0")
            return

        inc_certain = 0.0
        out_certain = 0.0
        inc_pending = 0.0
        out_pending = 0.0

        include_pending = self.include_pending_checkbox.isChecked()

        for tx in self.transactions_model.transactions:
            if tx.linked_period_id != period.id:
                continue
            if tx.type == "income":
                if tx.status == "certain":
                    inc_certain += tx.amount
                else:
                    inc_pending += tx.amount
            elif tx.type == "outgoing":
                if tx.status == "certain":
                    out_certain += tx.amount
                else:
                    out_pending += tx.amount

        total_inc = inc_certain + (inc_pending if include_pending else 0.0)
        total_out = out_certain + (out_pending if include_pending else 0.0)

        self.total_income_label.setText(
            f"Total income ({'incl. pending' if include_pending else 'certain'}): {total_inc:.2f}"
        )
        self.total_outgoing_label.setText(
            f"Total outgoing ({'incl. pending' if include_pending else 'certain'}): {total_out:.2f}"
        )
        self.net_label.setText(f"Net: {(total_inc - total_out):.2f}")
        self.pending_income_label.setText(f"Pending income: {inc_pending:.2f}")
        self.pending_outgoing_label.setText(f"Pending outgoing: {out_pending:.2f}")

    # --------- slots / UI events (no backend side-effects) ---------

    def on_period_filter_changed(self):
        text = self.search_edit.text()
        self.periods_proxy.set_name_filter(text)
        active_only = self.active_only_combo.currentIndex() == 1
        self.periods_proxy.set_active_only(active_only)

    def on_period_selection_changed(self, selected, deselected):
        period = self._get_selected_period()
        self._update_detail_for_period(period)

    def on_new_period_clicked(self):
        dialog = PeriodDialog(self)
        if dialog.exec():
            data = dialog.get_period_data()
            self.service.create_period(data)
            periods = self.service.get_periods()
            txs = self.service.get_transactions()
            self.periods_model.set_periods(periods)
            self.periods_model.set_transactions(txs)
            self.transactions_model.set_transactions(txs)

    def on_edit_period_clicked(self):
        period = self._get_selected_period()
        if period is None:
            return
        dialog = PeriodDialog(self, period=period)
        if dialog.exec():
            data = dialog.get_period_data()
            self.service.update_period(data, period)
            periods = self.service.get_periods()
            txs = self.service.get_transactions()
            self.periods_model.set_periods(periods)
            self.periods_model.set_transactions(txs)
            self.transactions_model.set_transactions(txs)

    def on_delete_period_clicked(self):
        period = self._get_selected_period()
        if period is None:
            return
        self.service.delete_period(period)
        periods = self.service.get_periods()
        txs = self.service.get_transactions()
        self.periods_model.set_periods(periods)
        self.periods_model.set_transactions(txs)
        self.transactions_model.set_transactions(txs)

    def on_save_period_clicked(self):
        from PyQt6.QtCore import QDate

        period = self._get_selected_period()
        if period is None:
            return

        sd = self.period_start_date.date()
        ed = self.period_end_date.date()
        data = {
            "name": self.period_name_edit.text(),
            "start_date": date(sd.year(), sd.month(), sd.day()),
            "end_date": date(ed.year(), ed.month(), ed.day()),
            "notes": self.period_notes_edit.toPlainText(),
        }

        self.service.update_period(data, period)
        periods = self.service.get_periods()
        txs = self.service.get_transactions()
        self.periods_model.set_periods(periods)
        self.periods_model.set_transactions(txs)
        self.transactions_model.set_transactions(txs)

    def on_recalc_links_clicked(self):
        self.service.recalculate_attachments()
        periods = self.service.get_periods()
        txs = self.service.get_transactions()
        self.periods_model.set_periods(periods)
        self.periods_model.set_transactions(txs)
        self.transactions_model.set_transactions(txs)

    def on_include_pending_toggled(self, checked: bool):
        self._update_summary_labels(self._get_selected_period())

    def on_attached_income_filter_changed(self, index: int):
        text = self.income_status_filter.currentText()
        self.income_proxy.set_status_filter("all" if text == "All" else text.lower())

    def on_attached_outgoing_filter_changed(self, index: int):
        text = self.outgoing_status_filter.currentText()
        self.outgoing_proxy.set_status_filter("all" if text == "All" else text.lower())


# ---------------------------------------------------------------------------
# Transactions Page (global view, UI only)
# ---------------------------------------------------------------------------

class TransactionsPage(QWidget):
    """Global view of all transactions with filters."""

    def __init__(
        self,
        transactions_model: TransactionTableModel,
        periods_model: BudgetPeriodTableModel,
        service: BudgetService,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)

        self.transactions_model = transactions_model
        self.periods_model = periods_model
        self.service = service

        main_layout = QVBoxLayout(self)

        filter_layout = QHBoxLayout()

        self.type_filter = QComboBox()
        self.type_filter.addItems(["All types", "Incomes", "Outgoings"])

        self.status_filter = QComboBox()
        self.status_filter.addItems(["All statuses", "Certain", "Pending"])

        self.attachment_filter = QComboBox()
        self.attachment_filter.addItems(["All", "Attached", "Unattached"])

        self.date_from = QDateEdit()
        self.date_from.setCalendarPopup(True)
        self.date_to = QDateEdit()
        self.date_to.setCalendarPopup(True)

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search description/category...")

        self.reset_filters_btn = QPushButton("Reset")

        filter_layout.addWidget(QLabel("Type:"))
        filter_layout.addWidget(self.type_filter)
        filter_layout.addWidget(QLabel("Status:"))
        filter_layout.addWidget(self.status_filter)
        filter_layout.addWidget(QLabel("Attachment:"))
        filter_layout.addWidget(self.attachment_filter)
        filter_layout.addWidget(QLabel("From:"))
        filter_layout.addWidget(self.date_from)
        filter_layout.addWidget(QLabel("To:"))
        filter_layout.addWidget(self.date_to)
        filter_layout.addWidget(self.search_edit)
        filter_layout.addWidget(self.reset_filters_btn)

        main_layout.addLayout(filter_layout)

        self.transactions_table = QTableView()
        self.transactions_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.transactions_table.setAlternatingRowColors(True)

        self.proxy = TransactionsFilterProxyModel()
        self.proxy.setSourceModel(self.transactions_model)
        self.transactions_table.setModel(self.proxy)

        main_layout.addWidget(self.transactions_table)

        # NEW: actions layout with "Delete selected" button
        actions_layout = QHBoxLayout()
        self.delete_selected_btn = QPushButton("Delete selected")
        actions_layout.addWidget(self.delete_selected_btn)
        actions_layout.addStretch()
        main_layout.addLayout(actions_layout)

        totals_layout = QHBoxLayout()
        self.visible_count_label = QLabel("Visible: 0")
        self.visible_income_total_label = QLabel("Income (certain, visible): 0")
        self.visible_outgoing_total_label = QLabel("Outgoing (certain, visible): 0")
        totals_layout.addWidget(self.visible_count_label)
        totals_layout.addWidget(self.visible_income_total_label)
        totals_layout.addWidget(self.visible_outgoing_total_label)
        totals_layout.addStretch()
        main_layout.addLayout(totals_layout)

        self.type_filter.currentIndexChanged.connect(self.on_filter_changed)
        self.status_filter.currentIndexChanged.connect(self.on_filter_changed)
        self.attachment_filter.currentIndexChanged.connect(self.on_filter_changed)
        self.date_from.dateChanged.connect(self.on_filter_changed)
        self.date_to.dateChanged.connect(self.on_filter_changed)
        self.search_edit.textChanged.connect(self.on_filter_changed)
        self.reset_filters_btn.clicked.connect(self.on_reset_filters_clicked)

        self.transactions_table.doubleClicked.connect(self.on_transaction_double_clicked)
        self.delete_selected_btn.clicked.connect(self.on_delete_selected_clicked)

        # Initial load from backend for this page
        txs = self.service.get_transactions()
        self.transactions_model.set_transactions(txs)
        self.periods_model.set_transactions(txs)

        self.refresh_totals()

    def on_filter_changed(self, *args, **kwargs):
        from PyQt6.QtCore import QDate

        t = self.type_filter.currentText()
        self.proxy.set_type_filter("income" if t == "Incomes" else "outgoing" if t == "Outgoings" else "all")

        s = self.status_filter.currentText()
        self.proxy.set_status_filter("certain" if s == "Certain" else "pending" if s == "Pending" else "all")

        a = self.attachment_filter.currentText()
        self.proxy.set_attachment_filter("attached" if a == "Attached" else "unattached" if a == "Unattached" else "all")

        df: QDate = self.date_from.date()
        dt: QDate = self.date_to.date()
        self.proxy.set_date_from(None if df.isNull() else date(df.year(), df.month(), df.day()))
        self.proxy.set_date_to(None if dt.isNull() else date(dt.year(), dt.month(), dt.day()))

        self.proxy.set_search_text(self.search_edit.text())
        self.refresh_totals()

    def on_reset_filters_clicked(self):
        from PyQt6.QtCore import QDate

        self.type_filter.setCurrentIndex(0)
        self.status_filter.setCurrentIndex(0)
        self.attachment_filter.setCurrentIndex(0)
        self.date_from.setDate(QDate())
        self.date_to.setDate(QDate())
        self.search_edit.clear()
        self.on_filter_changed()

    def on_transaction_double_clicked(self, index):
        proxy_index = index
        source_index = self.proxy.mapToSource(proxy_index)
        tx: Transaction = self.transactions_model.data(source_index, Qt.ItemDataRole.UserRole)
        if tx is None:
            return

        dialog = TransactionDialog(
            self,
            tx=tx,
            periods=self.periods_model.periods,
            categories=["try1", "try2"],
        )
        if dialog.exec():
            data = dialog.get_transaction_data()
            self.service.update_tx(data, tx)
            txs = self.service.get_transactions()
            self.transactions_model.set_transactions(txs)
            self.periods_model.set_transactions(txs)  # for totals

        self.refresh_totals()

    def on_delete_selected_clicked(self):
        idxs = self.transactions_table.selectionModel().selectedRows()
        if not idxs:
            return

        selected_ids = []
        for proxy_index in idxs:
            source_index = self.proxy.mapToSource(proxy_index)
            tx: Transaction = self.transactions_model.data(source_index, Qt.ItemDataRole.UserRole)
            if tx is not None:
                selected_ids.append(tx.id)

        if not selected_ids:
            return

        self.service.delete_tx(selected_ids)
        txs = self.service.get_transactions()
        self.transactions_model.set_transactions(txs)
        self.periods_model.set_transactions(txs)  # keep totals consistent
        self.refresh_totals()

    def refresh_totals(self):
        count, inc, out = self.proxy.visible_totals()
        self.visible_count_label.setText(f"Visible: {count}")
        self.visible_income_total_label.setText(f"Income (certain, visible): {inc:.2f}")
        self.visible_outgoing_total_label.setText(f"Outgoing (certain, visible): {out:.2f}")


# ---------------------------------------------------------------------------
# Pending Transactions Page (UI only)
# ---------------------------------------------------------------------------

class PendingTransactionsPage(QWidget):
    """
    Dedicated page for pending transactions (incomes + outgoings).
    All actions are delegated to backend via comments.
    """

    def __init__(
        self,
        transactions_model: TransactionTableModel,
        service: BudgetService,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)

        self.transactions_model = transactions_model
        self.service = service

        from PyQt6.QtCore import QDate

        main_layout = QVBoxLayout(self)

        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)

        self.income_proxy = TransactionsFilterProxyModel()
        self.income_proxy.setSourceModel(self.transactions_model)
        self.income_proxy.set_type_filter("income")
        self.income_proxy.set_status_filter("pending")

        self.outgoing_proxy = TransactionsFilterProxyModel()
        self.outgoing_proxy.setSourceModel(self.transactions_model)
        self.outgoing_proxy.set_type_filter("outgoing")
        self.outgoing_proxy.set_status_filter("pending")

        # ---------------- Incomes tab ----------------
        self.income_tab = QWidget()
        income_layout = QVBoxLayout(self.income_tab)

        income_filter_layout = QHBoxLayout()
        self.income_date_from = QDateEdit()
        self.income_date_from.setCalendarPopup(True)
        self.income_date_to = QDateEdit()
        self.income_date_to.setCalendarPopup(True)

        self.income_attachment_filter = QComboBox()
        self.income_attachment_filter.addItems(["All", "Attached", "Unattached"])

        self.income_search_edit = QLineEdit()
        self.income_search_edit.setPlaceholderText("Search pending incomes...")

        income_filter_layout.addWidget(QLabel("From:"))
        income_filter_layout.addWidget(self.income_date_from)
        income_filter_layout.addWidget(QLabel("To:"))
        income_filter_layout.addWidget(self.income_date_to)
        income_filter_layout.addWidget(QLabel("Attachment:"))
        income_filter_layout.addWidget(self.income_attachment_filter)
        income_filter_layout.addWidget(self.income_search_edit)

        income_layout.addLayout(income_filter_layout)

        self.pending_income_table = QTableView()
        self.pending_income_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.pending_income_table.setAlternatingRowColors(True)
        self.pending_income_table.setModel(self.income_proxy)
        income_layout.addWidget(self.pending_income_table)

        income_actions_layout = QHBoxLayout()
        self.income_mark_certain_btn = QPushButton("Mark selected as Certain")
        self.income_delete_btn = QPushButton("Delete selected")
        income_actions_layout.addWidget(self.income_mark_certain_btn)
        income_actions_layout.addWidget(self.income_delete_btn)
        income_actions_layout.addStretch()
        income_layout.addLayout(income_actions_layout)

        self.tabs.addTab(self.income_tab, "Pending Incomes")

        # ---------------- Outgoings tab ----------------
        self.outgoing_tab = QWidget()
        outgoing_layout = QVBoxLayout(self.outgoing_tab)

        outgoing_filter_layout = QHBoxLayout()
        self.outgoing_date_from = QDateEdit()
        self.outgoing_date_from.setCalendarPopup(True)
        self.outgoing_date_to = QDateEdit()
        self.outgoing_date_to.setCalendarPopup(True)

        self.outgoing_attachment_filter = QComboBox()
        self.outgoing_attachment_filter.addItems(["All", "Attached", "Unattached"])

        self.outgoing_search_edit = QLineEdit()
        self.outgoing_search_edit.setPlaceholderText("Search pending outgoings...")

        outgoing_filter_layout.addWidget(QLabel("From:"))
        outgoing_filter_layout.addWidget(self.outgoing_date_from)
        outgoing_filter_layout.addWidget(QLabel("To:"))
        outgoing_filter_layout.addWidget(self.outgoing_date_to)
        outgoing_filter_layout.addWidget(QLabel("Attachment:"))
        outgoing_filter_layout.addWidget(self.outgoing_attachment_filter)
        outgoing_filter_layout.addWidget(self.outgoing_search_edit)

        outgoing_layout.addLayout(outgoing_filter_layout)

        self.pending_outgoing_table = QTableView()
        self.pending_outgoing_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.pending_outgoing_table.setAlternatingRowColors(True)
        self.pending_outgoing_table.setModel(self.outgoing_proxy)
        outgoing_layout.addWidget(self.pending_outgoing_table)

        outgoing_actions_layout = QHBoxLayout()
        self.outgoing_mark_certain_btn = QPushButton("Mark selected as Certain")
        self.outgoing_delete_btn = QPushButton("Delete selected")
        outgoing_actions_layout.addWidget(self.outgoing_mark_certain_btn)
        outgoing_actions_layout.addWidget(self.outgoing_delete_btn)
        outgoing_actions_layout.addStretch()
        outgoing_layout.addLayout(outgoing_actions_layout)

        self.tabs.addTab(self.outgoing_tab, "Pending Outgoings")

        # Default dates
        self.income_date_from.setDate(QDate())
        self.income_date_to.setDate(QDate())
        self.outgoing_date_from.setDate(QDate())
        self.outgoing_date_to.setDate(QDate())

        # Filters
        self.income_date_from.dateChanged.connect(self.on_income_filter_changed)
        self.income_date_to.dateChanged.connect(self.on_income_filter_changed)
        self.income_attachment_filter.currentIndexChanged.connect(self.on_income_filter_changed)
        self.income_search_edit.textChanged.connect(self.on_income_filter_changed)

        self.outgoing_date_from.dateChanged.connect(self.on_outgoing_filter_changed)
        self.outgoing_date_to.dateChanged.connect(self.on_outgoing_filter_changed)
        self.outgoing_attachment_filter.currentIndexChanged.connect(self.on_outgoing_filter_changed)
        self.outgoing_search_edit.textChanged.connect(self.on_outgoing_filter_changed)

        # Actions
        self.income_mark_certain_btn.clicked.connect(self.on_income_mark_certain_clicked)
        self.income_delete_btn.clicked.connect(self.on_income_delete_clicked)

        self.outgoing_mark_certain_btn.clicked.connect(self.on_outgoing_mark_certain_clicked)
        self.outgoing_delete_btn.clicked.connect(self.on_outgoing_delete_clicked)

        # Initial load from backend for this page
        txs = self.service.get_transactions()
        self.transactions_model.set_transactions(txs)

    # --------- income tab ---------

    def _apply_income_filters(self):
        from PyQt6.QtCore import QDate

        df: QDate = self.income_date_from.date()
        dt: QDate = self.income_date_to.date()

        self.income_proxy.set_date_from(None if df.isNull() else date(df.year(), df.month(), df.day()))
        self.income_proxy.set_date_to(None if dt.isNull() else date(dt.year(), dt.month(), dt.day()))

        a = self.income_attachment_filter.currentText()
        self.income_proxy.set_attachment_filter(
            "attached" if a == "Attached" else "unattached" if a == "Unattached" else "all"
        )

        self.income_proxy.set_search_text(self.income_search_edit.text())

    def on_income_filter_changed(self, *args, **kwargs):
        self._apply_income_filters()

    def _get_selected_pending(self, proxy: TransactionsFilterProxyModel, table: QTableView) -> List[Transaction]:
        idxs = table.selectionModel().selectedRows()
        selected: List[Transaction] = []
        for proxy_index in idxs:
            source_index = proxy.mapToSource(proxy_index)
            tx: Transaction = self.transactions_model.data(source_index, Qt.ItemDataRole.UserRole)
            if tx is not None:
                selected.append(tx)
        return selected

    def on_income_mark_certain_clicked(self):
        selected = self._get_selected_pending(self.income_proxy, self.pending_income_table)
        self.service.mark_certain(selected)
        txs = self.service.get_transactions()
        self.transactions_model.set_transactions(txs)

    def on_income_delete_clicked(self):
        selected = self._get_selected_pending(self.income_proxy, self.pending_income_table)
        if not selected:
            return
        self.service.delete_pending(selected)
        txs = self.service.get_transactions()
        self.transactions_model.set_transactions(txs)

    # --------- outgoing tab ---------

    def _apply_outgoing_filters(self):
        from PyQt6.QtCore import QDate

        df: QDate = self.outgoing_date_from.date()
        dt: QDate = self.outgoing_date_to.date()

        self.outgoing_proxy.set_date_from(None if df.isNull() else date(df.year(), df.month(), df.day()))
        self.outgoing_proxy.set_date_to(None if dt.isNull() else date(dt.year(), dt.month(), dt.day()))

        a = self.outgoing_attachment_filter.currentText()
        self.outgoing_proxy.set_attachment_filter(
            "attached" if a == "Attached" else "unattached" if a == "Unattached" else "all"
        )

        self.outgoing_proxy.set_search_text(self.outgoing_search_edit.text())

    def on_outgoing_filter_changed(self, *args, **kwargs):
        self._apply_outgoing_filters()

    def on_outgoing_mark_certain_clicked(self):
        selected = self._get_selected_pending(self.outgoing_proxy, self.pending_outgoing_table)
        self.service.mark_certain(selected)
        txs = self.service.get_transactions()
        self.transactions_model.set_transactions(txs)

    def on_outgoing_delete_clicked(self):
        selected = self._get_selected_pending(self.outgoing_proxy, self.pending_outgoing_table)
        if not selected:
            return
        self.service.delete_pending(selected)
        txs = self.service.get_transactions()
        self.transactions_model.set_transactions(txs)


# ---------------------------------------------------------------------------
# Main Window (entry point for backend to plug into)
# ---------------------------------------------------------------------------

class MainWindow(QMainWindow):
    """
    Main window with navigation and stacked pages.

    Backend should:
      - Instantiate this window
      - Use `load_data(...)` to push periods & transactions into models
      - Fill in BACKEND sections with real logic (or connect signals)
    """

    def __init__(self, service: BudgetService):
        super().__init__()
        self.service = service

        self.setWindowTitle("Budget Tracker")
        self.resize(1200, 800)

        # UI models (start empty, backend must feed data)
        self.periods_model = BudgetPeriodTableModel()
        self.transactions_model = TransactionTableModel()

        # period resolver so TransactionTableModel can show period names
        def resolve_period(pid: Optional[int]) -> Optional[BudgetPeriod]:
            if pid is None:
                return None
            for p in self.periods_model.periods:
                if p.id == pid:
                    return p
            return None

        self.transactions_model.set_period_resolver(resolve_period)

        # Proxy for list of periods
        self.periods_proxy = BudgetPeriodFilterProxyModel()
        self.periods_proxy.setSourceModel(self.periods_model)

        central_widget = QWidget()
        central_layout = QHBoxLayout(central_widget)

        self.nav_list = QListWidget()
        self.nav_list.setFixedWidth(180)
        self.nav_list.setSpacing(4)
        self.nav_list.setUniformItemSizes(True)

        self.nav_budget_periods = QListWidgetItem("Budget Periods")
        self.nav_transactions = QListWidgetItem("Transactions")
        self.nav_pending = QListWidgetItem("Pending")

        self.nav_list.addItem(self.nav_budget_periods)
        self.nav_list.addItem(self.nav_transactions)
        self.nav_list.addItem(self.nav_pending)

        central_layout.addWidget(self.nav_list)

        self.pages = QStackedWidget()

        self.budget_periods_page = BudgetPeriodsPage(
            self.periods_model,
            self.transactions_model,
            self.periods_proxy,
            self.service,
        )
        self.transactions_page = TransactionsPage(
            self.transactions_model,
            self.periods_model,
            self.service,
        )
        self.pending_page = PendingTransactionsPage(
            self.transactions_model,
            self.service,
        )

        self.pages.addWidget(self.budget_periods_page)
        self.pages.addWidget(self.transactions_page)
        self.pages.addWidget(self.pending_page)

        central_layout.addWidget(self.pages)

        self.setCentralWidget(central_widget)

        toolbar = QToolBar("Main Toolbar")
        toolbar.setIconSize(QSize(16, 16))
        self.addToolBar(toolbar)

        self.new_period_action = toolbar.addAction("New Period")
        self.new_transaction_action = toolbar.addAction("New Transaction")

        status_bar = QStatusBar()
        self.setStatusBar(status_bar)

        # When navbar page changes, also refresh from backend
        self.nav_list.currentRowChanged.connect(self.on_nav_page_changed)
        self.new_period_action.triggered.connect(self.on_new_period_action_triggered)
        self.new_transaction_action.triggered.connect(self.on_new_transaction_action_triggered)

        # Initial full refresh from backend
        self.refresh_from_backend()

        self.nav_list.setCurrentRow(0)

    # --------- backend convenience API ---------

    def load_data(self, periods: List[BudgetPeriod], transactions: List[Transaction]):
        """
        Backend should call this to push current data into the UI models.
        """
        self.periods_model.set_periods(periods)
        self.periods_model.set_transactions(transactions)
        self.transactions_model.set_transactions(transactions)

    def refresh_from_backend(self):
        """
        Fetch fresh data from backend and update all UI models/pages.
        Called:
          - On app start
          - Whenever navbar page changes
          - From toolbar actions
        """
        # >>> RELOAD ALL MODELS FROM BACKEND HERE <<<
        periods = self.service.get_periods()
        txs = self.service.get_transactions()
        self.load_data(periods, txs)

        # >>> PAGE-SPECIFIC AFTER-REFRESH UPDATES HERE <<<
        # Transactions page totals (uses proxy on transactions_model)
        self.transactions_page.refresh_totals()

        # Keep summary on BudgetPeriodsPage consistent with selection
        period = self.budget_periods_page._get_selected_period()
        self.budget_periods_page._update_summary_labels(period)

    # --------- navigation handler ---------

    def on_nav_page_changed(self, row: int):
        # Switch visible page
        self.pages.setCurrentIndex(row)
        # >>> RELOAD DATA WHEN A NAVBAR PAGE IS OPENED <<<
        self.refresh_from_backend()

    # --------- toolbar handlers (UI only) ---------

    def on_new_period_action_triggered(self):
        dialog = PeriodDialog(self)
        if dialog.exec():
            data = dialog.get_period_data()
            self.service.create_period(data)
            # After creation, refresh everything
            self.refresh_from_backend()

    def on_new_transaction_action_triggered(self):
        dialog = TransactionDialog(
            self,
            tx=None,
            periods=self.periods_model.periods,
            categories=["try1", "try2"],
        )
        if dialog.exec():
            data = dialog.get_transaction_data()
            self.service.create_tx(data)
            # After creation, refresh everything
            self.refresh_from_backend()


# ---------------------------------------------------------------------------
# Entry point (pure UI, no backend)
# ---------------------------------------------------------------------------

def main(service: BudgetService):
    app = QApplication(sys.argv)
    window = MainWindow(service)
    window.show()
    sys.exit(app.exec())
