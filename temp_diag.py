
import sys
import os
import json
import pandas as pd
from core.db import engine

try:
    # Get last 5 runs metadata
    df_runs = pd.read_sql("SELECT * FROM crawl_runs ORDER BY run_id DESC LIMIT 5", engine)
    
    results = []
    for idx, row in df_runs.iterrows():
        rid = row["run_id"]
        # Try to find a timestamp column
        time_col = "created_at" if "created_at" in row else ("timestamp" if "timestamp" in row else None)
        st = str(row[time_col]) if time_col else "unknown"
        
        # Snapshot count
        snap_cnt = pd.read_sql(f"SELECT COUNT(*) as cnt FROM live_snapshots WHERE run_id={rid}", engine).iloc[0,0]
        
        # Chat count
        chat_cnt = pd.read_sql(f"SELECT COUNT(*) as cnt FROM chat_messages_raw WHERE run_id={rid}", engine).iloc[0,0]
        
        # Feature count
        feat_cnt = pd.read_sql(f"SELECT COUNT(*) as cnt FROM minute_features WHERE run_id={rid}", engine).iloc[0,0]
        
        results.append({
            "run_id": int(rid),
            "start_time": st,
            "snapshots": int(snap_cnt),
            "chats": int(chat_cnt),
            "features": int(feat_cnt)
        })
    print(json.dumps(results))
except Exception as e:
    print(json.dumps({"error": str(e)}))
