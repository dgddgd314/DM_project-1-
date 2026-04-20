import subprocess
import sys

def main():
    start_id = 33
    end_id = 47
    
    for run_id in range(start_id, end_id + 1):
        print(f"--- Exporting Run {run_id} ---")
        
        # Export Features (Excel)
        cmd_feat = [
            "python", "scripts/export_csv.py",
            "--table", "minute_features",
            "--run_id", str(run_id),
            "--excel",
            "--out", f"exports/Run_{run_id}_Features.xlsx"
        ]
        subprocess.run(cmd_feat)
        
        # Export Chats (CSV - safer for size)
        cmd_chat = [
            "python", "scripts/export_csv.py",
            "--table", "chat_messages_raw",
            "--run_id", str(run_id),
            "--out", f"exports/Run_{run_id}_Chats.csv"
        ]
        subprocess.run(cmd_chat)

if __name__ == "__main__":
    main()
