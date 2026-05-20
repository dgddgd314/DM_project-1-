from pathlib import Path
import yaml
import numpy as np
import pandas as pd

from src.session import make_session
from src.cluster import add_cluster
from src.detect import add_detectors
from src.synthetic import make_synthetic
from src.model import add_model_scores
from src.docs import write_score_doc
from src.plots import make_plots
from src.prep import id_str

KEY = ["run_id", "broad_no"]
NUM_COLS = [
    "viewer_count_last", "chat_count", "unique_chatters", "avg_msg_len",
    "repeat_msg_ratio", "new_chatter_ratio", "chat_per_viewer",
    "delta_viewer_1m", "delta_chat_1m"
]


def _as_numeric(df, cols):
    for c in cols:
        if c not in df.columns:
            df[c] = np.nan
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


def normalize_saved_minute(df, cfg):
    """Normalize saved minute CSVs before rebuilding session_summary_processed.csv."""
    df = df.copy()
    if "minute_ts" not in df.columns:
        raise ValueError("minute CSV must contain minute_ts")
    if not set(KEY).issubset(df.columns):
        raise ValueError("minute CSV must contain run_id and broad_no")

    df["minute_ts"] = pd.to_datetime(df["minute_ts"], errors="coerce")
    df["run_id"] = pd.to_numeric(df["run_id"], errors="coerce").astype("Int64")
    df["broad_no"] = id_str(df["broad_no"])
    df = df.dropna(subset=["run_id", "broad_no", "minute_ts"]).copy()
    df["run_id"] = df["run_id"].astype(int)
    df = _as_numeric(df, NUM_COLS)

    if "user_id" not in df.columns:
        df["user_id"] = "UNKNOWN_USER"
    df["user_id"] = df.groupby(KEY)["user_id"].transform(lambda s: s.ffill().bfill()).fillna("UNKNOWN_USER")
    if "category_id" not in df.columns:
        df["category_id"] = "UNKNOWN_CAT"
    df["category_id"] = df.groupby(KEY)["category_id"].transform(lambda s: s.ffill().bfill()).fillna("UNKNOWN_CAT")

    df = df.sort_values(KEY + ["minute_ts"]).reset_index(drop=True)
    if "session_key" not in df.columns:
        df["session_key"] = df["run_id"].astype(str) + "_" + df["broad_no"].astype(str)

    df["viewer_count_last"] = df["viewer_count_last"].mask(df["viewer_count_last"].lt(0))
    if cfg["prep"].get("zero_viewer_na", True):
        df["viewer_count_last"] = df["viewer_count_last"].mask(df["viewer_count_last"].eq(0))
    df["viewer_count_last"] = df.groupby(KEY)["viewer_count_last"].transform(lambda s: s.interpolate(method="linear", limit_direction="both"))
    df["chat_count"] = df["chat_count"].fillna(0).clip(lower=0)
    df["unique_chatters"] = df["unique_chatters"].fillna(0).clip(lower=0)
    no_chat = df["chat_count"].eq(0)
    for c in ["avg_msg_len", "repeat_msg_ratio", "new_chatter_ratio"]:
        df[c] = df[c].mask(no_chat & df[c].isna(), 0)
        med = df.groupby(KEY)[c].transform("median")
        df[c] = df[c].fillna(med).fillna(0)

    df["chat_per_viewer"] = np.where(df["viewer_count_last"].gt(0), df["chat_count"] / df["viewer_count_last"], np.nan)
    df["delta_viewer_1m"] = df.groupby(KEY)["viewer_count_last"].diff()
    df["delta_chat_1m"] = df.groupby(KEY)["chat_count"].diff()

    n = df.groupby(KEY)["viewer_count_last"].transform("size")
    miss = df.groupby(KEY)["viewer_count_last"].transform(lambda s: s.isna().sum())
    df["v_miss_r"] = miss / n
    df["v_qc"] = (miss == n).astype(int)
    df["v_edge"] = 0
    return df


def main(cfg_path="cfg.yml"):
    cfg = yaml.safe_load(open(cfg_path, encoding="utf-8"))
    out = Path(cfg["path"]["out_dir"])

    minute_all = normalize_saved_minute(pd.read_csv(out / "minute_all.csv", encoding="utf-8-sig"), cfg)
    minute_model = normalize_saved_minute(pd.read_csv(out / "minute_model.csv", encoding="utf-8-sig"), cfg)

    session_all, session_model, session_qc = make_session(minute_all, minute_model, cfg)
    session_model = add_cluster(session_model, out, cfg)
    session_model = add_detectors(session_model, out, cfg)

    syn_train = make_synthetic(minute_model, session_model, out, cfg)
    model_scores = add_model_scores(syn_train, session_model, out, cfg)
    if not model_scores.empty:
        session_model = session_model.merge(model_scores, on="session_key", how="left")

    session_all.to_csv(out / "session_all.csv", index=False, encoding="utf-8-sig")
    session_qc.to_csv(out / "session_qc.csv", index=False, encoding="utf-8-sig")
    session_model.to_csv(out / "session_summary_processed.csv", index=False, encoding="utf-8-sig")
    write_score_doc(out, cfg, session_model=session_model, syn_train=syn_train, model_scores=model_scores)
    make_plots(minute_all, minute_model, session_all, session_model, out)
    print("saved out/session_summary_processed.csv")


if __name__ == "__main__":
    main()
