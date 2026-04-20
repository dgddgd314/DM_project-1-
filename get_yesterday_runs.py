
import subprocess
import os

key_path = r"C:\Users\PC\Downloads\soop-crawler-key.pem"
server = "ubuntu@52.62.62.79"

def run_ssh(cmd):
    full_cmd = f'ssh -i "{key_path}" {server} "{cmd}"'
    result = subprocess.run(full_cmd, capture_output=True, text=True, shell=True)
    return result.stdout

# Check runs for yesterday (April 13)
# KST is UTC+9. April 13 KST is April 12 15:00 UTC to April 13 15:00 UTC
query = "SELECT run_id, MIN(minute_ts), MAX(minute_ts) FROM minute_features WHERE minute_ts >= '2026-04-12 15:00:00' AND minute_ts < '2026-04-13 15:00:00' GROUP BY run_id;"
db_path = "/home/ubuntu/app/chzzk-crawler/data-back/chzzk_crawler.db"
# Use a simple sqlite3 command without complex shell characters
cmd = f"sqlite3 {db_path} \\\"{query}\\\"" 

output = run_ssh(cmd)
print("Runs from yesterday:")
print(output)
