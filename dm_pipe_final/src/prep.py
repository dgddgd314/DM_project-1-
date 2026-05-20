import numpy as np
import pandas as pd


KEY = ["run_id", "broad_no"]

MINUTE_COLS = [
    "source_file",
    "run_id", "broad_no", "session_key", "user_id", "category_id", "minute_ts",
    "viewer_count_last", "chat_count", "unique_chatters", "avg_msg_len",
    "repeat_msg_ratio", "new_chatter_ratio", "chat_per_viewer",
    "delta_viewer_1m", "delta_chat_1m"
]

NUM_COLS = [
    "viewer_count_last", "chat_count", "unique_chatters", "avg_msg_len",
    "repeat_msg_ratio", "new_chatter_ratio", "chat_per_viewer",
    "delta_viewer_1m", "delta_chat_1m"
]


def minute_cols(df):
    return [c for c in MINUTE_COLS if c in df.columns]


def to_num(s):
    return pd.to_numeric(s, errors="coerce")


def id_str(s):
    """Keep numeric and string broadcast IDs stable without creating 1101.0 text."""
    x = s.astype("string").str.strip().replace("", pd.NA)
    as_num = pd.to_numeric(x, errors="coerce")
    int_like = as_num.notna() & np.isclose(as_num, np.floor(as_num))
    x = x.mask(int_like, as_num.round().astype("Int64").astype("string"))
    return x


def fill_id(df, col, value):
    if col not in df.columns:
        df[col] = np.nan
    df[col] = df.groupby(KEY)[col].transform(lambda x: x.ffill().bfill())
    df[col] = df[col].fillna(value)
    return df


def fill_metric(df, col, flag):
    bad = df[col].isna() & df["chat_count"].gt(0)
    df[flag] = bad.astype(int)
    med = df.groupby(KEY)[col].transform("median")
    df[col] = df[col].fillna(med).fillna(0)
    return df


def clean_viewer(g, cfg):
    g = g.sort_values("minute_ts").copy()
    v = to_num(g["viewer_count_last"]).mask(lambda x: x.lt(0))
    if cfg["prep"].get("zero_viewer_na", True):
        v = v.mask(v.eq(0))

    miss = v.isna()
    g["v_miss_r"] = float(miss.mean()) if len(g) else np.nan
    g["v_edge"] = int(bool(len(g) and (miss.iloc[0] or miss.iloc[-1])))
    g["v_qc"] = int(miss.all())
    g["viewer_count_last"] = v.interpolate(method="linear", limit_direction="both").clip(lower=0)
    return g


def prep_minute(df, cfg):
    df = df.copy()
    df["minute_ts"] = pd.to_datetime(df["minute_ts"], errors="coerce")

    for c in NUM_COLS:
        if c not in df.columns:
            df[c] = np.nan
        df[c] = to_num(df[c])

    df["run_id"] = to_num(df["run_id"])
    df["broad_no"] = id_str(df["broad_no"])
    df = df.dropna(subset=["run_id", "broad_no", "minute_ts"]).copy()

    df["run_id"] = df["run_id"].astype(int)
    df = df.sort_values(KEY + ["minute_ts"]).reset_index(drop=True)

    df = fill_id(df, "user_id", "UNKNOWN_USER")
    df = fill_id(df, "category_id", "UNKNOWN_CAT")
    df = df.groupby(KEY, group_keys=False).apply(lambda g: clean_viewer(g, cfg)).reset_index(drop=True)

    df["chat_count"] = df["chat_count"].fillna(0).clip(lower=0)
    df["unique_chatters"] = df["unique_chatters"].fillna(0).clip(lower=0)

    no_chat = df["chat_count"].eq(0)
    for c in ["avg_msg_len", "repeat_msg_ratio", "new_chatter_ratio"]:
        df[c] = df[c].mask(no_chat & df[c].isna(), 0)

    df = fill_metric(df, "avg_msg_len", "avg_qc")
    df = fill_metric(df, "repeat_msg_ratio", "rep_qc")
    df = fill_metric(df, "new_chatter_ratio", "new_qc")

    df["chat_per_viewer"] = np.where(df["viewer_count_last"].gt(0), df["chat_count"] / df["viewer_count_last"], np.nan)

    df = df.sort_values(KEY + ["minute_ts"]).reset_index(drop=True)
    df["delta_viewer_1m"] = df.groupby(KEY)["viewer_count_last"].diff()
    df["delta_chat_1m"] = df.groupby(KEY)["chat_count"].diff()
    df["session_key"] = df["run_id"].astype(str) + "_" + df["broad_no"].astype(str)
    return df


def split_minute(df):
    all_zero = df.groupby(KEY)["chat_count"].transform(lambda x: x.eq(0).all())

    minute_all = df.copy()
    minute_model = df.loc[~all_zero].copy()
    qc_zero = df.loc[all_zero].copy()

    qcols = [
        "source_file", "session_key", "run_id", "broad_no", "minute_ts",
        "v_qc", "v_edge", "v_miss_r", "avg_qc", "rep_qc", "new_qc"
    ]
    qcols = [c for c in qcols if c in df.columns]
    row_qc = df.loc[
        df["v_qc"].eq(1) | df["v_edge"].eq(1) | df["avg_qc"].eq(1) | df["rep_qc"].eq(1) | df["new_qc"].eq(1),
        qcols
    ].copy()

    return minute_all, minute_model, qc_zero, row_qc
