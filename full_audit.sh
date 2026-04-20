#!/bin/bash
echo "=== DISK SPACE ==="
df -h /
echo ""

echo "=== MEMORY ==="
free -h
echo ""

echo "=== MySQL DB SIZES ==="
mysql -u soop_user -pSoopCrawler2026! soop_dm -e "
SELECT table_name, table_rows,
       ROUND(data_length/1024/1024,2) as data_MB,
       ROUND(index_length/1024/1024,2) as index_MB
FROM information_schema.tables
WHERE table_schema='soop_dm'
ORDER BY data_length DESC;" 2>/dev/null
echo ""

echo "=== ALL RUNS SUMMARY ==="
mysql -u soop_user -pSoopCrawler2026! soop_dm -e "
SELECT r.run_id, r.run_date, r.window_label, r.started_at, r.ended_at, r.status,
       (SELECT COUNT(*) FROM live_snapshots WHERE run_id = r.run_id) as snapshots,
       (SELECT COUNT(*) FROM chat_messages_raw WHERE run_id = r.run_id) as chats,
       (SELECT COUNT(*) FROM minute_features WHERE run_id = r.run_id) as features
FROM crawl_runs r ORDER BY r.run_id DESC;" 2>/dev/null
echo ""

echo "=== LOG FILE SIZES ==="
du -sh /home/ubuntu/app/chzzk-crawler/logs/* 2>/dev/null
echo ""

echo "=== CSV FILES ==="
ls -lh /home/ubuntu/app/chzzk-crawler/*.csv 2>/dev/null
echo ""

echo "=== .ENV CONFIG ==="
cat /home/ubuntu/app/chzzk-crawler/.env
echo ""

echo "=== CRONTAB ==="
crontab -l
echo ""

echo "=== RUNNING PROCESSES ==="
ps aux | grep -E 'python|mysql' | grep -v grep
echo ""

echo "=== MYSQL STATUS ==="
systemctl status mysql --no-pager 2>/dev/null | head -15
echo ""

echo "=== CORE MODULE: database.py ==="
cat /home/ubuntu/app/chzzk-crawler/core/db.py 2>/dev/null
echo ""

echo "=== CORE MODULE: models.py ==="
cat /home/ubuntu/app/chzzk-crawler/core/models.py 2>/dev/null
echo ""

echo "=== CONFIGS: settings.py ==="
cat /home/ubuntu/app/chzzk-crawler/configs/settings.py 2>/dev/null
echo ""

echo "=== PIPELINE: manager.py ==="
cat /home/ubuntu/app/chzzk-crawler/pipeline/manager.py 2>/dev/null
echo ""

echo "=== PIPELINE: aggregate.py ==="
cat /home/ubuntu/app/chzzk-crawler/pipeline/aggregate.py 2>/dev/null
echo ""

echo "=== SCRIPTS: run_pilot.py ==="
cat /home/ubuntu/app/chzzk-crawler/scripts/run_pilot.py 2>/dev/null
echo ""

echo "=== SCRIPTS: verify_run.py ==="
cat /home/ubuntu/app/chzzk-crawler/scripts/verify_run.py 2>/dev/null
echo ""

echo "=== SCRIPTS: export_csv.py ==="
cat /home/ubuntu/app/chzzk-crawler/scripts/export_csv.py 2>/dev/null
echo ""

echo "=== SCRIPTS: setup.py ==="
cat /home/ubuntu/app/chzzk-crawler/scripts/setup.py 2>/dev/null
echo ""

echo "=== COLLECTORS: base.py ==="
cat /home/ubuntu/app/chzzk-crawler/collectors/base.py 2>/dev/null
echo ""

echo "=== COLLECTORS: chat_wss.py ==="
cat /home/ubuntu/app/chzzk-crawler/collectors/chat_wss.py 2>/dev/null
echo ""

echo "=== COLLECTORS: live_discovery.py ==="
cat /home/ubuntu/app/chzzk-crawler/collectors/live_discovery.py 2>/dev/null
echo ""

echo "=== build_pool.py ==="
cat /home/ubuntu/app/chzzk-crawler/build_pool.py 2>/dev/null
echo ""

echo "=== find_top20.py ==="
cat /home/ubuntu/app/chzzk-crawler/find_top20.py 2>/dev/null
echo ""
