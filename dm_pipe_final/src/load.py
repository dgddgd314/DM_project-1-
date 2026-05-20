from pathlib import Path
import re
import numpy as np
import pandas as pd


def run_id_from_name(name):
    m = re.search(r"Run_(\d+)_Features", name)
    return int(m.group(1)) if m else None


def _min_of_day(ts):
    ts = pd.to_datetime(ts, errors="coerce").dt.floor("min")
    return ts.dt.hour * 60 + ts.dt.minute


def _parse_time(t):
    h, m = str(t).split(":")[:2]
    return int(h) * 60 + int(m)


def _parse_window(w):
    a, b = str(w).split("-")
    return _parse_time(a), _parse_time(b), str(w)


def _in_window(mins, start, end, tol):
    start = start - tol
    end = end + tol
    if start < 0:
        return (mins >= start + 1440) | (mins <= end)
    if end >= 1440:
        return (mins >= start) | (mins <= end - 1440)
    if start <= end:
        return (mins >= start) & (mins <= end)
    return (mins >= start) | (mins <= end)


def window_check(ts, cfg):
    ts = pd.to_datetime(ts, errors="coerce").dropna()
    windows = cfg.get("time", {}).get(
        "valid_windows",
        ["14:00-16:00", "17:00-19:00", "20:00-22:00", "23:00-01:00"],
    )
    tol = int(cfg.get("time", {}).get("tolerance_min", 1))

    if ts.empty:
        return {
            "time_ok": 0,
            "time_window": "no_valid_time",
            "off_window_rows": 0,
            "off_window_rate": np.nan,
        }

    mins = _min_of_day(ts)
    best_name, best_ok = "off_window", pd.Series(False, index=ts.index)
    for w in windows:
        start, end, name = _parse_window(w)
        ok = _in_window(mins, start, end, tol)
        if ok.mean() > best_ok.mean():
            best_name, best_ok = name, ok

    off = int((~best_ok).sum())
    return {
        "time_ok": int(off == 0),
        "time_window": best_name,
        "off_window_rows": off,
        "off_window_rate": float(off / len(ts)),
    }


def load_features(cfg):
    in_dir = Path(cfg["path"]["in_dir"])
    files = sorted(in_dir.glob(cfg["path"]["pattern"]))
    if not files:
        raise FileNotFoundError(f"no files: {in_dir / cfg['path']['pattern']}")

    shift_h = int(cfg.get("time", {}).get("shift_hours", 9))
    drop_runs = set(int(x) for x in cfg.get("time", {}).get("drop_runs", []))
    drop_off = bool(cfg.get("time", {}).get("drop_off_window", True))
    frames, audit = [], []

    for file in files:
        df = pd.read_excel(file)
        df.columns = [str(c).strip() for c in df.columns]
        df["source_file"] = file.name

        if "run_id" not in df.columns or df["run_id"].isna().all():
            df["run_id"] = run_id_from_name(file.name)

        df["run_id"] = pd.to_numeric(df["run_id"], errors="coerce")
        df["minute_ts"] = pd.to_datetime(df.get("minute_ts"), errors="coerce")
        raw_start, raw_end = df["minute_ts"].min(), df["minute_ts"].max()
        df["minute_ts"] = df["minute_ts"] + pd.Timedelta(hours=shift_h)

        rows_raw = len(df)
        df = df.dropna(subset=["run_id", "minute_ts"]).copy()
        df["run_id"] = df["run_id"].astype(int)
        run_id = run_id_from_name(file.name)
        if run_id is None and len(df):
            run_id = int(df["run_id"].iloc[0])

        w = window_check(df["minute_ts"], cfg)
        reason = "ok"
        use = len(df) > 0

        if run_id in drop_runs:
            use = False
            reason = "dropped_by_run_id"
        elif drop_off and not bool(w["time_ok"]):
            use = False
            reason = "off_window"
        elif not use:
            reason = "no_valid_rows"

        audit.append({
            "file": file.name,
            "use": int(use),
            "rows_raw": rows_raw,
            "rows_after_basic_clean": len(df),
            "rows_used": len(df) if use else 0,
            "run_id": run_id,
            "raw_start": raw_start,
            "raw_end": raw_end,
            "kst_start": df["minute_ts"].min() if len(df) else pd.NaT,
            "kst_end": df["minute_ts"].max() if len(df) else pd.NaT,
            "shift_hours": shift_h,
            **w,
            "reason": reason,
        })
        if use:
            frames.append(df)

    file_audit = pd.DataFrame(audit)
    if not frames:
        out = Path(cfg["path"]["out_dir"])
        out.mkdir(parents=True, exist_ok=True)
        file_audit.to_csv(out / "file_audit.csv", index=False, encoding="utf-8-sig")
        raise ValueError("no usable feature rows; see out/file_audit.csv")

    raw = pd.concat(frames, ignore_index=True)
    used = (
        raw.groupby("run_id")
           .agg(rows=("run_id", "size"), start=("minute_ts", "min"), end=("minute_ts", "max"), files=("source_file", "nunique"))
           .reset_index()
           .sort_values("run_id")
    )
    checks = used.apply(lambda r: pd.Series(window_check(pd.Series([r["start"], r["end"]]), cfg)), axis=1)
    used = pd.concat([used, checks], axis=1)
    return raw, file_audit, used
