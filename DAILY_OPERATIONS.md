# Daily Operations Guide: CHZZK Livestream Crawler

This guide provides the necessary procedures for the daily monitoring, data extraction, and maintenance of the CHZZK data collection system.

---

## 1. System Architecture Overview
The crawler operates on an AWS EC2 instance and collects real-time data from the CHZZK (Naver) livestream platform. Each session:
1. **Builds a pool** of the top ~100 live streamers (by viewer count).
2. **Randomly selects 15** from that pool to avoid selection bias.
3. **Collects data** for 2 hours: viewer snapshots (per minute) + real-time chat messages (via WebSocket).
4. **Aggregates** minute-level features (chat density, unique chatters, repeat message ratio, etc.) into MySQL.

---

## 2. Automated Collection Schedule (Cron)
The system runs **3 data collection windows daily** (Seoul Time - KST). Before each window, it automatically refreshes the random 15 streamer selection from a fresh pool of 100.

| Session | KST Time (UTC+9) | Duration | Streamers |
| :--- | :--- | :--- | :--- |
| **Evening 1** | 5:00 PM - 7:00 PM | 2 Hours | Random 15 / pool 100 |
| **Evening 2** | 8:00 PM - 10:00 PM | 2 Hours | Random 15 / pool 100 |
| **Night** | 11:00 PM - 1:00 AM | 2 Hours | Random 15 / pool 100 |

> **Note:** Each window selects its own independent random subset of 15, meaning different streamers may be tracked across different windows. This ensures broad coverage across the streamer population.

---

## 3. Daily Health Check
To verify that the system is collecting data correctly, run the following command from your local machine:

```powershell
ssh -i "C:\Users\PC\Downloads\soop-crawler-key.pem" ubuntu@52.62.62.79 "cd app/chzzk-crawler && source .venv/bin/activate && python scripts/verify_run.py"
```

**What to look for:**
- High numbers in `Chat messages collected` (usually 50k+ for a 2-hour run).
- Increasing counts in `Minute feature rows built`.

---

## 4. Data Export Procedure
When you need to pull data for analysis (Excel/Python), follow these two steps:

### Step 1: Export to CSV on the Server
Connect via SSH and run the export script:

```powershell
# SSH into the server first
ssh -i "C:\Users\PC\Downloads\soop-crawler-key.pem" ubuntu@52.62.62.79

# Then on the server:
cd app/chzzk-crawler && source .venv/bin/activate

# Export minute features (most relevant for research)
python scripts/export_csv.py --table minute_features --out daily_features.csv

# Optional: Export raw chat messages
python scripts/export_csv.py --table chat_messages_raw --out daily_chats.csv

# Optional: Filter by specific run_id
python scripts/export_csv.py --table minute_features --run_id 24 --out run24_features.csv
```

### Step 2: Download file to Local Machine
Run this command on your **Local Computer** (PowerShell):

```powershell
scp -i "C:\Users\PC\Downloads\soop-crawler-key.pem" ubuntu@52.62.62.79:/home/ubuntu/app/chzzk-crawler/daily_features.csv ./
```

---

## 5. Manually Re-rolling the Streamer Pool (If Needed)
The pool is automatically rebuilt before each cron window. However, if you want to manually trigger a re-roll:

```powershell
ssh -i "C:\Users\PC\Downloads\soop-crawler-key.pem" ubuntu@52.62.62.79 "cd app/chzzk-crawler && source .venv/bin/activate && python build_pool.py && python scripts/setup.py --load-csv top15_targets.csv"
```

This will:
1. Scan CHZZK for the current top 100 streamers → `pool_100.csv`
2. Randomly select 15 from that pool → `top15_targets.csv`
3. Update the database with the new targets.

---

## 6. Troubleshooting
- **API 500 Errors:** Occasional Naver API congestion is normal. The system automatically retries or skips failed requests.
- **Connection Issues:** If SSH fails, check the AWS EC2 Console to ensure the instance is running.
- **Out of Memory (OOM):** The server has a 2GB swap file (`/swapfile`) configured to prevent crashes during heavy 2-hour crawling sessions with many chat messages.
- **Logs:**
    - `/home/ubuntu/app/chzzk-crawler/logs/crawler.log` (Crawler logic)
    - `/home/ubuntu/app/chzzk-crawler/logs/cron.log` (Schedule logs)

> [!IMPORTANT]
> Ensure the `.pem` key file remains at `C:\Users\PC\Downloads\soop-crawler-key.pem`. If you move it, update the commands above accordingly.
