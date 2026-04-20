SELECT r.run_id, r.run_date, r.window_label, r.started_at, r.ended_at, r.status,
       (SELECT COUNT(*) FROM live_snapshots WHERE run_id = r.run_id) as snapshots,
       (SELECT COUNT(*) FROM chat_messages_raw WHERE run_id = r.run_id) as chats,
       (SELECT COUNT(*) FROM minute_features WHERE run_id = r.run_id) as features
FROM crawl_runs r
WHERE r.run_date >= '2026-04-12'
ORDER BY r.run_id;
