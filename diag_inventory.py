from core.db import SessionLocal
from sqlalchemy import text

def get_stats():
    session = SessionLocal()
    print("--- Features ---")
    res = session.execute(text("SELECT run_id, COUNT(*) FROM minute_features WHERE run_id BETWEEN 29 AND 48 GROUP BY run_id"))
    for row in res:
        print(f"Run {row[0]}: {row[1]} rows")
        
    print("\n--- Chats ---")
    res = session.execute(text("SELECT run_id, COUNT(*) FROM chat_messages_raw WHERE run_id BETWEEN 29 AND 48 GROUP BY run_id"))
    for row in res:
        print(f"Run {row[0]}: {row[1]} rows")
    
    session.close()

if __name__ == "__main__":
    get_stats()
