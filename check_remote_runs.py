
import subprocess

def run_ssh_command(cmd):
    full_cmd = [
        "ssh", "-i", "C:\\Users\\PC\\Downloads\\soop-crawler-key.pem",
        "ubuntu@52.62.62.79",
        f"cd app/chzzk-crawler && source .venv/bin/activate && {cmd}"
    ]
    result = subprocess.run(full_cmd, capture_output=True, text=True, shell=True)
    return result.stdout, result.stderr

sql = "SELECT run_id, MIN(start_time), MAX(start_time) FROM minute_features GROUP BY run_id ORDER BY run_id DESC LIMIT 10"
py_cmd = f"python -c \"import mysql.connector; from config.db_config import DB_CONFIG; conn = mysql.connector.connect(**DB_CONFIG); cursor = conn.cursor(); cursor.execute('{sql}'); [print(row) for row in cursor.fetchall()]\""

stdout, stderr = run_ssh_command(py_cmd)
print("STDOUT:", stdout)
print("STDERR:", stderr)
