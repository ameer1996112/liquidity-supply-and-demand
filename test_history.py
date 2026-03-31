import json
from src.adapters.supabase_api import get_api_supabase
from src.api_portfolio_control import get_trade_history

def run():
    try:
        res = get_trade_history("ACG-DEMO-2", 90, None)
        print(f"Returned trades count: {len(res['trades'])}")
        for t in res['trades']:
            print(f"ID: {t.get('id')}, Date: {t.get('exit_time') or t.get('entry_time')}, Pnl: {t.get('pnl_usd')}")
    except Exception as e:
        print("ERROR:", e)

if __name__ == '__main__':
    run()
