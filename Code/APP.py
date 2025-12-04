import sys
import UI
import domain
import service
import json
from pathlib import Path

# --- PyInstaller splash handling (safe import) ---
try:
    if getattr(sys, "frozen", False):
        import pyi_splash
    else:
        pyi_splash = None
except ModuleNotFoundError:
    pyi_splash = None
# -------------------------------------------------


def main():
    P_Path = Path("Periods.json")
    T_Path = Path("Transactions.json")
    if not P_Path.exists() and not T_Path.exists():
        service.Save([], [])
    elif not P_Path.exists():
        service.save_periods_to_json([], "Periods.json")
    elif not T_Path.exists():
        service.save_transactions_to_json([], "Transactions.json")
    
    service_obj = service.BudgetService(
        service.load_periods_from_json(),
        service.load_transactions_from_json()
    )

    # >>> CLOSE THE PYINSTALLER SPLASH HERE <<<
    if pyi_splash is not None:
        pyi_splash.close()
    # >>> SPLASH IS GONE, NOW START YOUR UI <<<
    
    UI.main(service_obj)
    

if __name__ == "__main__":
    main()
