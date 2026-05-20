import os
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
os.environ.setdefault("NUMEXPR_NUM_THREADS", "1")
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from sklearn.preprocessing import RobustScaler
from sklearn.cluster import KMeans
try:
    from sklearn.cluster import HDBSCAN
except Exception:
    HDBSCAN = None
from sklearn.metrics import silhouette_score
from sklearn.mixture import GaussianMixture
import joblib


FEATS = ["log_viewer", "log_chat", "log_unique", "zero_rate", "gap_med", "log_zrun"]
ASSIGN_COLS = ["session_key", "run_id", "broad_no", "cluster_number", "gmm", "hdbscan", "hdbscan_noise"]
CLUSTER_COLORS = ["#1B9E77", "#D95F02", "#7570B3", "#E7298A", "#66A61E", "#E6AB02", "#A6761D", "#666666"]
EDGE_COLOR = "#222222"


def _cluster_color(i):
    return CLUSTER_COLORS[i % len(CLUSTER_COLORS)]


def make_x(df, feats=FEATS):
    x = df[feats].replace([np.inf, -np.inf], np.nan)
    return x.fillna(x.median(numeric_only=True)).fillna(0)


def write_doc(out, cfg, k_min, k_max, best_k, gmm_note="", hdb_note="", note=""):
    txt = [
        "클러스터링 자동 설정 기록",
        "========================",
        "이 파일은 add_cluster() 실행 시 현재 cfg.yml과 실제 session 수를 기준으로 생성됨.",
        "목적: 방송 세션의 viewer-chat 행동 유형을 분류한다. 뷰봇 정답 라벨 생성용이 아니다.",
        "",
        "공통 입력",
        "---------",
        "입력 데이터: session_model = session_all 중 min_n 이상, viewer QC 통과, all-zero chat 제외 세션",
        "분석 단위: session = run_id + broad_no",
        f"사용 feature: {', '.join(FEATS)}",
        "feature 처리: inf/-inf -> NaN, feature median 대체, 잔여 NaN은 0 대체",
        "스케일링: RobustScaler",
        "모델 입력값: RobustScaler.fit_transform(cluster_features)",
        "",
        "1) KMeans main clustering",
        "-------------------------",
        f"K 후보: {k_min}..{k_max}",
        f"선택된 K: {best_k}",
        "K 선택 기준: silhouette 최대, 동률이면 더 작은 K",
        f"hyperparameter: n_clusters={best_k}, random_state={cfg['cluster']['seed']}, n_init={cfg['cluster']['n_init']}",
        "출력 컬럼: cluster_number",
        "",
        "2) GMM robustness check",
        "------------------------",
        "역할: KMeans와 다른 확률적 mixture 관점에서 세션 유형 구조가 비슷한지 확인",
        "n_components 후보: 2..min(6, n_session-1)",
        "선택 기준: BIC 최소, 동률이면 작은 n_components",
        f"선택된 GMM components: {gmm_note}",
        "hyperparameter: covariance_type='full', n_init=10, random_state=cluster.seed",
        "출력 컬럼: gmm",
        "",
        "3) HDBSCAN density check",
        "------------------------",
        "역할: 미리 K를 정하지 않는 밀도 기반 관점에서 noise와 cluster 구조를 확인",
        "min_cluster_size 후보: cfg.hdbscan.min_sizes",
        "min_samples: max(2, min_cluster_size//2)",
        "선택 기준: balanced_score=silhouette*(1-noise_ratio), 유효 해가 없으면 noise_ratio 최소",
        f"선택된 HDBSCAN min_cluster_size: {hdb_note}",
        "출력 컬럼: hdbscan, hdbscan_noise",
        "",
        "저장 파일",
        "---------",
        "out/cluster_select.csv: KMeans K 선택 과정",
        "out/gmm_select.csv: GMM component 선택 과정",
        "out/hdbscan_select.csv: HDBSCAN min_cluster_size 선택 과정",
        "out/cluster_profile.csv: cluster별 요약 profile",
        "out/cluster_assignments.csv: session_key별 cluster_number/gmm/hdbscan 결과",
        "out/plots/04_cluster.png: 발표용 clustering summary plot",
        "",
        "시각화 스타일",
        "-------------",
        "좌표: x=viewer_med(log scale), y=gap_med",
        "점 크기: 45 + 25*log1p(zrun_max)",
        "색: cluster label, cmap=tab10",
        "주의: cluster_number/gmm/hdbscan은 뷰봇 정답 라벨이 아니라 세션 행동 유형 라벨입니다.",
    ]
    if note:
        txt.append(f"비고: {note}")
    Path(out, "cluster.txt").write_text("\n".join(txt) + "\n", encoding="utf-8")


def save_plot(s, out):
    # Plotting is centralized in src/plots.py.
    # Do not create out/cluster.png, because final slides use out/plots/04_cluster.png.
    return None

def add_gmm(s, xs, cfg):
    if len(s) < 4:
        s["gmm"] = np.nan
        return s, pd.DataFrame(columns=["n", "bic", "aic"]), "not available"

    rows, labels = [], {}
    for n in range(2, min(6, len(s) - 1) + 1):
        gm = GaussianMixture(n_components=n, random_state=int(cfg["cluster"]["seed"]), n_init=10)
        lab = gm.fit_predict(xs)
        rows.append({"n": n, "bic": gm.bic(xs), "aic": gm.aic(xs)})
        labels[n] = lab

    sel = pd.DataFrame(rows)
    best = int(sel.sort_values(["bic", "n"]).iloc[0]["n"])
    s["gmm"] = labels[best]
    return s, sel, str(best)


def add_hdbscan(s, xs, cfg):
    if HDBSCAN is None or len(s) < 5:
        s["hdbscan"] = np.nan
        s["hdbscan_noise"] = np.nan
        return s, pd.DataFrame(), "not available"

    sizes = cfg.get("hdbscan", {}).get("min_sizes", [5, 8, 10])
    sizes = sorted({int(v) for v in sizes if 2 <= int(v) < len(s)})
    if not sizes:
        sizes = [max(2, min(5, len(s) - 1))]

    rows, labels = [], {}
    for min_size in sizes:
        min_samples = max(2, min_size // 2)
        model = HDBSCAN(min_cluster_size=min_size, min_samples=min_samples, metric="euclidean", copy=True)
        lab = model.fit_predict(xs)
        labels[min_size] = lab

        non_noise = lab != -1
        n_noise = int((lab == -1).sum())
        n_cluster = len([x for x in np.unique(lab) if x != -1])
        sil = np.nan
        if n_cluster >= 2 and non_noise.sum() > n_cluster:
            sil = silhouette_score(xs[non_noise], lab[non_noise])
        noise_ratio = n_noise / len(lab)
        rows.append({
            "min_cluster_size": min_size,
            "min_samples": min_samples,
            "n_clusters": n_cluster,
            "n_noise": n_noise,
            "noise_ratio": noise_ratio,
            "coverage": 1 - noise_ratio,
            "silhouette": sil,
            "balanced_score": sil * (1 - noise_ratio) if np.isfinite(sil) else np.nan,
        })

    sel = pd.DataFrame(rows)
    valid = sel.dropna(subset=["balanced_score"])
    valid = valid[valid["n_clusters"].ge(2)]
    if valid.empty:
        best = int(sel.sort_values(["noise_ratio", "min_cluster_size"]).iloc[0]["min_cluster_size"])
    else:
        best = int(valid.sort_values(["balanced_score", "silhouette", "coverage"], ascending=[False, False, False]).iloc[0]["min_cluster_size"])

    s["hdbscan"] = labels[best]
    s["hdbscan_noise"] = s["hdbscan"].eq(-1).astype(int)
    return s, sel, str(best)


def add_cluster(df, out, cfg):
    out = Path(out)
    s = df.copy()
    k_min = int(cfg["cluster"]["k_min"])
    k_max_cfg = int(cfg["cluster"]["k_max"])

    if len(s) < 3:
        s["cluster_number"] = 0
        s["gmm"] = np.nan
        s["hdbscan"] = np.nan
        s["hdbscan_noise"] = np.nan
        pd.DataFrame(columns=["k", "silhouette", "inertia"]).to_csv(out / "cluster_select.csv", index=False, encoding="utf-8-sig")
        pd.DataFrame(columns=["n", "bic", "aic"]).to_csv(out / "gmm_select.csv", index=False, encoding="utf-8-sig")
        pd.DataFrame().to_csv(out / "hdbscan_select.csv", index=False, encoding="utf-8-sig")
        s[ASSIGN_COLS].to_csv(out / "cluster_assignments.csv", index=False, encoding="utf-8-sig")
        save_plot(s, out)
        write_doc(out, cfg, k_min, k_max_cfg, 1, note="세션 수가 3개 미만이라 단일 cluster로 고정")
        return s

    scaler = RobustScaler()
    xs = scaler.fit_transform(make_x(s))
    k_max = min(k_max_cfg, len(s) - 1)

    rows, models, labels = [], {}, {}
    for k in range(k_min, k_max + 1):
        km = KMeans(n_clusters=k, random_state=int(cfg["cluster"]["seed"]), n_init=int(cfg["cluster"]["n_init"]))
        lab = km.fit_predict(xs)
        if len(np.unique(lab)) < 2:
            continue
        rows.append({"k": k, "silhouette": silhouette_score(xs, lab), "inertia": km.inertia_})
        models[k] = km
        labels[k] = lab

    if not rows:
        s["cluster_number"] = 0
        best_k = 1
        sel = pd.DataFrame(columns=["k", "silhouette", "inertia"])
        note = "세션 feature가 거의 동일해 단일 cluster로 고정"
    else:
        sel = pd.DataFrame(rows)
        best_k = int(sel.sort_values(["silhouette", "k"], ascending=[False, True]).iloc[0]["k"])
        s["cluster_number"] = labels[best_k]
        note = ""

    s, g_sel, g_note = add_gmm(s, xs, cfg)
    s, h_sel, h_note = add_hdbscan(s, xs, cfg)

    profile = s.groupby("cluster_number").agg(
        n=("session_key", "size"),
        viewer_med=("viewer_med", "median"),
        chat_mean=("chat_mean", "mean"),
        unique_mean=("unique_mean", "mean"),
        zero_rate=("zero_rate", "mean"),
        gap_med=("gap_med", "median"),
        zrun_max=("zrun_max", "median"),
    ).reset_index()

    sel.to_csv(out / "cluster_select.csv", index=False, encoding="utf-8-sig")
    g_sel.to_csv(out / "gmm_select.csv", index=False, encoding="utf-8-sig")
    h_sel.to_csv(out / "hdbscan_select.csv", index=False, encoding="utf-8-sig")
    profile.to_csv(out / "cluster_profile.csv", index=False, encoding="utf-8-sig")
    s[ASSIGN_COLS].to_csv(out / "cluster_assignments.csv", index=False, encoding="utf-8-sig")

    if rows:
        joblib.dump(models[best_k], out / "kmeans.joblib")
        joblib.dump({"features": FEATS, "scaler": scaler, "kmeans": models[best_k], "best_k": best_k}, out / "kmeans_bundle.joblib")

    write_doc(out, cfg, k_min, k_max, best_k, gmm_note=g_note, hdb_note=h_note, note=note)
    save_plot(s, out)
    return s
