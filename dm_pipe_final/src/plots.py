from pathlib import Path
import warnings
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.lines import Line2D
from matplotlib.ticker import FormatStrFormatter

warnings.filterwarnings("ignore")
_available_fonts = {f.name for f in font_manager.fontManager.ttflist}
plt.rcParams["font.family"] = "Malgun Gothic" if "Malgun Gothic" in _available_fonts else "DejaVu Sans"
plt.rcParams["axes.unicode_minus"] = False
plt.rcParams["axes.formatter.use_mathtext"] = False

KEY = ["run_id", "broad_no"]
DPI = 200


def _save(fig, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=DPI, bbox_inches="tight")
    plt.close(fig)


def _blank(path, msg):
    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.text(0.5, 0.5, msg, ha="center", va="center", fontsize=13)
    ax.axis("off")
    _save(fig, path)


def _table(df, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    out = df.copy()
    for c in out.columns:
        if pd.api.types.is_float_dtype(out[c]):
            out[c] = out[c].round(3)
    out.to_csv(path, index=False, encoding="utf-8-sig")


def _plot_df(minute):
    p = minute.copy()
    if p.empty:
        return p
    p["minute_ts"] = pd.to_datetime(p["minute_ts"], errors="coerce")
    p = p.sort_values(KEY + ["minute_ts"]).reset_index(drop=True)
    p["viewer_log"] = np.log1p(p["viewer_count_last"].clip(lower=0))
    p["chat_log"] = np.log1p(p["chat_count"].clip(lower=0))
    p["unique_log"] = np.log1p(p["unique_chatters"].clip(lower=0))
    p["gap"] = p["viewer_log"] - p["chat_log"]
    p["zero_chat"] = p["chat_count"].eq(0)
    p["minute_idx"] = p.groupby(KEY).cumcount() + 1
    p["session_id"] = p["run_id"].astype(str) + "_" + p["broad_no"].astype(str)
    if "delta_viewer_1m" not in p.columns:
        p["delta_viewer_1m"] = p.groupby(KEY)["viewer_count_last"].diff()
    if "delta_chat_1m" not in p.columns:
        p["delta_chat_1m"] = p.groupby(KEY)["chat_count"].diff()
    p["unique_delta_1m"] = p.groupby(KEY)["unique_chatters"].diff()
    block = p.groupby(KEY)["zero_chat"].transform(lambda x: x.ne(x.shift()).cumsum())
    p["zrun"] = p["zero_chat"].groupby([p["run_id"], p["broad_no"], block]).cumcount().add(1).where(p["zero_chat"], 0).astype(int)
    return p


def _std_sess(s):
    d = s.copy()
    rename = {
        "viewer_med": "median_viewer",
        "chat_mean": "mean_chat",
        "unique_mean": "mean_unique",
        "zero_rate": "zero_chat_rate",
        "gap_med": "median_gap",
        "gap_max": "max_gap",
        "zrun_max": "max_zero_run",
        "cluster_number": "kmeans",
    }
    for a, b in rename.items():
        if a in d.columns and b not in d.columns:
            d[b] = d[a]
    return d


def _size_gap(d):
    if "max_gap" in d.columns:
        return (d["max_gap"].fillna(0).clip(lower=0) * 30).clip(lower=22, upper=280)
    return pd.Series(45, index=d.index)


def _size_zrun(d):
    if "max_zero_run" in d.columns:
        return (45 + 25 * np.log1p(d["max_zero_run"].fillna(0).clip(lower=0))).clip(35, 180)
    return pd.Series(45, index=d.index)


def _label_top(ax, d, score=None, n=5):
    if d.empty:
        return
    if score and score in d.columns:
        d = d.sort_values(score, ascending=False).head(n)
    else:
        d = d.sort_values(["zero_chat_rate", "median_gap"], ascending=False).head(n)
    for _, r in d.iterrows():
        ax.annotate(
            f"r{int(r['run_id'])}\nb{str(r['broad_no'])[-4:]}",
            (r["median_viewer"], r["median_gap"]),
            xytext=(5, 5), textcoords="offset points",
            fontsize=8, weight="bold", color="black", alpha=0.85,
        )


def _add_size_legend(ax):
    vals = [4, 6, 8]
    handles = [plt.scatter([], [], s=v * 30, c="gray", edgecolors="black", alpha=.7) for v in vals]
    ax.legend(handles, [str(v) for v in vals], title="max_gap(size)", loc="lower right", frameon=True)


def _base_map(ax, d, title, flag=None, score=None, label="flag"):
    d = _std_sess(d).dropna(subset=["median_viewer", "median_gap"]).copy()
    if d.empty:
        ax.text(.5, .5, "no session", ha="center", va="center")
        ax.axis("off")
        return None

    if flag is None:
        flag = pd.Series(False, index=d.index)
    flag = flag.reindex(d.index).fillna(False)
    bg = d.loc[~flag]
    fg = d.loc[flag]

    sc = ax.scatter(
        bg["median_viewer"], bg["median_gap"],
        s=_size_gap(bg), c=bg["zero_chat_rate"], cmap="viridis", vmin=0, vmax=1,
        alpha=0.25, edgecolor="none",
    )
    ax.scatter(
        fg["median_viewer"], fg["median_gap"],
        s=_size_gap(fg), c=fg["zero_chat_rate"], cmap="viridis", vmin=0, vmax=1,
        alpha=0.9, edgecolor="red", linewidth=1.1, label=label,
    )
    if len(fg):
        _label_top(ax, fg, score)
        ax.legend(loc="upper right", frameon=True)
    ax.set_title(title)
    ax.set_xscale("log")
    ax.set_xlabel("median_viewer (log scale)")
    ax.set_ylabel("median_gap")
    ax.grid(True, alpha=0.2)
    return sc


def _flag_by_label_or_rank(d, score, lab=None, top=.05):
    if lab and lab in d.columns and d[lab].notna().any():
        return d[lab].eq(-1)
    if score in d.columns and d[score].notna().any():
        return d[score].ge(d[score].quantile(1 - top))
    return pd.Series(False, index=d.index)


def _cluster_map(ax, d, col, title):
    d = _std_sess(d).dropna(subset=["median_viewer", "median_gap"]).copy()
    if d.empty or col not in d.columns or d[col].isna().all():
        ax.text(.5, .5, f"{title}\nnot available", ha="center", va="center")
        ax.axis("off")
        return
    vals = sorted(d[col].dropna().unique(), key=lambda x: float(x))
    cmap = plt.get_cmap("tab10")
    color_map = {v: cmap(i % 10) for i, v in enumerate(vals)}
    for v in vals:
        part = d[d[col].eq(v)]
        lab = "-1 noise" if str(v) == "-1" else str(int(v)) if float(v).is_integer() else str(v)
        ax.scatter(
            part["median_viewer"], part["median_gap"],
            s=_size_zrun(part), c=[color_map[v]], alpha=0.75,
            edgecolor="white", linewidth=0.5, label=lab,
        )
    ax.set_xscale("log")
    ax.set_title(title)
    ax.set_xlabel("median_viewer (log scale)")
    ax.set_ylabel("median_gap")
    ax.grid(True, alpha=0.2)
    ax.legend(loc="upper left", title=col, frameon=True, fontsize=8)


def _quality_tables(session_all, session_model, tables):
    all_zero = int(session_all.get("all_zero", pd.Series(False, index=session_all.index)).sum())
    tables["quality_table.csv"] = pd.DataFrame([
        {"item": "all_sessions", "value": len(session_all), "note": "including all-zero chat"},
        {"item": "all_zero_sessions", "value": all_zero, "note": "saved as QC bucket"},
        {"item": "behavior_sessions", "value": int((~session_all.get("all_zero", pd.Series(False, index=session_all.index))).sum()), "note": "all-zero excluded"},
        {"item": "model_sessions", "value": len(session_model), "note": "eligible for clustering/modeling"},
    ])
    if len(session_model):
        tables["metric_table.csv"] = pd.DataFrame([
            {"metric": "median_viewer", "median": session_model["viewer_med"].median(), "q1": session_model["viewer_med"].quantile(.25), "q3": session_model["viewer_med"].quantile(.75)},
            {"metric": "mean_chat_per_min", "median": session_model["chat_mean"].median(), "q1": session_model["chat_mean"].quantile(.25), "q3": session_model["chat_mean"].quantile(.75)},
            {"metric": "median_gap", "median": session_model["gap_med"].median(), "q1": session_model["gap_med"].quantile(.25), "q3": session_model["gap_med"].quantile(.75)},
            {"metric": "zero_chat_rate", "median": session_model["zero_rate"].median(), "q1": session_model["zero_rate"].quantile(.25), "q3": session_model["zero_rate"].quantile(.75)},
        ])


def _plot_quality(p, session_all, session_model, plots):
    if p.empty:
        _blank(plots / "01_data_quality.png", "no minute data")
        return
    fig, ax = plt.subplots(2, 2, figsize=(13, 8), constrained_layout=True)
    ax = ax.ravel()

    all_zero = int(session_all.get("all_zero", pd.Series(False, index=session_all.index)).sum())
    counts = [len(session_all), all_zero, len(session_model)]
    names = ["all\nsessions", "all-zero\nsessions", "modeling\nsessions"]
    ax[0].bar(names, counts, edgecolor="black")
    for i, v in enumerate(counts):
        ax[0].text(i, v, str(v), ha="center", va="bottom")
    ax[0].set_title("Session filtering")
    ax[0].set_ylabel("count")
    ax[0].grid(axis="y", alpha=.25)

    nonzero = p.groupby(KEY)["chat_count"].apply(lambda x: x.ne(0).mean() * 100)
    ax[1].hist(nonzero, bins=15, edgecolor="black")
    ax[1].set_title("Session non-zero chat ratio")
    ax[1].set_xlabel("non-zero chat ratio (%)")
    ax[1].set_ylabel("sessions")
    ax[1].grid(axis="y", alpha=.25)

    z = p.loc[p["zero_chat"], "zrun"].value_counts().sort_index().head(25)
    ax[2].bar(z.index.astype(str), z.values)
    ax[2].set_title("Consecutive zero-chat run")
    ax[2].set_xlabel("zero-run length")
    ax[2].set_ylabel("count (log scale)")
    ax[2].set_yscale("log")
    ax[2].tick_params(axis="x", rotation=45)
    ax[2].grid(axis="y", alpha=.25)

    tmp = p.dropna(subset=["viewer_count_last"]).copy()
    if len(tmp) >= 10:
        tmp["viewer_bin"] = pd.qcut(tmp["viewer_count_last"].rank(method="first"), 10, labels=False, duplicates="drop")
        by_bin = tmp.groupby("viewer_bin")["zero_chat"].mean()
        ax[3].bar(by_bin.index.astype(str), by_bin.values)
    ax[3].set_title("Zero-chat rate by viewer decile")
    ax[3].set_xlabel("viewer decile")
    ax[3].set_ylabel("zero-chat rate")
    ax[3].set_ylim(0, 1)
    ax[3].grid(axis="y", alpha=.25)
    fig.suptitle("Data quality and zero-chat diagnostics", fontsize=15)
    _save(fig, plots / "01_data_quality.png")


def _plot_dist_time(p, plots):
    if p.empty:
        _blank(plots / "02_dist_time.png", "no minute data")
        return
    agg = p.groupby("minute_idx").agg(
        viewer_med=("viewer_count_last", "median"), viewer_q1=("viewer_count_last", lambda x: x.quantile(.25)), viewer_q3=("viewer_count_last", lambda x: x.quantile(.75)),
        gap_med=("gap", "median"), gap_q1=("gap", lambda x: x.quantile(.25)), gap_q3=("gap", lambda x: x.quantile(.75)),
        n=("session_id", "nunique"),
    ).reset_index()

    fig, ax = plt.subplots(2, 2, figsize=(13, 8), constrained_layout=True)
    ax[0, 0].hist(p["gap"].dropna(), bins="sturges", edgecolor="black")
    ax[0, 0].set_title("viewer-chat log gap distribution")
    ax[0, 0].set_xlabel("log1p(viewer) - log1p(chat)")
    ax[0, 0].set_ylabel("count")
    ax[0, 0].grid(axis="y", alpha=.25)

    ax[0, 1].hist(p["chat_log"].dropna(), bins="sturges", edgecolor="black")
    ax[0, 1].set_title("chat_count log distribution")
    ax[0, 1].set_xlabel("log1p(chat_count)")
    ax[0, 1].set_ylabel("count")
    ax[0, 1].grid(axis="y", alpha=.25)

    ax[1, 0].fill_between(agg["minute_idx"], agg["viewer_q1"], agg["viewer_q3"], color="tab:blue", alpha=.2, label="IQR")
    ax[1, 0].plot(agg["minute_idx"], agg["viewer_med"], color="tab:blue", lw=2, label="median")
    ax[1, 0].set_title("Session trajectory: viewer")
    ax[1, 0].set_xlabel("minute_idx")
    ax[1, 0].set_ylabel("viewer_count_last")
    ax[1, 0].grid(alpha=.2)
    ax[1, 0].legend(loc="upper left")

    ax[1, 1].fill_between(agg["minute_idx"], agg["gap_q1"], agg["gap_q3"], color="tab:blue", alpha=.2, label="IQR")
    ax[1, 1].plot(agg["minute_idx"], agg["gap_med"], color="tab:blue", lw=2, label="median")
    ax[1, 1].bar(agg["minute_idx"], agg["n"] / max(agg["n"].max(), 1), color="gray", alpha=.22, label="surviving N scaled")
    ax[1, 1].set_title("Session trajectory: viewer-chat gap")
    ax[1, 1].set_xlabel("minute_idx")
    ax[1, 1].set_ylabel("gap")
    ax[1, 1].grid(alpha=.2)
    ax[1, 1].legend(loc="upper left")
    fig.suptitle("Distribution and time structure", fontsize=15)
    _save(fig, plots / "02_dist_time.png")


def _plot_view_chat(p, plots, tables):
    if p.empty:
        _blank(plots / "03_view_chat.png", "no minute data")
        return
    fig, ax = plt.subplots(1, 3, figsize=(17, 5), constrained_layout=True)

    hb = ax[0].hexbin(p["chat_log"], p["viewer_log"], gridsize=50, cmap="Blues", mincnt=1, bins="log")
    fig.colorbar(hb, ax=ax[0], label="log(count)")
    ax[0].set_title("viewer_log vs chat_log")
    ax[0].set_xlabel("chat_log")
    ax[0].set_ylabel("viewer_log")

    m = p[["delta_viewer_1m", "delta_chat_1m"]].dropna()
    if len(m):
        qv = m["delta_viewer_1m"].quantile([.01, .99])
        qc = m["delta_chat_1m"].quantile([.01, .99])
        ax[1].scatter(m["delta_viewer_1m"], m["delta_chat_1m"], s=1, alpha=.05)
        ax[1].set_xlim(qv.iloc[0], qv.iloc[1])
        ax[1].set_ylim(qc.iloc[0], qc.iloc[1])
    ax[1].axhline(0, ls="--", color="red", alpha=.5)
    ax[1].axvline(0, ls="--", color="red", alpha=.5)
    ax[1].set_title("1-minute viewer vs chat change")
    ax[1].set_xlabel("delta_viewer_1m")
    ax[1].set_ylabel("delta_chat_1m")
    ax[1].grid(alpha=.2)

    base = p.sort_values(KEY + ["minute_ts"])
    rows = []
    for lag in range(11):
        tmp = base.copy()
        tmp["chat_next"] = tmp.groupby(KEY)["delta_chat_1m"].shift(-lag)
        tmp["unique_next"] = tmp.groupby(KEY)["unique_delta_1m"].shift(-lag)
        vc = tmp[["delta_viewer_1m", "chat_next"]].dropna()
        vu = tmp[["delta_viewer_1m", "unique_next"]].dropna()
        rows.append({
            "lag_min": lag,
            "chat_spearman": vc["delta_viewer_1m"].corr(vc["chat_next"], method="spearman") if len(vc) else np.nan,
            "unique_spearman": vu["delta_viewer_1m"].corr(vu["unique_next"], method="spearman") if len(vu) else np.nan,
        })
    lag = pd.DataFrame(rows)
    tables["lag_corr.csv"] = lag
    ax[2].plot(lag["lag_min"], lag["chat_spearman"], marker="o", label="viewer delta -> chat delta")
    ax[2].plot(lag["lag_min"], lag["unique_spearman"], marker="o", label="viewer delta -> unique delta")
    ax[2].axhline(0, ls="--", lw=1)
    ax[2].set_title("Lag response after viewer change")
    ax[2].set_xlabel("lag (minutes)")
    ax[2].set_ylabel("Spearman correlation")
    ax[2].grid(alpha=.3)
    ax[2].legend()
    fig.suptitle("Viewer-chat dynamics", fontsize=15)
    _save(fig, plots / "03_view_chat.png")

    pairs = [
        ("viewer_log", "chat_log"),
        ("viewer_log", "unique_log"),
        ("delta_viewer_1m", "delta_chat_1m"),
        ("chat_log", "gap"),
    ]
    tables["corr_table.csv"] = pd.DataFrame([
        {"pair": f"{a} vs {b}", "pearson": p[a].corr(p[b], method="pearson"), "spearman": p[a].corr(p[b], method="spearman")}
        for a, b in pairs if a in p.columns and b in p.columns
    ])


def _plot_cluster(s, out, plots, tables):
    d = _std_sess(s)
    if d.empty:
        _blank(plots / "04_cluster.png", "no session data")
        return
    fig, ax = plt.subplots(2, 3, figsize=(17, 10), constrained_layout=True)

    sel = pd.read_csv(Path(out) / "cluster_select.csv") if Path(out, "cluster_select.csv").exists() else pd.DataFrame()
    if not sel.empty:
        ax[0, 0].plot(sel["k"], sel["silhouette"], marker="o")
    ax[0, 0].set_title("KMeans selection")
    ax[0, 0].set_xlabel("K")
    ax[0, 0].set_ylabel("silhouette")
    ax[0, 0].grid(alpha=.25)

    _cluster_map(ax[0, 1], d, "kmeans", "KMeans session type map")

    prof = d.groupby("kmeans").agg(n=("session_key", "size"), viewer=("median_viewer", "median"), chat=("mean_chat", "mean"), zero=("zero_chat_rate", "mean"), gap=("median_gap", "median"), zrun=("max_zero_run", "median")).reset_index() if "kmeans" in d else pd.DataFrame()
    if not prof.empty:
        tables["cluster_profile.csv"] = prof
        mat = prof.set_index("kmeans")[["n", "viewer", "chat", "zero", "gap", "zrun"]]
        scaled = (mat - mat.min()) / (mat.max() - mat.min()).replace(0, 1)
        im = ax[0, 2].imshow(scaled.values, cmap="viridis", aspect="auto", vmin=0, vmax=1)
        ax[0, 2].set_xticks(range(len(mat.columns)), mat.columns, rotation=35, ha="right")
        ax[0, 2].set_yticks(range(len(mat.index)), [str(int(x)) for x in mat.index])
        for i in range(mat.shape[0]):
            for j in range(mat.shape[1]):
                ax[0, 2].text(j, i, f"{mat.iloc[i, j]:.2f}", ha="center", va="center", fontsize=7, color="white" if scaled.iloc[i, j] < .45 else "black")
        ax[0, 2].set_title("KMeans profile")
        fig.colorbar(im, ax=ax[0, 2], shrink=.8)
    else:
        ax[0, 2].axis("off")

    gmm = pd.read_csv(Path(out) / "gmm_select.csv") if Path(out, "gmm_select.csv").exists() else pd.DataFrame()
    if not gmm.empty:
        x = "n_components" if "n_components" in gmm.columns else "n"
        ax[1, 0].plot(gmm[x], gmm["bic"], marker="o", label="BIC")
        if "aic" in gmm:
            ax[1, 0].plot(gmm[x], gmm["aic"], marker="o", label="AIC")
        ax[1, 0].legend()
    ax[1, 0].set_title("GMM component selection")
    ax[1, 0].set_xlabel("n_components")
    ax[1, 0].set_ylabel("criterion (lower better)")
    ax[1, 0].grid(alpha=.25)

    _cluster_map(ax[1, 1], d, "gmm", "GMM robustness map")
    _cluster_map(ax[1, 2], d, "hdbscan", "HDBSCAN density map")
    fig.suptitle("Clustering summary: KMeans main, GMM/HDBSCAN checks", fontsize=15)
    _save(fig, plots / "04_cluster.png")


def _plot_detectors(s, plots):
    d = _std_sess(s)
    if d.empty:
        _blank(plots / "05_detectors.png", "no session data")
        return
    specs = [
        ("if_score", "if_lab", "IsolationForest"),
        ("lof_score", "lof_lab", "LOF"),
        ("ocsvm_score", "ocsvm_lab", "OneClassSVM"),
    ]
    fig, ax = plt.subplots(1, 3, figsize=(17, 5.4), constrained_layout=True)
    sc = None
    for a, (score, lab, title) in zip(ax, specs):
        flag = _flag_by_label_or_rank(d, score, lab)
        sc = _base_map(a, d, title, flag=flag, score=score, label=f"{title} flag")
    if sc is not None:
        fig.colorbar(sc, ax=ax, label="zero_chat_rate", shrink=.82)
    fig.suptitle("Unsupervised detector review maps", fontsize=15)
    _save(fig, plots / "05_detectors.png")


def _plot_models(s, plots):
    d = _std_sess(s)
    specs = [
        ("ae_score", "AutoEncoder"),
        ("svm_syn_score", "Synthetic SVM"),
        ("xgb_syn_score", "Synthetic XGBoost"),
        ("lgb_syn_score", "Synthetic LightGBM"),
    ]
    specs = [(c, t) for c, t in specs if c in d.columns and d[c].notna().sum() > 0]
    if not specs:
        _blank(plots / "06_models.png", "no model score available")
        return
    n = len(specs)
    rows, cols = (2, 2) if n > 2 else (1, n)
    fig, ax = plt.subplots(rows, cols, figsize=(14 if cols == 2 else 8 * cols, 9 if rows == 2 else 5.2), constrained_layout=True)
    axes = np.array(ax).reshape(-1)
    sc = None
    for a, (score, title) in zip(axes, specs):
        flag = _flag_by_label_or_rank(d, score, None)
        sc = _base_map(a, d, title, flag=flag, score=score, label=f"{title} top")
    for a in axes[len(specs):]:
        a.axis("off")
    if sc is not None:
        fig.colorbar(sc, ax=axes[:len(specs)], label="zero_chat_rate", shrink=.82)
    fig.suptitle("Model-based score review maps", fontsize=15)
    _save(fig, plots / "06_models.png")

    if "pu_score" in d.columns and d["pu_score"].notna().sum() > 0:
        fig, ax = plt.subplots(figsize=(8, 5.5))
        flag = _flag_by_label_or_rank(d, "pu_score", None)
        sc = _base_map(ax, d, "PU score", flag=flag, score="pu_score", label="PU top")
        if sc is not None:
            fig.colorbar(sc, ax=ax, label="zero_chat_rate")
        _save(fig, plots / "07_pu.png")


def _write_tables(tables, out):
    table_dir = Path(out) / "tables"
    table_dir.mkdir(parents=True, exist_ok=True)
    for name, df in tables.items():
        _table(df, table_dir / name)
    if tables:
        with pd.ExcelWriter(table_dir / "eda_tables.xlsx", engine="openpyxl") as writer:
            for name, df in tables.items():
                df.to_excel(writer, sheet_name=Path(name).stem[:31], index=False)


def _write_plot_doc(out, manifest):
    lines = [
        "Plot 자동 생성 기록",
        "====================",
        "이 파일은 make_plots() 실행 시 out/plots/*.png와 함께 자동 생성된다.",
        "그래프 구성은 기존 EDA notebook의 발표용 핵심 plot 흐름을 유지하되, overlay/중복 plot은 줄였다.",
        "",
        "공통 스타일",
        "----------",
        "저장: dpi=200, bbox_inches='tight'",
        "폰트: Malgun Gothic 우선, DejaVu Sans fallback, unicode minus 보정",
        "grid: alpha 0.2~0.3",
        "session map 좌표: x=median_viewer(log scale), y=median_gap",
        "session map 색: zero_chat_rate 또는 cluster label",
        "session map 점 크기: 기존 notebook 방식 유지 - max_gap*30 또는 45+25*log1p(max_zero_run)",
        "detector/model overlay: 일반 session은 alpha=0.25, flag/top session은 red edge와 alpha=0.9",
        "",
        "생성 plot",
        "---------",
    ]
    if manifest:
        lines.extend(f"- {name}" for name in manifest)
    else:
        lines.append("- no png generated")
    lines += [
        "",
        "주요 파일 해석",
        "------------",
        "01_data_quality.png: 세션 필터링, zero-chat 품질 진단",
        "02_dist_time.png: gap/chat 분포와 시간 경과별 median/IQR trajectory",
        "03_view_chat.png: viewer-chat 관계, 1분 변화량, lag response",
        "04_cluster.png: KMeans 선택/지도, profile, GMM/HDBSCAN robustness map",
        "05_detectors.png: IF/LOF/OCSVM 비지도 detector별 review map",
        "06_models.png: AE/Synthetic supervised model score별 review map",
        "07_pu.png: manual positive label이 있을 때만 생성되는 PU score map",
    ]
    Path(out, "plot_guide.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")


def make_plots(minute_all, minute_model, session_all, session_model, out):
    out = Path(out)
    plots = out / "plots"
    plots.mkdir(parents=True, exist_ok=True)
    for old in plots.glob("*.png"):
        old.unlink()
    old_cluster = out / "cluster.png"
    if old_cluster.exists():
        old_cluster.unlink()

    tables = {}
    p = _plot_df(minute_model)
    s = session_model.copy()

    _quality_tables(session_all, s, tables)
    _plot_quality(p, session_all, s, plots)
    _plot_dist_time(p, plots)
    _plot_view_chat(p, plots, tables)
    _plot_cluster(s, out, plots, tables)
    _plot_detectors(s, plots)
    _plot_models(s, plots)

    _write_tables(tables, out)
    manifest = sorted(str(p.relative_to(out)) for p in plots.glob("*.png"))
    pd.DataFrame({"plot_file": manifest}).to_csv(out / "plot_manifest.csv", index=False, encoding="utf-8-sig")
    _write_plot_doc(out, manifest)
