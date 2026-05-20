import os
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
os.environ.setdefault("NUMEXPR_NUM_THREADS", "1")
from pathlib import Path
import yaml
import pandas as pd

from src.load import load_features
from src.prep import prep_minute, split_minute, minute_cols
from src.session import make_session
from src.cluster import add_cluster
from src.detect import add_detectors
from src.synthetic import make_synthetic
from src.model import add_model_scores
from src.docs import write_score_doc
from src.plots import make_plots


def save(df, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False, encoding="utf-8-sig")
    print(f"saved {path} {df.shape}")


def main(cfg_path="cfg.yml"):
    cfg = yaml.safe_load(open(cfg_path, encoding="utf-8"))
    out = Path(cfg["path"]["out_dir"])
    out.mkdir(parents=True, exist_ok=True)

    raw, file_audit, used_windows = load_features(cfg)
    save(file_audit, out / "file_audit.csv")
    save(used_windows, out / "used_windows.csv")

    minute_full = prep_minute(raw, cfg)
    minute_all, minute_model, qc_zero, row_qc = split_minute(minute_full)

    save(minute_all[minute_cols(minute_all)], out / "minute_all.csv")
    save(minute_model[minute_cols(minute_model)], out / "minute_model.csv")
    save(qc_zero[minute_cols(qc_zero)], out / "qc_zero.csv")
    save(row_qc, out / "row_qc.csv")

    session_all, session_model, session_qc = make_session(minute_all, minute_model, cfg)
    save(session_all, out / "session_all.csv")
    save(session_qc, out / "session_qc.csv")

    session_model = add_cluster(session_model, out, cfg)
    session_model = add_detectors(session_model, out, cfg)

    syn_train = make_synthetic(minute_model, session_model, out, cfg)
    model_scores = add_model_scores(syn_train, session_model, out, cfg)

    if not model_scores.empty:
        session_model = session_model.merge(model_scores, on="session_key", how="left")

    save(session_model, out / "session_summary_processed.csv")
    write_score_doc(out, cfg, session_model=session_model, syn_train=syn_train, model_scores=model_scores)
    make_plots(minute_all, minute_model, session_all, session_model, out)


if __name__ == "__main__":
    main()
