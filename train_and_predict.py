"""
InterTech PRJ001 — MNC-Grade Project Delay Prediction Pipeline (Honest & Leakage-Free)
======================================================================================
Models compared:
 1. Logistic Regression (baseline, balanced)
 2. Random Forest (tree ensemble, balanced)
 3. Gradient Boosting (sklearn GBM)
 4. XGBoost (scale_pos_weight balanced)
 5. Stacking Ensemble (RF + XGB + LR → LR meta)

Data Leakage Prevention:
 - Excludes post-hoc features (RootCause, Overdue flag) which are only populated 
 AFTER a delay occurs.
 - Retains purely pre-execution/in-flight features: Priority, Risk, Hours, 
 Planned Duration, Workload Intensity, and Discipline encodings.

Cross-Validation:
 - 5-Fold StratifiedKFold cross-validation.
"""

import pandas as pd
import numpy as np
import os, sys, json, warnings
warnings.filterwarnings("ignore")

from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier, StackingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold, LeaveOneOut
from sklearn.base import clone
from sklearn.metrics import (f1_score, roc_auc_score, matthews_corrcoef,
 precision_score, recall_score, accuracy_score,
 classification_report)
from sklearn.calibration import CalibratedClassifierCV
from scipy import stats
import xgboost as xgb
import shap

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# ---------------------------------------------------------------------------
# 1. LOAD DATA
# ---------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

csv_path = None
for candidate in [
    # Written only after the user explicitly activates LLM-prepared historical data.
    os.path.join(BASE_DIR, "uploaded_training_dataset.csv"),
    os.path.join(BASE_DIR, "simulated_project_delay_dataset_1000.csv"),
    os.path.join(BASE_DIR, "SAMPLE DATA(Book2).csv"),
    os.path.join(BASE_DIR, "..", "simulated_project_delay_dataset_1000.csv"),
    os.path.join(BASE_DIR, "project_data.csv"),
]:
    if os.path.exists(candidate):
        csv_path = candidate
        break

if csv_path is None:
 raise FileNotFoundError("Dataset CSV not found.")

df_raw = pd.read_csv(csv_path)
df_raw.columns = df_raw.columns.str.strip()
df = df_raw.dropna(subset=["TaskID"]).copy().reset_index(drop=True)

print("=" * 65)
print(" InterTech PRJ001 — Honest ML Delay Prediction Pipeline")
print("=" * 65)

# ---------------------------------------------------------------------------
# 2. FEATURE ENGINEERING (Strictly Pre-Execution Features)
# ---------------------------------------------------------------------------
TODAY = pd.Timestamp.today().normalize()

df["Delay"] = pd.to_numeric(df["Delay"], errors="coerce")
df["Hours"] = pd.to_numeric(df["Hours"], errors="coerce")
df["Created"] = pd.to_datetime(df["Created"], errors="coerce", dayfirst=False)
df["Target"] = pd.to_datetime(df["Target"], errors="coerce", dayfirst=False)
df["Actual"] = pd.to_datetime(df["Actual"], errors="coerce", dayfirst=False)

# Ordinal encodings
priority_map = {"High": 2, "Medium": 1, "Low": 0}
risk_map = {"High": 2, "Medium": 1, "Low": 0}
df["priority_enc"] = df["Priority"].map(priority_map).fillna(1)
df["risk_enc"] = df["Risk"].map(risk_map).fillna(1)

# High priority AND High risk interaction
df["high_pri_high_risk"] = ((df["priority_enc"] == 2) & (df["risk_enc"] == 2)).astype(int)

# Planned duration (days)
df["planned_duration"] = (df["Target"] - df["Created"]).dt.days.clip(lower=1)

# Hours per day (workload intensity)
df["Hours"] = df["Hours"].fillna(df["Hours"].median())
df["hours_per_day"] = (df["Hours"] / df["planned_duration"].replace(0, np.nan)).fillna(0)

# Discipline one-hot encoding
disc_dummies = pd.get_dummies(df["ProjectDiscipline"], prefix="disc")
df = pd.concat([df, disc_dummies], axis=1)
disc_cols = [c for c in df.columns if c.startswith("disc_")]

# Historical discipline delay rate for the final production model. During model
# evaluation this value is rebuilt inside each fold so validation labels never
# influence their own features.
train_closed_mask = df["Status"] == "Closed"
disc_delay_rate = (
 df[train_closed_mask]
 .groupby("ProjectDiscipline")["Delay"]
 .apply(lambda x: (x > 0).mean())
)
df["disc_hist_delay_rate"] = df["ProjectDiscipline"].map(disc_delay_rate).fillna(0.5)

# PURE PREDICTIVE FEATURES (No post-hoc RootCause or Overdue target leakage)
FEATURES = [
 "priority_enc", "risk_enc", "high_pri_high_risk", "Hours",
 "planned_duration", "hours_per_day", "disc_hist_delay_rate"
] + disc_cols

df["is_delayed"] = (df["Delay"] > 0).astype(int)

# ---------------------------------------------------------------------------
# 3. TRAINING SET
# ---------------------------------------------------------------------------
train_df = df[df["Status"] == "Closed"].copy()
X_train = train_df[FEATURES].fillna(0)
y_train = train_df["is_delayed"]

n_delayed = int(y_train.sum())
n_ontime = int((y_train == 0).sum())
scale_pos = n_ontime / max(n_delayed, 1)

print(f"[TRAIN] Closed tasks : {len(train_df)}")
print(f" Delayed : {n_delayed} | On-time: {n_ontime}")
print(f" Features : {len(FEATURES)} (Post-hoc leakage features removed)\n")

# ---------------------------------------------------------------------------
# 4. MODEL DEFINITIONS
# ---------------------------------------------------------------------------
lr = LogisticRegression(max_iter=1000, class_weight="balanced", C=0.5, random_state=42)

rf = RandomForestClassifier(
 n_estimators=200, max_depth=4, min_samples_leaf=3,
 class_weight="balanced", random_state=42
)

gb = GradientBoostingClassifier(
 n_estimators=100, max_depth=3, learning_rate=0.05,
 subsample=0.8, random_state=42
)

xgb_model = xgb.XGBClassifier(
 n_estimators=100, max_depth=3, learning_rate=0.05,
 subsample=0.8, colsample_bytree=0.8,
 scale_pos_weight=scale_pos, eval_metric="logloss",
 random_state=42, verbosity=0
)

stacking = StackingClassifier(
 estimators=[
 ("rf", RandomForestClassifier(n_estimators=100, max_depth=3, class_weight="balanced", random_state=42)),
 ("xgb", xgb.XGBClassifier(n_estimators=80, max_depth=3, learning_rate=0.05, scale_pos_weight=scale_pos, eval_metric="logloss", random_state=42, verbosity=0)),
 ("lr", LogisticRegression(max_iter=1000, class_weight="balanced", C=0.5, random_state=42)),
 ],
 final_estimator=LogisticRegression(max_iter=1000, class_weight="balanced", random_state=42),
 cv=3
)

models = {
 "Logistic Regression": lr,
 "Random Forest": rf,
 "Gradient Boosting": gb,
 "XGBoost": xgb_model,
 "Stacking Ensemble": stacking,
}

# ---------------------------------------------------------------------------
# 5. CROSS-VALIDATION EVALUATION
# ---------------------------------------------------------------------------
X_arr = X_train.values
y_arr = y_train.values

if len(y_arr) <= 50:
 cv_method = "Leave-One-Out CV"
 cv_splitter = LeaveOneOut()
else:
 n_splits = 5
 cv_method = f"{n_splits}-Fold Stratified CV"
 cv_splitter = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=42)

print("=" * 95)
print(f" {cv_method} — Honest Benchmark (No Target Leakage)")
print("=" * 95)
print(f" {'Model':<25} {'Accuracy (95% CI)':>20} {'F1 (95% CI)':>20} {'AUC':>8}")
print(f" {'-'*25} {'-'*20} {'-'*20} {'-'*8}")

def fold_features(fit_idx, eval_idx):
    """Build features with discipline rates learned only from the fold's fit set."""
    fold_train = train_df.iloc[fit_idx]
    fold_rate = fold_train.groupby("ProjectDiscipline")["is_delayed"].mean()
    fallback_rate = float(fold_train["is_delayed"].mean())

    def apply_rate(indices):
        features = X_train.iloc[indices].copy()
        disciplines = train_df.iloc[indices]["ProjectDiscipline"]
        features.loc[:, "disc_hist_delay_rate"] = disciplines.map(fold_rate).fillna(fallback_rate).to_numpy()
        return features

    return apply_rate(fit_idx), apply_rate(eval_idx)

def compute_bootstrap_ci(y_true, y_pred, y_prob, n_bootstraps=500, ci_level=95):
    np.random.seed(42)
    accs, f1s, aucs = [], [], []
    n = len(y_true)
    for _ in range(n_bootstraps):
        indices = np.random.choice(n, size=n, replace=True)
        yt = y_true[indices]
        yp = y_pred[indices]
        pr = y_prob[indices]
        if len(np.unique(yt)) < 2:
            continue
        accs.append(accuracy_score(yt, yp) * 100)
        f1s.append(f1_score(yt, yp, zero_division=0) * 100)
        try:
            aucs.append(roc_auc_score(yt, pr) * 100)
        except Exception:
            pass
    alpha = (100 - ci_level) / 2.0
    return {
        "accuracy_ci_95": [round(float(np.percentile(accs, alpha)), 1), round(float(np.percentile(accs, 100 - alpha)), 1)] if accs else [0.0, 0.0],
        "f1_ci_95": [round(float(np.percentile(f1s, alpha)), 1), round(float(np.percentile(f1s, 100 - alpha)), 1)] if f1s else [0.0, 0.0],
        "auc_ci_95": [round(float(np.percentile(aucs, alpha)), 1), round(float(np.percentile(aucs, 100 - alpha)), 1)] if aucs else [0.0, 0.0]
    }

loo_results = {}
cv_predictions = {}

for name, model in models.items():
    y_pred_cv = np.zeros(len(y_arr), dtype=int)
    y_prob_cv = np.zeros(len(y_arr))

    for train_idx, test_idx in cv_splitter.split(X_arr, y_arr):
        X_fold_train, X_fold_test = fold_features(train_idx, test_idx)
        m = clone(model)
        m.fit(X_fold_train, y_arr[train_idx])
        y_pred_cv[test_idx] = m.predict(X_fold_test)
        if hasattr(m, "predict_proba"):
            y_prob_cv[test_idx] = m.predict_proba(X_fold_test)[:, 1]
        else:
            y_prob_cv[test_idx] = float(y_pred_cv[test_idx][0])

    acc = round(accuracy_score(y_arr, y_pred_cv) * 100, 1)
    f1 = round(f1_score(y_arr, y_pred_cv, zero_division=0) * 100, 1)
    prec = round(precision_score(y_arr, y_pred_cv, zero_division=0) * 100, 1)
    rec = round(recall_score(y_arr, y_pred_cv, zero_division=0) * 100, 1)
    mcc = round(matthews_corrcoef(y_arr, y_pred_cv) * 100, 1)
    try:
        auc = round(roc_auc_score(y_arr, y_prob_cv) * 100, 1)
    except Exception:
        auc = 0.0

    ci_bounds = compute_bootstrap_ci(y_arr, y_pred_cv, y_prob_cv)

    cv_predictions[name] = {"pred": y_pred_cv, "prob": y_prob_cv}

    loo_results[name] = {
        "acc": acc, "f1": f1, "precision": prec,
        "recall": rec, "mcc": mcc, "auc_roc": auc,
        "ci_95": ci_bounds
    }
    print(f" {name:<25} {acc:>5.1f}% {f1:>5.1f}% {auc:>5.1f}% {prec:>5.1f}% {rec:>5.1f}% {mcc:>5.1f}")

print()

# Baseline comparisons ("flag every High Risk task" / predict 1 vs predict 0)
flag_all_preds = np.ones(len(y_arr), dtype=int)
flag_none_preds = np.zeros(len(y_arr), dtype=int)

baseline_flag_all_acc = round(accuracy_score(y_arr, flag_all_preds) * 100, 1)
baseline_flag_all_f1 = round(f1_score(y_arr, flag_all_preds, zero_division=0) * 100, 1)
baseline_flag_none_acc = round(accuracy_score(y_arr, flag_none_preds) * 100, 1)

# Cross-fitted rates keep final training matrix aligned with honest validation scheme
X_train_final = X_train.copy()
for train_idx, test_idx in cv_splitter.split(X_arr, y_arr):
    _, X_fold_test = fold_features(train_idx, test_idx)
    X_train_final.iloc[test_idx] = X_fold_test

# ---------------------------------------------------------------------------
# 6. SELECT CHAMPION (highest LOO-CV F1)
# ---------------------------------------------------------------------------
champion_name = max(loo_results, key=lambda k: loo_results[k]["f1"])
champion_metrics = loo_results[champion_name]

baseline_comparison = {
    "baseline_name": "Flag every task as High Risk",
    "baseline_accuracy": baseline_flag_all_acc,
    "baseline_f1": baseline_flag_all_f1,
    "always_ontime_accuracy": baseline_flag_none_acc,
    "champion_name": champion_name,
    "champion_accuracy": champion_metrics["acc"],
    "champion_f1": champion_metrics["f1"],
    "accuracy_lift_pp": round(champion_metrics["acc"] - baseline_flag_all_acc, 1),
    "f1_lift_pp": round(champion_metrics["f1"] - baseline_flag_all_f1, 1),
}

print("=" * 65)
print(f" CHAMPION → {champion_name}")
print(f" F1={champion_metrics['f1']}% AUC={champion_metrics['auc_roc']}% "
      f"MCC={champion_metrics['mcc']} Acc={champion_metrics['acc']}%")
print(f" 95% CI Accuracy: [{champion_metrics['ci_95']['accuracy_ci_95'][0]}%, {champion_metrics['ci_95']['accuracy_ci_95'][1]}%]")
print(f" BASELINE (Flag All High Risk) → Acc={baseline_flag_all_acc}% | F1={baseline_flag_all_f1}%")
print(f" MODEL LIFT → +{baseline_comparison['accuracy_lift_pp']} percentage points Accuracy | +{baseline_comparison['f1_lift_pp']} pp F1")
print("=" * 65 + "\n")

# ---------------------------------------------------------------------------
# 6b. CHRONOLOGICAL HOLDOUT (time-based future-data train/test split)
# ---------------------------------------------------------------------------
# Sort by the task creation date and reserve the newest 20% of closed records
# as a future holdout. Discipline history is learned strictly from older records.
chron_df = train_df.dropna(subset=["Created"]).sort_values("Created").reset_index(drop=True)
chron_cut = int(len(chron_df) * 0.8)
temporal_validation = {"available": False}
if chron_cut >= 20 and len(chron_df) - chron_cut >= 10:
    chron_fit = chron_df.iloc[:chron_cut]
    chron_test = chron_df.iloc[chron_cut:]
    if chron_fit["is_delayed"].nunique() == 2 and chron_test["is_delayed"].nunique() == 2:
        rate_by_discipline = chron_fit.groupby("ProjectDiscipline")["is_delayed"].mean()
        fallback_rate = float(chron_fit["is_delayed"].mean())
        X_chron_fit = chron_fit[FEATURES].fillna(0).copy()
        X_chron_test = chron_test[FEATURES].fillna(0).copy()
        X_chron_fit.loc[:, "disc_hist_delay_rate"] = chron_fit["ProjectDiscipline"].map(rate_by_discipline).fillna(fallback_rate).to_numpy()
        X_chron_test.loc[:, "disc_hist_delay_rate"] = chron_test["ProjectDiscipline"].map(rate_by_discipline).fillna(fallback_rate).to_numpy()
        y_chron_fit = chron_fit["is_delayed"].to_numpy()
        y_chron_test = chron_test["is_delayed"].to_numpy()
        chronological_model = clone(models[champion_name])
        chronological_model.fit(X_chron_fit, y_chron_fit)
        chron_pred = chronological_model.predict(X_chron_test)
        chron_prob = chronological_model.predict_proba(X_chron_test)[:, 1]
        
        chron_acc = round(accuracy_score(y_chron_test, chron_pred) * 100, 1)
        chron_f1 = round(f1_score(y_chron_test, chron_pred, zero_division=0) * 100, 1)
        chron_base_acc = round(accuracy_score(y_chron_test, np.ones_like(y_chron_test)) * 100, 1)
        
        temporal_validation = {
            "available": True,
            "cutoff_date": chron_test["Created"].iloc[0].strftime("%Y-%m-%d"),
            "train_records": int(len(chron_fit)),
            "test_records": int(len(chron_test)),
            "accuracy": chron_acc,
            "f1": chron_f1,
            "precision": round(precision_score(y_chron_test, chron_pred, zero_division=0) * 100, 1),
            "recall": round(recall_score(y_chron_test, chron_pred, zero_division=0) * 100, 1),
            "auc_roc": round(roc_auc_score(y_chron_test, chron_prob) * 100, 1),
            "mcc": round(matthews_corrcoef(y_chron_test, chron_pred) * 100, 1),
            "baseline_accuracy": chron_base_acc,
            "baseline_name": "Flag every task as high risk",
            "always_ontime_accuracy": round(accuracy_score(y_chron_test, np.zeros_like(y_chron_test)) * 100, 1),
            "temporal_lift_pp": round(chron_acc - chron_base_acc, 1)
        }
        print(f"[TEMPORAL HOLDOUT] Newest {len(chron_test)} records (Time-based Split) | Model Accuracy {chron_acc}% | F1 {chron_f1}% | Flag-all baseline {chron_base_acc}% (Lift: +{round(chron_acc - chron_base_acc, 1)} pp)")
else:
    print("[TEMPORAL HOLDOUT] Not available: insufficient dated closed records with both classes.")

# ---------------------------------------------------------------------------
# 7. TRAIN FINAL CALIBRATED MODEL
# ---------------------------------------------------------------------------
base_champion = models[champion_name]
base_champion.fit(X_train_final, y_train)

try:
 calibrated = CalibratedClassifierCV(base_champion, cv=3, method="isotonic")
 calibrated.fit(X_train_final, y_train)
 final_model = calibrated
 use_calibrated = True
 print("[*] Probability calibration applied (isotonic regression).")
except Exception as e:
 final_model = base_champion
 use_calibrated = False
 print(f"[!] Calibration skipped ({e}). Using raw probabilities.")

# ---------------------------------------------------------------------------
# 8. SHAP EXPLAINABILITY
# ---------------------------------------------------------------------------
print("[*] Computing SHAP values...")
X_all_filled = df[FEATURES].fillna(0)
X_train_filled = X_train_final.fillna(0)
shap_vals = None
shap_method = "None"

try:
    tree_model = models.get("Random Forest")
    if hasattr(base_champion, "feature_importances_"):
        tree_model = base_champion
    elif hasattr(base_champion, "estimators_"):
        for _, est in base_champion.estimators_:
            if hasattr(est, "feature_importances_"):
                tree_model = est
                break

    if tree_model is not None and hasattr(tree_model, "feature_importances_"):
        explainer = shap.TreeExplainer(tree_model)
        sv = explainer.shap_values(X_all_filled)
        if isinstance(sv, list):
            shap_vals = sv[1] if len(sv) > 1 else sv[0]
        elif isinstance(sv, np.ndarray) and sv.ndim == 3:
            shap_vals = sv[:, :, 1]
        else:
            shap_vals = sv
        shap_method = f"TreeExplainer ({type(tree_model).__name__})"
        print(f"[*] SHAP via {shap_method}")
    else:
        bg = shap.sample(X_train_filled, min(30, len(X_train_filled)), random_state=42)
        def _pred(X):
            return final_model.predict_proba(pd.DataFrame(X, columns=FEATURES))[:, 1]
        exp2 = shap.KernelExplainer(_pred, bg)
        shap_vals = exp2.shap_values(X_all_filled.values, nsamples=40)
        shap_method = "KernelExplainer"
        print(f"[*] SHAP via KernelExplainer")
except Exception as e:
    print(f"[!] SHAP calculation skipped ({e})")

def get_top_drivers(shap_row, top_n=3):
    if shap_row is None:
        return []
    shap_row = np.asarray(shap_row).flatten()
    pairs = sorted(zip(np.abs(shap_row), shap_row, FEATURES), key=lambda x: float(x[0]), reverse=True)
    out = []
    for abs_v, v, fname in pairs[:top_n]:
        if abs_v < 1e-6:
            continue
        label = fname.replace("disc_", "Discipline: ").replace("_", " ").title()
        out.append({
            "feature": label,
            "direction": "increases" if v > 0 else "decreases",
            "impact": round(float(abs_v), 4)
        })
    return out

# ---------------------------------------------------------------------------
# 9. PREDICT ON ALL TASKS
# ---------------------------------------------------------------------------
df["delay_prob"] = final_model.predict_proba(X_all_filled)[:, 1]
df["delay_score"] = (df["delay_prob"] * 100).round(1)

def classify_risk(p):
    if p >= 0.70:
        return "HIGH"
    if p >= 0.40:
        return "MEDIUM"
    return "LOW"

df["risk_cat"] = df["delay_prob"].apply(classify_risk)
df["actual_delayed"] = df["is_delayed"].map({1: "Delayed", 0: "On-time"})
df.loc[df["Status"] != "Closed", "actual_delayed"] = "Unknown"

# Feature importance
feat_imp_export = {}
try:
    src = base_champion
    if hasattr(src, "estimators_"):
        for est in src.estimators_:
            if hasattr(est, "feature_importances_"):
                src = est
                break
    if hasattr(src, "feature_importances_"):
        fi = pd.Series(src.feature_importances_, index=FEATURES).sort_values(ascending=False)
        feat_imp_export = {str(k): round(float(v) * 100, 2) for k, v in fi.items()}
    elif hasattr(src, "coef_"):
        coefs = np.abs(src.coef_[0])
        total_c = coefs.sum()
        if total_c > 0:
            coefs = coefs / total_c * 100
        feat_imp_export = {str(k): round(float(v), 2) for k, v in sorted(zip(FEATURES, coefs), key=lambda x: x[1], reverse=True)}
    else:
        feat_imp_export = {f: 0.0 for f in FEATURES}
except Exception as e:
    print(f"[!] Feature importance error: {e}")
    feat_imp_export = {f: 0.0 for f in FEATURES}

# Mitigation alerts
open_tasks = df[df["Status"] == "Open"].copy()
mitigation_alerts = []
for _, row in open_tasks.iterrows():
    if row["risk_cat"] == "HIGH":
        action = "NOTIFY_PM + REALLOCATE_RESOURCE"
    elif row["risk_cat"] == "MEDIUM":
        action = "SCHEDULE_STATUS_MEETING"
    else:
        action = "MONITOR_WEEKLY"
    mitigation_alerts.append({
        "task_id": row["TaskID"], "desc": row["Description"],
        "discipline": row["ProjectDiscipline"], "priority": row["Priority"],
        "risk_cat": row["risk_cat"], "score": row["delay_score"], "action": action
    })

# Stats
closed_df = df[df["Status"] == "Closed"]
delayed_closed = closed_df[closed_df["is_delayed"] == 1]
avg_delay = delayed_closed["Delay"].mean() if len(delayed_closed) > 0 else 0
max_delay = delayed_closed["Delay"].max() if len(delayed_closed) > 0 else 0

disc_stats = {}
for disc, grp in df.groupby("ProjectDiscipline"):
    cg = grp[grp["Status"] == "Closed"]
    d = int((cg["is_delayed"] == 1).sum())
    t = int(len(cg))
    disc_stats[disc] = {
        "delayed": d, "total": t,
        "rate": round(d / t * 100, 1) if t > 0 else 0
    }

rc_counts = delayed_closed["RootCause"].value_counts().to_dict()
priority_delayed = delayed_closed["Priority"].value_counts().to_dict()

all_tasks_json = []
for i, (_, row) in enumerate(df.iterrows()):
 drivers = get_top_drivers(shap_vals[i] if shap_vals is not None else None)
 all_tasks_json.append({
 "id": str(row["TaskID"]),
 "desc": str(row["Description"]),
 "disc": str(row["ProjectDiscipline"]),
 "location": str(row.get("Location", "")) if pd.notna(row.get("Location")) else "Site",
 "status": str(row["Status"]),
 "priority": str(row["Priority"]),
 "risk": str(row["Risk"]),
 "hours": float(row["Hours"]) if pd.notna(row.get("Hours")) else 0.0,
 "created": row["Created"].strftime("%Y-%m-%d") if pd.notna(row.get("Created")) else "",
 "target": row["Target"].strftime("%Y-%m-%d") if pd.notna(row.get("Target")) else "",
 "actual_date": str(row.get("Actual", "")) if pd.notna(row.get("Actual")) else "—",
 "planned_days": int(row["planned_duration"]) if pd.notna(row.get("planned_duration")) else 0,
 "root_cause": str(row["RootCause"]) if pd.notna(row.get("RootCause")) else None,
 "comments": str(row.get("Comments", "")) if pd.notna(row.get("Comments")) else "",
 "delay": float(row["Delay"]) if pd.notna(row.get("Delay")) else None,
 "score": float(row["delay_score"]),
 "cat": str(row["risk_cat"]),
 "actual": str(row["actual_delayed"]),
 "shap_drivers": drivers,
 })

dashboard_payload = {
 "meta": {
 "project_id": "PRJ001",
 "total_tasks": int(len(df)),
 "delayed_tasks": int(len(delayed_closed)),
 "open_tasks": int(len(open_tasks)),
 "avg_delay_days": round(float(avg_delay), 1),
 "max_delay_days": int(max_delay),
 "model": f"{champion_name} (Calibrated: {use_calibrated})",
 "champion": champion_name,
 "calibrated": use_calibrated,
 "cv_method": cv_method,
 "shap_method": shap_method,
 "n_features": len(FEATURES),
 "cv_accuracy": {
 name: {
 "mean": res["acc"],
 "std": 0.0,
 "f1": res["f1"],
 "auc": res["auc_roc"],
 "mcc": res["mcc"],
 "precision": res["precision"],
 "recall": res["recall"],
 }
 for name, res in loo_results.items()
 },
 "champion_metrics": champion_metrics,
 "temporal_validation": temporal_validation,
 "baseline_comparison": baseline_comparison,
 "confidence_intervals": champion_metrics.get("ci_95", {}),
 },
 "disc_stats": disc_stats,
 "root_causes": rc_counts,
 "priority_counts": priority_delayed,
 "feat_importance": feat_imp_export,
 "tasks": all_tasks_json,
 "mitigation": mitigation_alerts,
}

output_json = os.path.join(BASE_DIR, "dashboard_data.json")
with open(output_json, "w") as f:
    json.dump(dashboard_payload, f, indent=2)

# ---------------------------------------------------------------------------
# 10. MODEL REGISTRY SNAPSHOT
# ---------------------------------------------------------------------------
import datetime as _dt, shutil as _shutil
registry_dir = os.path.join(BASE_DIR, "model_registry")
os.makedirs(registry_dir, exist_ok=True)
reg_path = os.path.join(registry_dir, "registry.json")
try:
    with open(reg_path) as _rf:
        _registry = json.load(_rf)
except Exception:
    _registry = []
for _r in _registry:
    _r["active"] = False
_ts = _dt.datetime.now().strftime("%Y%m%d_%H%M")
_version = len(_registry) + 1
_snap_file = f"v{_version}_{_ts}.json"
_shutil.copy(output_json, os.path.join(registry_dir, _snap_file))
_registry.append({
    "version": _version,
    "date": _dt.datetime.now().isoformat(),
    "champion": champion_name,
    "f1": champion_metrics["f1"],
    "recall": champion_metrics["recall"],
    "auc": champion_metrics["auc_roc"],
    "acc": champion_metrics["acc"],
    "active": True,
    "file": _snap_file
})
with open(reg_path, "w") as _rf:
    json.dump(_registry, _rf, indent=2)
print(f"[*] Model registry snapshot: {_snap_file} (v{_version})")

public_dir = os.path.join(BASE_DIR, "public")
os.makedirs(public_dir, exist_ok=True)
public_json = os.path.join(public_dir, "dashboard_data.json")
with open(public_json, "w") as f:
    json.dump(dashboard_payload, f, indent=2)

print(f"\n{'='*65}")
print(f" HONEST PIPELINE COMPLETE")
print(f"{'='*65}")
print(f" Champion : {champion_name}")
print(f" CV Method : {cv_method}")
print(f" Accuracy : {champion_metrics['acc']}%")
print(f" F1 Score : {champion_metrics['f1']}%")
print(f" AUC-ROC : {champion_metrics['auc_roc']}%")
print(f" MCC : {champion_metrics['mcc']}")
print(f" Calibrated : {use_calibrated}")
print(f" JSON -> {output_json}")
print(f"{'='*65}")
