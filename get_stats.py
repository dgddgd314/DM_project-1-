import pymysql
import os
from datetime import datetime

DB_CONFIG = {
    "host": "127.0.0.1",
    "user": "soop_user",
    "password": "SoopCrawler2026!",
    "database": "soop_dm",
    "cursorclass": pymysql.cursors.DictCursor
}

def get_stats():
    connection = pymysql.connect(**DB_CONFIG)
    try:
        with connection.cursor() as cursor:
            sql = """
            SELECT 
                r.run_id, 
                r.started_at, 
                r.ended_at, 
                r.status,
                (SELECT COUNT(*) FROM minute_features WHERE run_id = r.run_id) as features,
                (SELECT COUNT(*) FROM chat_messages_raw WHERE run_id = r.run_id) as chats
            FROM crawl_runs r
            WHERE r.run_id >= 29
            ORDER BY r.run_id ASC;
            """
            cursor.execute(sql)
            rows = cursor.fetchall()
            
            print(f"{'ID':<5} | {'Started At (KST)':<20} | {'Status':<10} | {'Features':<10} | {'Chats':<10}")
            print("-" * 65)
            for row in rows:
                st = row['started_at'].strftime('%Y-%m-%d %H:%M') if row['started_at'] else 'N/A'
                print(f"{row['run_id']:<5} | {st:<20} | {row['status']:<10} | {row['features']:<10} | {row['chats']:<10}")
                
    finally:
        connection.close()

if __name__ == "__main__":
    get_stats()
