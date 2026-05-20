from pathlib import Path
import numpy as np
import pandas as pd
from .session import make_session


def recalc(g):
    g = g.sort_values("minute_ts").copy()
    g["chat_count"] = g["chat_count"].clip(lower=0)
    g["unique_chatters"] = g["unique_chatters"].clip(lower=0)
    for c in ["avg_msg_len", "repeat_msg_ratio", "new_chatter_ratio"]:
        g[c] = np.where(g["chat_count"].eq(0), 0, g[c].fillna(0))
    g["chat_per_viewer"] = np.where(g["viewer_count_last"].gt(0), g["chat_count"] / g["viewer_count_last"], np.nan)
    g["delta_viewer_1m"] = g["viewer_count_last"].diff()
    g["delta_chat_1m"] = g["chat_count"].diff()
    return g


def choose_seg(n, rng, lo, hi):
    # Target a percentage of the session, but keep at least 3 minutes so the
    # injected pattern is visible after session-level aggregation.
    min_len = max(3, int(np.floor(lo * n)))
    max_len = max(min_len, int(np.ceil(hi * n)))
    length = int(rng.integers(min_len, max_len + 1))
    length = min(length, n)
    start = int(rng.integers(0, max(1, n - length + 1)))
    return start, start + length


def inject(base, kind, idx, rng):
    g = base.copy().sort_values("minute_ts").reset_index(drop=True)
    for c in ["viewer_count_last", "chat_count", "unique_chatters"]:
        if c not in g.columns:
            g[c] = 0.0
        g[c] = pd.to_numeric(g[c], errors="coerce").fillna(0).astype(float)
    n = len(g)

    g["run_id"] = -100000 - idx
    g["broad_no"] = f"syn_{kind}_{idx}"
    g["session_key"] = g["run_id"].astype(str) + "_" + g["broad_no"].astype(str)
    g["syn_type"] = kind
    g["y_syn"] = 1

    if kind == "hi_view_low_chat":
        a, b = choose_seg(n, rng, 0.30, 0.60)
        ix = g.index[a:b]
        g.loc[ix, "viewer_count_last"] *= rng.uniform(1.05, 1.50)
        g.loc[ix, "chat_count"] = np.floor(g.loc[ix, "chat_count"] * rng.uniform(0.02, 0.25))
        g.loc[ix, "unique_chatters"] = np.floor(g.loc[ix, "unique_chatters"] * rng.uniform(0.02, 0.30))

    if kind == "silent_run":
        a, b = choose_seg(n, rng, 0.15, 0.35)
        ix = g.index[a:b]
        g.loc[ix, ["chat_count", "unique_chatters", "avg_msg_len", "repeat_msg_ratio", "new_chatter_ratio"]] = 0

    if kind == "view_spike_no_chat":
        a, b = choose_seg(n, rng, 0.05, 0.15)
        ix = g.index[a:b]
        g.loc[ix, "viewer_count_last"] *= rng.uniform(2.0, 4.0)
        g.loc[ix, "chat_count"] = np.floor(g.loc[ix, "chat_count"] * rng.uniform(0.3, 1.0))
        g.loc[ix, "unique_chatters"] = np.floor(g.loc[ix, "unique_chatters"] * rng.uniform(0.3, 1.0))

    return recalc(g)


def _counts_text(df, col):
    if df is None or df.empty or col not in df.columns:
        return "none"
    vc = df[col].value_counts(dropna=False).sort_index()
    return ", ".join(f"{k}:{v}" for k, v in vc.items())


def write_injection_doc(out, cfg, base_n=0, syn_min=None, train=None, note="ok"):
    """Write a concise, execution-specific synthetic injection summary."""
    out = Path(out)
    seed = int(cfg["synthetic"]["seed"])
    n_per = int(cfg["synthetic"]["n_per_type"])
    min_n = int(cfg["prep"]["min_n"])
    syn_min_n = 0 if syn_min is None else len(syn_min)
    train_n = 0 if train is None else len(train)
    syn_sess_n = 0
    real_sess_n = 0
    if train is not None and not train.empty and "y_syn" in train.columns:
        syn_sess_n = int(train["y_syn"].eq(1).sum())
        real_sess_n = int(train["y_syn"].eq(0).sum())

    lines = [
        "Synthetic injection 자동 요약",
        "============================",
        "목적: 실제 뷰봇 라벨이 없어서, 명시적 이상 시나리오를 주입해 supervised 보조 score 학습용 데이터를 만든다.",
        "입력: minute_model.csv의 실제 eligible session과 session_summary_processed의 세션 요약 feature.",
        f"base eligible session 수: {base_n}",
        f"seed: {seed}, scenario별 최대 추출 session 수: {n_per}, 최소 minute 수: {min_n}",
        "",
        "주입 방식",
        "---------",
        "1. 각 시나리오별로 base session을 무작위 선택한다.",
        "2. 선택 세션에서 연속 minute 구간 하나를 선택한다. 구간 길이는 목표 비율을 따르되 최소 3분을 보장한다.",
        "3. 해당 구간의 viewer/chat/unique 관련 값을 시나리오별 배율 또는 0 처리로 수정한다.",
        "4. 수정 뒤 chat_per_viewer, delta_viewer_1m, delta_chat_1m을 다시 계산한다.",
        "5. synthetic minute를 다시 session feature로 요약하고 y_syn=1로 둔다.",
        "6. 실제 session은 y_syn=0, synthetic session은 y_syn=1로 합쳐 syn_train.csv를 만든다.",
        "",
        "시나리오",
        "--------",
        "hi_view_low_chat: 목표 30~60% 구간, viewer 1.05~1.50배, chat 0.02~0.25배, unique 0.02~0.30배.",
        "silent_run: 목표 15~35% 구간, chat_count/unique_chatters/avg_msg_len/repeat_msg_ratio/new_chatter_ratio를 0으로 설정.",
        "view_spike_no_chat: 목표 5~15% 구간, viewer 2.0~4.0배, chat 0.3~1.0배, unique 0.3~1.0배.",
        "공통: 목표 구간이 너무 짧으면 최소 3분으로 보정한다.",
        "",
        "생성 결과",
        "---------",
        f"status: {note}",
        f"syn_minute row 수: {syn_min_n}",
        f"syn_minute scenario 분포: {_counts_text(syn_min, 'syn_type')}",
        f"syn_train row 수: {train_n}",
        f"syn_train 실제 session(y_syn=0): {real_sess_n}",
        f"syn_train synthetic session(y_syn=1): {syn_sess_n}",
        "저장 파일: out/syn_minute.csv, out/syn_train.csv, out/synthetic_injection.txt",
    ]
    (out / "synthetic_injection.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")


def make_synthetic(minute_model, session_model, out, cfg):
    out = Path(out)
    rng = np.random.default_rng(int(cfg["synthetic"]["seed"]))

    if minute_model.empty or session_model.empty:
        write_injection_doc(out, cfg, base_n=0, note="minute_model 또는 session_model이 비어 있어 synthetic 생성 안 됨")
        return pd.DataFrame()

    # Synthetic anomalies are injected into all eligible real sessions.
    # No detector-combined cutoff is used, because final score fusion is not part
    # of this deliverable.
    base_sessions = session_model

    keys = base_sessions["session_key"].dropna().unique()
    n_per = min(int(cfg["synthetic"]["n_per_type"]), len(keys))
    kinds = ["hi_view_low_chat", "silent_run", "view_spike_no_chat"]

    rows = []
    idx = 0
    for kind in kinds:
        for key in rng.choice(keys, size=n_per, replace=len(keys) < n_per):
            base = minute_model[minute_model["session_key"].eq(key)]
            if len(base) >= int(cfg["prep"]["min_n"]):
                rows.append(inject(base, kind, idx, rng))
                idx += 1

    if not rows:
        write_injection_doc(out, cfg, base_n=len(base_sessions), note="min_n 조건을 만족하는 base session이 없어 synthetic 생성 안 됨")
        return pd.DataFrame()

    syn_min = pd.concat(rows, ignore_index=True)
    syn_min.to_csv(out / "syn_minute.csv", index=False, encoding="utf-8-sig")

    _, syn_sess, _ = make_session(syn_min, syn_min, cfg)
    syn_sess["y_syn"] = 1

    real_norm = base_sessions.copy()
    real_norm["y_syn"] = 0

    train = pd.concat([real_norm, syn_sess], ignore_index=True)
    train.to_csv(out / "syn_train.csv", index=False, encoding="utf-8-sig")
    write_injection_doc(out, cfg, base_n=len(base_sessions), syn_min=syn_min, train=train, note="ok")
    return train
