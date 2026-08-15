"""
InterTech PRJ001 — Project Delay Prediction System
Senior Data Science Pipeline
Target: Delay column (>0 = delayed, ≤0 = on-time; open tasks have no Actual → treated as unknown)
"""

import pandas as pd
import numpy as np
import os
import sys
import json
import warnings
warnings.filterwarnings("ignore")

from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import cross_val_score, StratifiedKFold
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import classification_report, confusion_matrix

try:
    import xgboost as xgb
    XGBOOST_AVAILABLE = True
except ImportError:
    XGBOOST_AVAILABLE = False
    print("Warning: XGBoost not installed. Install with: pip install xgboost")

try:
    import shap
    SHAP_AVAILABLE = True
except ImportError:
    SHAP_AVAILABLE = False
    print("Warning: SHAP not installed. Install with: pip install shap")

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# ─────────────────────────────────────────────
# 1. LOAD & INSPECT DATA
# ─────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
csv_path = os.path.join(BASE_DIR, "simulated_project_delay_dataset_1000.csv")
if not os.path.exists(csv_path):
    csv_path = os.path.join(BASE_DIR, "..", "simulated_project_delay_dataset_1000.csv")
if not os.path.exists(csv_path):
    csv_path = "project_data.csv"

df_raw = pd.read_csv(csv_path)
df_raw.columns = df_raw.columns.str.strip()
df = df_raw.dropna(subset=["TaskID"]).copy()          # drop blank rows
df = df.reset_index(drop=True)

print("=== RAW DATA SHAPE ===")
print(f"  Rows: {len(df)}  |  Columns: {len(df.columns)}")
print(f"  Columns: {list(df.columns)}\n")
print(df[["TaskID","Status","Delay","Priority","Risk","RootCause","Hours"]].to_string())
print()

# ─────────────────────────────────────────────
# 2. FEATURE ENGINEERING
# ─────────────────────────────────────────────
# 2a. Target: Delayed = Delay > 0 (only for closed tasks with Actual dates)
df["Delay"] = pd.to_numeric(df["Delay"], errors="coerce")
df["is_delayed"] = (df["Delay"] > 0).astype(int)   # NaN (open) → 0 initially

# 2b. Planned duration in days
df["Created"]  = pd.to_datetime(df["Created"],  errors="coerce", dayfirst=False)
df["Target"]   = pd.to_datetime(df["Target"],   errors="coerce", dayfirst=False)
df["planned_duration"] = (df["Target"] - df["Created"]).dt.days

# 2c. Encode Priority (High=2, Medium=1, Low=0)
priority_map = {"High": 2, "Medium": 1, "Low": 0}
df["priority_enc"] = df["Priority"].map(priority_map).fillna(1)

# 2d. Encode Risk (High=2, Medium=1, Low=0)
risk_map = {"High": 2, "Medium": 1, "Low": 0}
df["risk_enc"] = df["Risk"].map(risk_map).fillna(1)

# 2e. Root cause exists?
df["has_root_cause"] = df["RootCause"].notna().astype(int)

# 2f. Status encoded
df["status_enc"] = (df["Status"] == "Closed").astype(int)

# 2g. Discipline encoded
disc_dummies = pd.get_dummies(df["ProjectDiscipline"], prefix="disc")
df = pd.concat([df, disc_dummies], axis=1)

# 2h. Hours (numeric, fill missing with median)
df["Hours"] = pd.to_numeric(df["Hours"], errors="coerce")
df["Hours"] = df["Hours"].fillna(df["Hours"].median())

FEATURES = ["priority_enc","risk_enc","has_root_cause","Hours","planned_duration","status_enc"] \
           + [c for c in df.columns if c.startswith("disc_")]

# ─────────────────────────────────────────────
# 3. TRAINING SPLIT: only closed tasks with known delay
# ─────────────────────────────────────────────
train_df = df[df["Status"] == "Closed"].copy()
train_df["planned_duration"] = train_df["planned_duration"].fillna(train_df["planned_duration"].median())

X_train = train_df[FEATURES]
y_train = train_df["is_delayed"]

print(f"=== TRAINING SET ===")
print(f"  Closed tasks: {len(train_df)}")
print(f"  Delayed (1): {y_train.sum()}  |  On-time (0): {(y_train==0).sum()}")
print(f"  Features: {FEATURES}\n")

# ─────────────────────────────────────────────
# 4. MODEL COMPARISON — 5-FOLD CV
# ─────────────────────────────────────────────
cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)

models = {
    "Logistic Regression": LogisticRegression(max_iter=1000, random_state=42),
    "Random Forest":        RandomForestClassifier(n_estimators=100, random_state=42),
    "Gradient Boosting":    GradientBoostingClassifier(n_estimators=100, random_state=42),
}

if XGBOOST_AVAILABLE:
    models["XGBoost"] = xgb.XGBClassifier(n_estimators=100, random_state=42, eval_metric="logloss", verbosity=0)

print("=== 5-FOLD CROSS-VALIDATION RESULTS ===")
cv_results = {}
best_model_name = None
best_accuracy = -1

for name, model in models.items():
    scores = cross_val_score(model, X_train, y_train, cv=cv, scoring="accuracy")
    mean_acc = scores.mean()
    cv_results[name] = {"mean": round(mean_acc*100, 1), "std": round(scores.std()*100, 1), "scores": scores}
    print(f"  {name:25s}  Acc: {mean_acc*100:.1f}% +/- {scores.std()*100:.1f}%")
    
    if mean_acc > best_accuracy:
        best_accuracy = mean_acc
        best_model_name = name

print(f"\n🏆 BEST MODEL: {best_model_name} (Accuracy: {best_accuracy*100:.1f}%)\n")

# ─────────────────────────────────────────────
# 5. TRAIN FINAL MODEL — BEST MODEL
# ─────────────────────────────────────────────
best_model = models[best_model_name]
best_model.fit(X_train, y_train)

# In-sample check
y_pred_train = best_model.predict(X_train)
print(f"=== FINAL MODEL — IN-SAMPLE REPORT ({best_model_name}) ===")
print(classification_report(y_train, y_pred_train, target_names=["On-time","Delayed"]))

# Feature importance
if hasattr(best_model, 'feature_importances_'):
    feat_imp = pd.Series(best_model.feature_importances_, index=FEATURES).sort_values(ascending=False)
    print("=== FEATURE IMPORTANCE ===")
    for f, v in feat_imp.items():
        print(f"  {f:30s}  {v*100:.1f}%")
else:
    print("=== FEATURE IMPORTANCE ===")
    print("  (Not available for this model)")
    feat_imp = pd.Series({f: 0 for f in FEATURES})
print()

# SHAP Explanations (if available and model supports it)
if SHAP_AVAILABLE and hasattr(best_model, 'feature_importances_'):
    print("=== SHAP MODEL EXPLANATIONS ===")
    try:
        explainer = shap.TreeExplainer(best_model)
        shap_values = explainer.shap_values(X_train)
        if isinstance(shap_values, list):
            shap_values = shap_values[1]  # for binary classification, take class 1
        mean_shap = np.abs(shap_values).mean(axis=0)
        shap_imp = pd.Series(mean_shap, index=FEATURES).sort_values(ascending=False)
        print("  SHAP Mean Absolute Impact:")
        for f, v in shap_imp.items():
            print(f"    {f:30s}  {v:.4f}")
    except Exception as e:
        print(f"  SHAP explanation failed: {e}")
    print()
else:
    if not SHAP_AVAILABLE:
        print("=== SHAP MODEL EXPLANATIONS ===")
        print("  (SHAP not installed)")
        print()

# ─────────────────────────────────────────────
# 6. PREDICT ON ALL TASKS (including open)
# ─────────────────────────────────────────────
df_all = df.copy()
df_all["planned_duration"] = df_all["planned_duration"].fillna(df_all["planned_duration"].median())
X_all = df_all[FEATURES]

df_all["delay_prob"]  = best_model.predict_proba(X_all)[:, 1]  # P(delayed)
df_all["delay_score"] = (df_all["delay_prob"] * 100).round(1)

def classify_risk(p):
    if p >= 0.70: return "HIGH"
    if p >= 0.40: return "MEDIUM"
    return "LOW"

df_all["risk_cat"] = df_all["delay_prob"].apply(classify_risk)

# For closed tasks, use actual outcome as ground truth label
df_all["actual_delayed"] = df_all["is_delayed"].map({1: "Delayed", 0: "On-time"})
df_all.loc[df_all["Status"] == "Open", "actual_delayed"] = "Unknown"

print("=== ALL TASK PREDICTIONS ===")
cols_show = ["TaskID","Description","ProjectDiscipline","Status","Priority","Risk",
             "Delay","delay_score","risk_cat","actual_delayed"]
print(df_all[cols_show].to_string())
print()

# ─────────────────────────────────────────────
# 7. MITIGATION LOGIC
# ─────────────────────────────────────────────
open_tasks  = df_all[df_all["Status"] == "Open"].copy()
closed_low  = df_all[(df_all["Status"] == "Closed") | (df_all["risk_cat"].isin(["LOW","MEDIUM"]))]

mitigation_alerts = []
for _, row in open_tasks.iterrows():
    action = None
    if row["risk_cat"] == "HIGH":
        action = "NOTIFY_PM + REALLOCATE_RESOURCE"
    elif row["risk_cat"] == "MEDIUM":
        action = "SCHEDULE_STATUS_MEETING"
    else:
        action = "MONITOR_WEEKLY"

    mitigation_alerts.append({
        "task_id":    row["TaskID"],
        "desc":       row["Description"],
        "discipline": row["ProjectDiscipline"],
        "priority":   row["Priority"],
        "risk_cat":   row["risk_cat"],
        "score":      row["delay_score"],
        "action":     action
    })

print("=== MITIGATION ALERTS FOR OPEN TASKS ===")
for a in mitigation_alerts:
    print(f"  {a['task_id']} | {a['desc']:30s} | {a['risk_cat']:6s} | Score:{a['score']:5.1f}% | -> {a['action']}")
print()

# ─────────────────────────────────────────────
# 8. COMPUTE DASHBOARD STATS
# ─────────────────────────────────────────────
closed_df = df_all[df_all["Status"] == "Closed"]
delayed_closed = closed_df[closed_df["is_delayed"] == 1]

avg_delay = delayed_closed["Delay"].mean()
max_delay = delayed_closed["Delay"].max()

# Delay rate by discipline
disc_stats = {}
for disc, grp in df_all.groupby("ProjectDiscipline"):
    closed_grp = grp[grp["Status"] == "Closed"]
    delayed = int((closed_grp["is_delayed"] == 1).sum())
    total   = int(len(closed_grp))
    rate    = round(delayed / total * 100, 1) if total > 0 else 0
    disc_stats[disc] = {"delayed": delayed, "total": total, "rate": rate}

# Root cause frequency
rc_counts = delayed_closed["RootCause"].value_counts().to_dict()

# Feature importance export
feat_imp_export = {k: round(v*100, 1) for k, v in feat_imp.items()}

# Priority breakdown of delayed tasks
priority_delayed = delayed_closed["Priority"].value_counts().to_dict()

# ─────────────────────────────────────────────
# 9. EXPORT JSON FOR DASHBOARD
# ─────────────────────────────────────────────
all_tasks_json = []
for _, row in df_all.iterrows():
    all_tasks_json.append({
        "id":           str(row["TaskID"]),
        "desc":         str(row["Description"]),
        "disc":         str(row["ProjectDiscipline"]),
        "location":     str(row.get("Location", "")) if pd.notna(row.get("Location")) else "Site",
        "status":       str(row["Status"]),
        "priority":     str(row["Priority"]),
        "risk":         str(row["Risk"]),
        "hours":        float(row["Hours"]) if pd.notna(row.get("Hours")) else 0.0,
        "created":      str(row["Created"].strftime("%Y-%m-%d")) if pd.notna(row.get("Created")) and hasattr(row.get("Created"), "strftime") else str(row.get("Created", "")),
        "target":       str(row["Target"].strftime("%Y-%m-%d")) if pd.notna(row.get("Target")) and hasattr(row.get("Target"), "strftime") else str(row.get("Target", "")),
        "actual_date":  str(row.get("Actual", "")) if pd.notna(row.get("Actual")) else "—",
        "planned_days": int(row["planned_duration"]) if pd.notna(row.get("planned_duration")) else 0,
        "root_cause":   str(row["RootCause"]) if pd.notna(row.get("RootCause")) else None,
        "comments":     str(row.get("Comments", "")) if pd.notna(row.get("Comments")) else "",
        "delay":        float(row["Delay"]) if pd.notna(row.get("Delay")) else None,
        "score":        float(row["delay_score"]),
        "cat":          str(row["risk_cat"]),
        "actual":       str(row["actual_delayed"])
    })

dashboard_payload = {
    "meta": {
        "project_id":      "PRJ001",
        "total_tasks":     int(len(df_all)),
        "delayed_tasks":   int(len(delayed_closed)),
        "open_tasks":      int(len(open_tasks)),
        "avg_delay_days":  round(float(avg_delay), 1),
        "max_delay_days":  int(max_delay),
        "best_model":      best_model_name,
        "best_model_accuracy": round(best_accuracy*100, 1),
        "all_models_cv_accuracy": cv_results
    },
    "disc_stats":      disc_stats,
    "root_causes":     rc_counts,
    "priority_counts": priority_delayed,
    "feat_importance": feat_imp_export,
    "tasks":           all_tasks_json,
    "mitigation":      mitigation_alerts
}

output_json = os.path.join(BASE_DIR, "dashboard_data.json")
with open(output_json, "w") as f:
    json.dump(dashboard_payload, f, indent=2)

print(f"=== JSON exported to {output_json} ===")
print(json.dumps(dashboard_payload["meta"], indent=2))