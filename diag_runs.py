
import subprocess

def run_ssh_command(cmd):
    full_cmd = [
        "ssh", "-i", "C:\\Users\\PC\\Downloads\\soop-crawler-key.pem",
        "ubuntu@52.62.62.79",
        f"cd app/chzzk-crawler && source .venv/bin/activate && {cmd}"
    ]
    result = subprocess.run(full_cmd, capture_output=True, text=True)
    return result.stdout, result.stderr

# This script will be executed on the server via python -c
# We avoid nested quotes by using single quotes for the python command 
# and double quotes inside, but we need to be careful with shell escaping.
py_code = """
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
"""

# To avoid escaping hell, I'll write this to a temp file and scp it
with open("temp_diag.py", "w") as f:
    f.write(py_code)

subprocess.run(["scp", "-i", "C:\\Users\\PC\\Downloads\\soop-crawler-key.pem", "temp_diag.py", "ubuntu@52.62.62.79:/home/ubuntu/app/chzzk-crawler/temp_diag.py"])
stdout, stderr = run_ssh_command("python temp_diag.py")
print(stdout)
if stderr:
    print("Error:", stderr)
