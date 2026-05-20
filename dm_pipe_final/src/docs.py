from pathlib import Path

from .detect import FEATS as DETECTOR_FEATS
from .model import FEATS as MODEL_FEATS, MODEL_SCORE_COLS


def _get(cfg, *keys, default=None):
    cur = cfg
    for key in keys:
        if not isinstance(cur, dict) or key not in cur:
            return default
        cur = cur[key]
    return cur


def _join(values):
    return ", ".join(str(v) for v in values)


def _nrows(df):
    return 0 if df is None else len(df)


def _value_counts(df, col):
    if df is None or col not in df.columns:
        return "not available"
    vc = df[col].value_counts(dropna=False).sort_index()
    return ", ".join(f"{k}:{v}" for k, v in vc.items())


def write_score_doc(out, cfg=None, session_df=None, syn_train=None, model_scores=None, session_model=None):
    """Write an execution-specific algorithm document.

    The file records the actual input columns, scaler, output columns, and
    hyperparameters used by each non-clustering score algorithm. Clustering is
    still documented separately in out/cluster.txt by src/cluster.py.
    """
    # Backward-compatible alias: run.py/min2sess.py pass session_model.
    if session_df is None and session_model is not None:
        session_df = session_model

    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    n_session = _nrows(session_df)
    n_train = _nrows(syn_train)
    n_features_detector = len(DETECTOR_FEATS)
    n_features_model = len(MODEL_FEATS)

    contam = float(_get(cfg, "detector", "contam", default=0.05))
    detector_seed = int(_get(cfg, "detector", "seed", default=42))
    model_seed = int(_get(cfg, "model", "seed", default=42))
    test_size = float(_get(cfg, "model", "test_size", default=0.25))
    syn_seed = int(_get(cfg, "synthetic", "seed", default=42))
    n_per_type = int(_get(cfg, "synthetic", "n_per_type", default=50))
    label_file = _get(cfg, "path", "label_file", default="data/labels/manual_labels.csv")
    prep_min_n = int(_get(cfg, "prep", "min_n", default=10))

    lof_neighbors = "not run"
    if n_session >= 5:
        lof_neighbors = min(20, n_session - 1)

    ae_hidden = "not run"
    if n_session >= 5:
        ae_hidden = max(2, min(8, n_features_model // 2 + 1))

    syn_counts = _value_counts(syn_train, "y_syn")
    score_cols_present = []
    if model_scores is not None:
        score_cols_present = [c for c in MODEL_SCORE_COLS if c in model_scores.columns]

    lines = [
        "점수/모델 자동 설정 기록",
        "=========================",
        "이 파일은 run.py 실행 시 현재 cfg.yml과 실제 입력 row 수를 기준으로 자동 생성됨",
        "클러스터링 자체의 KMeans/GMM/HDBSCAN 설정은 out/cluster.txt에 별도 저장됨.",
        "",
        "공통 입력 데이터",
        "--------------",
        "분석 단위: session = run_id + broad_no",
        f"score 입력 session 수: {n_session}",
        f"synthetic supervised train row 수: {n_train}",
        f"synthetic train y_syn 분포: {syn_counts}",
        "결측/무한대 처리: feature별 inf/-inf를 NaN으로 바꾼 뒤 median으로 채우고, 그래도 남으면 0으로 채움.",
        "점수 방향: *_score는 값이 클수록 이상 후보 가능성이 크도록 저장한다.",
        "rank 컬럼: 각 score의 percentile rank이며 최종 ensemble score가 아니다.",
        "",
        "1) IsolationForest",
        "-------------------",
        "목적: 세션 단위 비지도 이상 후보 탐지",
        "입력 데이터: eligible session_model",
        f"입력 feature: {_join(DETECTOR_FEATS)}",
        "스케일러: RobustScaler",
        "모델 입력값: RobustScaler.fit_transform(detector_features)",
        "출력 컬럼: if_lab, if_score, if_score_rank",
        f"hyperparameter: n_estimators=200, contamination={contam}, random_state={detector_seed}",
        "score 계산: -IsolationForest.decision_function(X_scaled)",
        "",
        "2) LocalOutlierFactor",
        "----------------------",
        "목적: 밀도 기반 비지도 이상 후보 탐지",
        "입력 데이터: eligible session_model",
        f"입력 feature: {_join(DETECTOR_FEATS)}",
        "스케일러: RobustScaler",
        "모델 입력값: RobustScaler.fit_transform(detector_features)",
        "출력 컬럼: lof_lab, lof_score, lof_score_rank",
        f"hyperparameter: n_neighbors={lof_neighbors}, contamination={contam}",
        "score 계산: -LocalOutlierFactor.negative_outlier_factor_",
        "",
        "3) OneClassSVM",
        "----------------",
        "목적: RBF boundary 기반 비지도 이상 후보 탐지",
        "입력 데이터: eligible session_model",
        f"입력 feature: {_join(DETECTOR_FEATS)}",
        "스케일러: RobustScaler",
        "모델 입력값: RobustScaler.fit_transform(detector_features)",
        "출력 컬럼: ocsvm_lab, ocsvm_score, ocsvm_score_rank",
        f"hyperparameter: kernel='rbf', gamma='scale', nu={contam}",
        "score 계산: -OneClassSVM.decision_function(X_scaled)",
        "",
        "4) AutoEncoder reconstruction score",
        "-----------------------------------",
        "목적: 라벨 없이 정상/이상 cutoff를 만들지 않고 세션 재구성오차를 개별 score로 저장",
        "입력 데이터: eligible session_model",
        f"입력 feature: {_join(MODEL_FEATS)}",
        "스케일러: RobustScaler",
        "모델 입력값: RobustScaler.fit_transform(model_features)",
        "출력 컬럼: ae_score, ae_score_rank",
        f"hyperparameter: MLPRegressor(hidden_layer_sizes=({ae_hidden},), activation='relu', max_iter=300, random_state={model_seed})",
        "score 계산: scaled input과 reconstructed input의 row-wise mean squared error",
        "",
        "5) Synthetic anomaly generation",
        "-------------------------------",
        "목적: 실제 뷰봇 라벨이 없을 때, 명시적 이상 시나리오를 주입한 보조 supervised score 생성",
        "입력 데이터: minute_model과 eligible session_model",
        f"eligible base 조건: session_model 기준, 각 base session은 최소 {prep_min_n} minute 이상이어야 주입 가능",
        "주입 공통 절차: base session 선택 -> 연속 minute 구간 수정 -> minute 파생변수 재계산 -> session feature 재요약",
        "주입 시나리오: hi_view_low_chat, silent_run, view_spike_no_chat",
        "hi_view_low_chat: viewer 증가 + chat/unique 급감",
        "silent_run: 연속 구간 chat/unique/message 관련 값 0 처리",
        "view_spike_no_chat: viewer 급등 + chat/unique는 약하게만 변화",
        f"hyperparameter: seed={syn_seed}, n_per_type={n_per_type}",
        "출력 파일: syn_minute.csv, syn_train.csv, synthetic_injection.txt",
        "세부 injection 범위와 생성 row 수는 out/synthetic_injection.txt에 자동 저장",
        "",
        "6) Synthetic SVM",
        "----------------",
        "목적: synthetic anomaly scenario에 가까운 세션 점수화",
        "입력 데이터: syn_train(real y_syn=0 + synthetic y_syn=1)",
        f"입력 feature: {_join(MODEL_FEATS)}",
        "스케일러: RobustScaler inside sklearn Pipeline",
        "모델 입력값: raw model_features -> RobustScaler -> SVC",
        "출력 컬럼: svm_syn_score, svm_syn_score_rank",
        f"train/test split: test_size={test_size}, random_state={model_seed}, stratify=y_syn",
        f"hyperparameter: SVC(kernel='rbf', C=1.0, gamma='scale', probability=True, class_weight='balanced', random_state={model_seed})",
        "score 계산: predict_proba(real_sessions)[:, 1]",
        "",
        "7) Synthetic XGBoost",
        "--------------------",
        "목적: tree boosting 기반 synthetic anomaly scenario 점수화",
        "입력 데이터: syn_train(real y_syn=0 + synthetic y_syn=1)",
        f"입력 feature: {_join(MODEL_FEATS)}",
        "스케일러: 사용하지 않음(tree model)",
        "모델 입력값: median/0 filled model_features",
        "출력 컬럼: xgb_syn_score, xgb_syn_score_rank",
        f"train/test split: test_size={test_size}, random_state={model_seed}, stratify=y_syn",
        f"hyperparameter: n_estimators=60, max_depth=3, learning_rate=0.07, subsample=0.9, colsample_bytree=0.9, eval_metric='logloss', random_state={model_seed}, n_jobs=1, verbosity=0",
        "score 계산: predict_proba(real_sessions)[:, 1]",
        "",
        "8) Synthetic LightGBM",
        "----------------------",
        "목적: gradient boosting 기반 synthetic anomaly scenario 점수화",
        "입력 데이터: syn_train(real y_syn=0 + synthetic y_syn=1)",
        f"입력 feature: {_join(MODEL_FEATS)}",
        "스케일러: 사용하지 않음(tree model)",
        "모델 입력값: median/0 filled model_features",
        "출력 컬럼: lgb_syn_score, lgb_syn_score_rank",
        f"train/test split: test_size={test_size}, random_state={model_seed}, stratify=y_syn",
        f"hyperparameter: n_estimators=60, learning_rate=0.07, num_leaves=15, subsample=0.9, colsample_bytree=0.9, random_state={model_seed}, verbose=-1, n_jobs=1",
        "score 계산: predict_proba(real_sessions)[:, 1]",
        "",
        "9) PU-style LogisticRegression bagging",
        "-------------------------------------",
        "목적: manual positive label이 있을 때만 positive-unlabeled 방식의 보조 score 생성",
        f"label 파일: {label_file}",
        "label 파일 필요 컬럼: session_key, label",
        "positive 정의: label == 1",
        "입력 데이터: eligible session_model + manual positive label",
        f"입력 feature: {_join(MODEL_FEATS)}",
        "스케일러: RobustScaler inside sklearn Pipeline",
        "모델 입력값: raw model_features -> RobustScaler -> LogisticRegression",
        "출력 컬럼: pu_score, pu_score_rank",
        f"bagging 반복: 30회, 각 반복 negative sample 수=min(n_unlabeled, max(n_positive*3, 10)), random_state={model_seed}",
        f"hyperparameter: LogisticRegression(max_iter=1000, class_weight='balanced', random_state={model_seed})",
        "score 계산: 30회 predict_proba(real_sessions)[:, 1] 평균",
        "생성 조건: manual label 파일이 없거나 positive가 부족하면 pu_score는 NaN",
        "",
        "현재 model score 컬럼",
        "----------------------",
        f"생성된 model score 컬럼: {_join(score_cols_present) if score_cols_present else 'not available'}",
        f"기본 model score 후보: {_join(MODEL_SCORE_COLS)}",
        "",
        "주의",
        "----",
        "cluster_number는 KMeans 세션 행동 유형 번호이며 뷰봇 정답 라벨이 아니다.",
        "본 코드에서는 review_score/final_score/ensemble_score처럼 여러 알고리즘을 결합한 최종 점수를 만들지 않는다.",
    ]

    (out / "score.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
