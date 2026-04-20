from core.database import SessionLocal
from sqlalchemy import text

db = SessionLocal()

result = db.execute(text('''
    SELECT r.id, r.started_at, r.ended_at,
           (SELECT COUNT(*) FROM live_snapshots WHERE run_id = r.id) as snapshots,
           (SELECT COUNT(*) FROM chat_messages_raw WHERE run_id = r.id) as chats,
           (SELECT COUNT(*) FROM minute_features WHERE run_id = r.id) as features
    FROM collection_runs r
    ORDER BY r.id DESC
    LIMIT 15
'''))
print('run_id | started_at          | ended_at            | snapshots | chats   | features')
print('-'*100)
for row in result:
    print(f'{row[0]:6} | {row[1]} | {row[2]} | {row[3]:9} | {row[4]:7} | {row[5]}')
db.close()
