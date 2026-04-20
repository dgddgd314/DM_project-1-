# CHZZK Data Dictionary (EN/KR) 
## 데이터 가이드 (영어/한국어 송어)

This document explains how to read the data fields in the exported **Feature** and **Chat** files for the CHZZK livestream crawler.
본 문서는 CHZZK 라이브스트림 크롤러에서 내보낸 **Feature(피처)** 및 **Chat(채팅)** 파일의 데이터 필드 읽는 법을 설명합니다.

---

### 1. Minute Features File (`CHZZK_Features_*.xlsx`)
**Minute-level aggregated metrics for each streamer.**
**스트리머별 분 단위 집계 데이터입니다.**

| Column Name (필드명) | Description (EN) | 설명 (KR) |
| :--- | :--- | :--- |
| **run_id** | Unique ID for the collection session. | 수집 세션의 고유 ID입니다. |
| **broad_no** | Unique identifier for the broadcast. | 방송의 고유 식별자입니다. |
| **minute_ts** | Timestamp of the data (YYYY-MM-DD HH:MM:00). | 데이터 수집 시점의 타임스탬프입니다. |
| **user_id** | Hashed unique ID of the streamer. | 스트리머의 고유 ID (해시 처리됨)입니다. |
| **category_id** | ID of the game or content category. | 게임 또는 콘텐츠 카테고리의 ID입니다. |
| **viewer_count_last** | Number of viewers at the end of this minute. | 해당 분의 종료 시점 시청자 수입니다. |
| **chat_count** | Total number of chat messages in this minute. | 해당 분 동안 발생한 총 채팅 메시지 수입니다. |
| **unique_chatters** | Number of unique users who sent at least one chat. | 채팅을 보낸 고유 이용자 수입니다. |
| **avg_msg_len** | Average length of characters per message. | 메시지당 평균 글자 길이입니다. |
| **repeat_msg_ratio** | Ratio of copy-paste/similar messages (0.0 to 1.0). | 반복/유사 메시지의 비율입니다 (스팸성 분석용). |
| **new_chatter_ratio** | Ratio of users chatting for the first time in this session. | 해당 세션에서 처음 채팅을 시작한 유저의 비율입니다. |
| **chat_per_viewer** | Engagement rate (Chat count / Viewer count). | 참여도 (채팅 수 / 시청자 수)입니다. |
| **delta_viewer_1m** | Change in viewers compared to the previous minute. | 전분 대비 시청자 수 변동 폭입니다. |
| **delta_chat_1m** | Change in chat count compared to the previous minute. | 전분 대비 채팅 수 변동 폭입니다. |

---

### 2. Chat Messages File (`CHZZK_Chats_*.csv`)
**Individual raw chat message data.**
**개별 채팅 메시지 원본 데이터입니다.**

| Column Name (필드명) | Description (EN) | 설명 (KR) |
| :--- | :--- | :--- |
| **chat_id** | Unique primary key for the chat record. | 채팅 레코드의 고유 기본 키입니다. |
| **run_id** | Session ID associated with this chat. | 이 채팅이 포함된 세션 ID입니다. |
| **event_ts** | The exact time when the chat was sent. | 채팅이 발송된 정확한 시간입니다. |
| **broad_no** | The broadcast ID where the chat occurred. | 채팅이 발생한 방송의 ID입니다. |
| **user_id** | Hashed identifier for the chatter (sender). | 채팅을 보낸 유저의 ID (해시 처리됨)입니다. |
| **user_nick** | Nickname of the user who sent the message. | 메시지를 보낸 유저의 닉네임입니다. |
| **message_raw** | Original message text as sent by the user. | 유저가 보낸 원본 메시지 텍스트입니다. |
| **message_clean** | Pre-processed message text (special chars removed). | 전처리된 메시지 텍스트 (특수문자 등 제거)입니다. |
| **message_hash** | Unique hash of the message content. | 메시지 내용의 고유 해시 값입니다. |
| **raw_json** | Full raw data payload from the CHZZK server (JSON). | CHZZK 서버에서 받은 원본 데이터 전체 (JSON 형태)입니다. |
| **created_at** | DB insertion timestamp. | 데이터베이스에 저장된 시간입니다. |

---

### Tips for Analysis
- **Engagement Analysis:** High `chat_per_viewer` or `unique_chatters` indicates a very active community.
- **Bot/Spam Detection:** High `repeat_msg_ratio` suggests potential bot activity or copy-paste "donating" behavior.
- **Trend Detection:** Observe `delta_viewer_1m` to find peak excitement moments in the stream.

**분석 팁:**
- **참여도 분석:** `chat_per_viewer`나 `unique_chatters`가 높으면 커뮤니티가 매우 활발함을 의미합니다.
- **스팸 탐지:** `repeat_msg_ratio`가 높으면 봇 활동이나 단순 복사-붙여넣기 "도배" 행위일 가능성이 높습니다.
- **트렌드 감지:** `delta_viewer_1m`을 관찰하여 방송 내 가장 흥미진진했던 순간을 찾을 수 있습니다.
