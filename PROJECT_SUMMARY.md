# CHZZK Livestream Data Crawler — Project Summary

## 1. Objective

This project develops a **real-time data collection system** for the CHZZK (Naver) livestream platform to support research on detecting **suspected anomalous viewing patterns** (e.g., view-bot segments) in Korean livestreams. The system captures synchronized **viewer count dynamics** and **chat message dynamics** at minute-level granularity, producing a labeled time-series dataset suitable for anomaly detection modeling.

---

## 2. Data Collection Methodology

### 2.1 Streamer Selection Strategy
To ensure **broad, unbiased coverage** across the CHZZK streamer population, the system implements a **two-stage random sampling** approach:

1. **Pool Construction (N ≈ 100):** Before each collection window, the system queries the CHZZK Open API to identify the top ~100 currently-live streamers ranked by concurrent viewer count. This forms the **candidate pool**.
2. **Random Selection (n = 20):** From this pool of 100, the system randomly selects 20 streamers to monitor during the session. A fresh random draw is performed independently for **each of the 3 daily collection windows**, maximizing population coverage over time.

This design avoids the bias of always tracking the same fixed set of streamers and ensures the dataset represents a diverse cross-section of the platform's ecosystem.

### 2.2 Collection Windows
Data is collected in **3 daily windows** during peak Korean viewing hours (KST):

| Window | KST Schedule | Duration | Purpose |
| :--- | :--- | :--- | :--- |
| Evening 1 | 5:00 PM – 7:00 PM | 2 hours | Early evening / after-school traffic |
| Evening 2 | 8:00 PM – 10:00 PM | 2 hours | Prime-time peak |
| Night | 11:00 PM – 1:00 AM | 2 hours | Late-night / potentially higher bot activity |

### 2.3 Data Sources
The system collects **two parallel data streams** per monitored streamer:

| Data Stream | Method | Frequency | Storage |
| :--- | :--- | :--- | :--- |
| **Viewer Snapshots** | CHZZK Open API v1 (`/open/v1/lives`) | Every 60 seconds | `live_snapshots` table |
| **Chat Messages** | Native WebSocket connection to Naver Game chat servers | Real-time (3-second flush intervals) | `chat_messages_raw` table |

---

## 3. Feature Engineering (Minute-Level Aggregation)

Raw data is automatically aggregated into **minute-level features** at the end of each collection run. The following features are computed per streamer per minute:

| Feature | Description |
| :--- | :--- |
| `viewer_count_last` | Last observed viewer count in the minute |
| `chat_count` | Total chat messages in the minute |
| `unique_chatters` | Number of distinct chat users |
| `avg_msg_len` | Average message length (characters) |
| `repeat_msg_ratio` | Ratio of repeated/duplicate messages |
| `new_chatter_ratio` | Ratio of first-time chatters in this minute |
| `chat_per_viewer` | Chat density = `chat_count / viewer_count` |
| `delta_viewer_1m` | Viewer count change vs. previous minute |
| `delta_chat_1m` | Chat count change vs. previous minute |

These features are stored in the `minute_features` table and exported as CSV for downstream analysis.

---

## 4. System Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    AWS EC2 Instance                      │
│                                                         │
│  ┌──────────────┐    ┌──────────────┐                   │
│  │ build_pool.py│───>│ setup.py     │  (Pool 100 →      │
│  │ (Top 100)    │    │ (Random 20)  │   Random 20)      │
│  └──────────────┘    └──────────────┘                   │
│         │                                               │
│         ▼                                               │
│  ┌─────────────────────────────────────┐                │
│  │         CrawlManager (manager.py)   │                │
│  │                                     │                │
│  │  ┌────────────┐  ┌──────────────┐   │                │
│  │  │ Live API   │  │ WebSocket    │   │                │
│  │  │ Snapshots  │  │ Chat (×20)   │   │                │
│  │  └─────┬──────┘  └──────┬───────┘   │                │
│  │        │                │           │                │
│  │        ▼                ▼           │                │
│  │  ┌──────────────────────────────┐   │                │
│  │  │    MySQL Database            │   │                │
│  │  │  - live_snapshots            │   │                │
│  │  │  - chat_messages_raw         │   │                │
│  │  │  - minute_features (ETL)     │   │                │
│  │  └──────────────────────────────┘   │                │
│  └─────────────────────────────────────┘                │
│                                                         │
│  Cron: 3 windows/day × 2 hours each                    │
└─────────────────────────────────────────────────────────┘
```

---

## 5. Technical Stack

| Component | Technology |
| :--- | :--- |
| Runtime | Python 3.11 |
| Database | MySQL 8.0 (via SQLAlchemy ORM) |
| Chat Collection | Native WebSocket (`websocket-client`) |
| API Access | CHZZK Open API v1 (Client ID/Secret auth) |
| Deployment | AWS EC2 (Ubuntu), cron-based scheduling |
| Data Export | Pandas → CSV (UTF-8 with BOM for Excel compatibility) |

---

## 6. Pilot Results

The system was validated through multiple pilot runs. Key metrics from a 1-hour pilot:

| Metric | Value |
| :--- | :--- |
| Chat messages collected | **94,188** |
| Viewer snapshots | **1,888** |
| Minute feature rows | **1,110** |
| Streamers monitored | **20** (random from pool of 100) |
| System stability | No crashes — API 500 errors handled gracefully |

---

## 7. Output Files

| File | Description |
| :--- | :--- |
| `pool_100.csv` | Full pool of top 100 streamers (for audit) |
| `top20_targets.csv` | The 20 randomly selected for current session |
| `run_XX_features.csv` | Minute-level feature dataset (research-ready) |
| `run_XX_chats.csv` | Raw chat messages with timestamps |

---

## 8. Automation

The system is fully automated via Linux cron. Before each collection window, it:
1. Fetches the current top 100 live streamers from CHZZK.
2. Randomly selects 20 from that pool.
3. Updates the tracking database.
4. Runs the 2-hour collection + aggregation pipeline.

No manual intervention is required for daily operation.
