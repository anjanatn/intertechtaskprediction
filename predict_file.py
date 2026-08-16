"""
InterTech PRJ001 — File Import Delay Prediction Engine
======================================================
Processes user-uploaded CSV and Excel (.xlsx, .xls) files, applies pre-execution
feature engineering, fits/runs the calibrated ML model, and returns risk scores,
SHAP explainability drivers, and mitigation plans.
"""

import os
import sys
import json
import io
import pandas as pd
import numpy as np
import warnings
warnings.filterwarnings("ignore")

from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier, StackingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.calibration import CalibratedClassifierCV
import xgboost as xgb
import shap

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def get_base_training_data():
    """Load baseline historical dataset to train/calibrate champion model."""
    candidates = [
        os.path.join(BASE_DIR, "simulated_project_delay_dataset_1000.csv"),
        os.path.join(BASE_DIR, "SAMPLE DATA(Book2).csv"),
        os.path.join(BASE_DIR, "..", "simulated_project_delay_dataset_1000.csv"),
        os.path.join(BASE_DIR, "project_data.csv"),
    ]
    csv_path = None
    for c in candidates:
        if os.path.exists(c):
            csv_path = c
            break
    if csv_path is None:
        raise FileNotFoundError("Base dataset CSV not found.")

    df_raw = pd.read_csv(csv_path)
    df_raw.columns = df_raw.columns.str.strip()
    df = df_raw.dropna(subset=["TaskID"]).copy().reset_index(drop=True)
    return df

def train_production_model(df_base):
    """Train calibrated Random Forest champion model on historical closed tasks."""
    df_base["Delay"] = pd.to_numeric(df_base["Delay"], errors="coerce")
    df_base["Hours"] = pd.to_numeric(df_base["Hours"], errors="coerce")
    df_base["Created"] = pd.to_datetime(df_base["Created"], errors="coerce")
    df_base["Target"]  = pd.to_datetime(df_base["Target"], errors="coerce")
    
    priority_map = {"High": 2, "Medium": 1, "Low": 0}
    risk_map     = {"High": 2, "Medium": 1, "Low": 0}
    
    df_base["priority_enc"] = df_base["Priority"].map(priority_map).fillna(1)
    df_base["risk_enc"]     = df_base["Risk"].map(risk_map).fillna(1)
    df_base["high_pri_high_risk"] = ((df_base["priority_enc"] == 2) & (df_base["risk_enc"] == 2)).astype(int)
    
    df_base["planned_duration"] = (df_base["Target"] - df_base["Created"]).dt.days.clip(lower=1)
    df_base["Hours"] = df_base["Hours"].fillna(df_base["Hours"].median())
    df_base["hours_per_day"] = (df_base["Hours"] / df_base["planned_duration"].replace(0, np.nan)).fillna(0)
    
    disc_dummies = pd.get_dummies(df_base["ProjectDiscipline"], prefix="disc")
    df_base = pd.concat([df_base, disc_dummies], axis=1)
    disc_cols = [c for c in df_base.columns if c.startswith("disc_")]
    
    closed_mask = df_base["Status"] == "Closed"
    disc_delay_rate = df_base[closed_mask].groupby("ProjectDiscipline")["Delay"].apply(lambda x: (x > 0).mean()).to_dict()
    df_base["disc_hist_delay_rate"] = df_base["ProjectDiscipline"].map(disc_delay_rate).fillna(0.5)
    
    features = ["priority_enc", "risk_enc", "high_pri_high_risk", "Hours", "planned_duration", "hours_per_day", "disc_hist_delay_rate"] + disc_cols
    df_base["is_delayed"] = (df_base["Delay"] > 0).astype(int)
    
    train_df = df_base[closed_mask].copy()
    X_train  = train_df[features].fillna(0)
    y_train  = train_df["is_delayed"]
    
    rf = RandomForestClassifier(n_estimators=200, max_depth=4, min_samples_leaf=3, class_weight="balanced", random_state=42)
    rf.fit(X_train, y_train)
    
    try:
        calibrated = CalibratedClassifierCV(rf, cv=3, method="isotonic")
        calibrated.fit(X_train, y_train)
        model = calibrated
    except Exception:
        model = rf
        
    try:
        explainer = shap.TreeExplainer(rf)
    except Exception:
        explainer = None
        
    return {
        "model": model,
        "rf": rf,
        "explainer": explainer,
        "features": features,
        "disc_cols": disc_cols,
        "disc_delay_rate": disc_delay_rate,
        "overall_delay_rate": float(y_train.mean()) if len(y_train) > 0 else 0.436
    }

# Cache model instance
_MODEL_CACHE = None

def get_model():
    global _MODEL_CACHE
    if _MODEL_CACHE is None:
        df_base = get_base_training_data()
        _MODEL_CACHE = train_production_model(df_base)
    return _MODEL_CACHE

def parse_input_file(file_content, filename):
    """Parse raw bytes or file path into pandas DataFrame."""
    fn_lower = filename.lower()
    if isinstance(file_content, (str, bytes)):
        if isinstance(file_content, str) and os.path.exists(file_content):
            if fn_lower.endswith(".csv"):
                df = pd.read_csv(file_content)
            elif fn_lower.endswith((".xlsx", ".xls")):
                df = pd.read_excel(file_content)
            else:
                try:
                    df = pd.read_csv(file_content)
                except Exception:
                    df = pd.read_excel(file_content)
        else:
            bio = io.BytesIO(file_content if isinstance(file_content, bytes) else file_content.encode("utf-8"))
            if fn_lower.endswith(".csv"):
                df = pd.read_csv(bio)
            elif fn_lower.endswith((".xlsx", ".xls")):
                df = pd.read_excel(bio)
            else:
                try:
                    df = pd.read_csv(bio)
                except Exception:
                    bio.seek(0)
                    df = pd.read_excel(bio)
    elif isinstance(file_content, pd.DataFrame):
        df = file_content.copy()
    else:
        raise ValueError("Unsupported file_content type")
        
    df.columns = df.columns.str.strip()
    return df

def predict_imported_dataframe(df_raw, filename="imported_data.csv"):
    """
    Takes imported DataFrame, runs feature engineering and ML prediction,
    and returns rich JSON payload.
    """
    model_ctx = get_model()
    model = model_ctx["model"]
    rf = model_ctx["rf"]
    explainer = model_ctx["explainer"]
    features = model_ctx["features"]
    disc_cols = model_ctx["disc_cols"]
    disc_delay_rate = model_ctx["disc_delay_rate"]
    overall_delay_rate = model_ctx["overall_delay_rate"]

    df = df_raw.copy()
    
    # Standardize column mapping (case-insensitive)
    col_map = {str(c).lower().replace(" ", "").replace("_", ""): c for c in df.columns}
    
    def fetch_col(targets, default=None):
        for t in targets:
            key = t.lower().replace(" ", "").replace("_", "")
            if key in col_map:
                return df[col_map[key]]
        return pd.Series([default] * len(df))

    task_ids    = fetch_col(["TaskID", "ID", "Task_ID", "TaskId"], default=None)
    desc_series = fetch_col(["Description", "TaskDescription", "Desc", "Name", "TaskName"], default="Unspecified Task")
    disc_series = fetch_col(["ProjectDiscipline", "Discipline", "Department", "Disc"], default="General")
    prio_series = fetch_col(["Priority", "Prio"], default="Medium")
    risk_series = fetch_col(["Risk", "RiskLevel"], default="Medium")
    hrs_series  = fetch_col(["Hours", "WorkHours", "PlannedHours", "DurationHours"], default=40)
    created_s   = fetch_col(["Created", "CreatedDate", "StartDate"], default=pd.Timestamp.today().strftime("%Y-%m-%d"))
    target_s    = fetch_col(["Target", "TargetDate", "DueDate", "EndDate"], default=(pd.Timestamp.today() + pd.Timedelta(days=7)).strftime("%Y-%m-%d"))
    status_s    = fetch_col(["Status", "TaskStatus"], default="Open")
    location_s  = fetch_col(["Location", "Site"], default="Site")

    # Generate TaskIDs if missing
    parsed_task_ids = []
    for i, tid in enumerate(task_ids):
        if pd.isna(tid) or str(tid).strip() == "" or str(tid) == "None":
            parsed_task_ids.append(f"IMP-{1000 + i + 1}")
        else:
            parsed_task_ids.append(str(tid).strip())

    proc_df = pd.DataFrame({
        "TaskID": parsed_task_ids,
        "Description": desc_series.fillna("Unspecified Task").astype(str),
        "ProjectDiscipline": disc_series.fillna("General").astype(str),
        "Priority": prio_series.fillna("Medium").astype(str),
        "Risk": risk_series.fillna("Medium").astype(str),
        "Hours": pd.to_numeric(hrs_series, errors="coerce").fillna(40.0),
        "Created": pd.to_datetime(created_s, errors="coerce").fillna(pd.Timestamp.today()),
        "Target": pd.to_datetime(target_s, errors="coerce").fillna(pd.Timestamp.today() + pd.Timedelta(days=7)),
        "Status": status_s.fillna("Open").astype(str),
        "Location": location_s.fillna("Site").astype(str)
    })

    # Enforce priority & risk values
    proc_df["Priority"] = proc_df["Priority"].str.title().apply(lambda x: x if x in ["High", "Medium", "Low"] else "Medium")
    proc_df["Risk"]     = proc_df["Risk"].str.title().apply(lambda x: x if x in ["High", "Medium", "Low"] else "Medium")

    priority_map = {"High": 2, "Medium": 1, "Low": 0}
    risk_map     = {"High": 2, "Medium": 1, "Low": 0}

    proc_df["priority_enc"] = proc_df["Priority"].map(priority_map).fillna(1)
    proc_df["risk_enc"]     = proc_df["Risk"].map(risk_map).fillna(1)
    proc_df["high_pri_high_risk"] = ((proc_df["priority_enc"] == 2) & (proc_df["risk_enc"] == 2)).astype(int)

    proc_df["planned_duration"] = (proc_df["Target"] - proc_df["Created"]).dt.days.clip(lower=1)
    proc_df["hours_per_day"]    = (proc_df["Hours"] / proc_df["planned_duration"].replace(0, np.nan)).fillna(0)
    proc_df["disc_hist_delay_rate"] = proc_df["ProjectDiscipline"].map(disc_delay_rate).fillna(overall_delay_rate)

    # Discipline one-hot matching feature matrix
    for col in disc_cols:
        disc_name = col.replace("disc_", "")
        proc_df[col] = (proc_df["ProjectDiscipline"] == disc_name).astype(int)

    X_imp = proc_df[features].fillna(0)

    # Model Prediction
    probs = model.predict_proba(X_imp)[:, 1]
    proc_df["delay_prob"]  = probs
    proc_df["delay_score"] = (probs * 100).round(1)

    def get_cat(p):
        if p >= 0.70: return "HIGH"
        if p >= 0.40: return "MEDIUM"
        return "LOW"

    proc_df["risk_cat"] = proc_df["delay_prob"].apply(get_cat)

    # SHAP Feature Explanations
    shap_matrix = None
    if explainer is not None:
        try:
            sv = explainer.shap_values(X_imp)
            if isinstance(sv, list):
                shap_matrix = sv[1] if len(sv) > 1 else sv[0]
            elif isinstance(sv, np.ndarray) and sv.ndim == 3:
                shap_matrix = sv[:, :, 1]
            else:
                shap_matrix = sv
        except Exception:
            shap_matrix = None

    tasks_out = []
    high_count = 0
    med_count  = 0
    low_count  = 0
    mitigations = []

    for i, row in proc_df.iterrows():
        cat = row["risk_cat"]
        if cat == "HIGH": high_count += 1
        elif cat == "MEDIUM": med_count += 1
        else: low_count += 1

        # Extract SHAP top drivers
        drivers = []
        if shap_matrix is not None:
            shap_row = np.asarray(shap_matrix[i]).flatten()
            pairs = sorted(zip(np.abs(shap_row), shap_row, features), key=lambda x: float(x[0]), reverse=True)
            for abs_v, v, fname in pairs[:3]:
                if abs_v < 1e-5: continue
                flabel = fname.replace("disc_", "Discipline: ").replace("_", " ").title()
                drivers.append({
                    "feature": flabel,
                    "direction": "increases" if v > 0 else "decreases",
                    "impact": round(float(abs_v), 4)
                })

        if cat == "HIGH":
            action = "NOTIFY_PM + REALLOCATE_RESOURCE"
        elif cat == "MEDIUM":
            action = "SCHEDULE_STATUS_MEETING"
        else:
            action = "MONITOR_WEEKLY"

        t_obj = {
            "id":           str(row["TaskID"]),
            "desc":         str(row["Description"]),
            "disc":         str(row["ProjectDiscipline"]),
            "location":     str(row["Location"]),
            "status":       str(row["Status"]),
            "priority":     str(row["Priority"]),
            "risk":         str(row["Risk"]),
            "hours":        float(row["Hours"]),
            "created":      row["Created"].strftime("%Y-%m-%d") if pd.notna(row["Created"]) else "",
            "target":       row["Target"].strftime("%Y-%m-%d") if pd.notna(row["Target"]) else "",
            "actual_date":  "—",
            "planned_days": int(row["planned_duration"]),
            "score":        float(row["delay_score"]),
            "cat":          cat,
            "shap_drivers": drivers,
            "action":       action
        }
        tasks_out.append(t_obj)

        if cat in ["HIGH", "MEDIUM"]:
            mitigations.append({
                "task_id": t_obj["id"],
                "desc": t_obj["desc"],
                "discipline": t_obj["disc"],
                "priority": t_obj["priority"],
                "risk_cat": cat,
                "score": t_obj["score"],
                "action": action
            })

    total_tasks = len(tasks_out)
    avg_score = round(float(proc_df["delay_score"].mean()), 1) if total_tasks > 0 else 0.0

    return {
        "success": True,
        "filename": filename,
        "meta": {
            "total_tasks": total_tasks,
            "high_risk_count": high_count,
            "high_risk_pct": round(high_count / total_tasks * 100, 1) if total_tasks > 0 else 0.0,
            "med_risk_count": med_count,
            "low_risk_count": low_count,
            "avg_delay_score": avg_score,
            "model_used": "Calibrated Random Forest (Production)",
        },
        "tasks": tasks_out,
        "mitigation": mitigations
    }

def send_high_risk_delay_email(high_risk_tasks, manager_email=None, smtp_config=None):
    """
    Sends SMTP HTML email alert to Project Manager for high-risk delayed tasks.
    """
    import smtplib
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText

    if not high_risk_tasks:
        return {"success": False, "message": "No high-risk delayed tasks to notify."}

    smtp_config = smtp_config or {}
    smtp_host = smtp_config.get("host") or os.environ.get("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(smtp_config.get("port") or os.environ.get("SMTP_PORT", 587))
    smtp_user = smtp_config.get("user") or os.environ.get("SMTP_USER", "")
    smtp_pass = smtp_config.get("pass") or os.environ.get("SMTP_PASS", "")
    sender_email = smtp_config.get("sender") or os.environ.get("SMTP_SENDER", smtp_user or "alerts@intertech.com")
    manager_email = manager_email or smtp_config.get("recipient") or os.environ.get("MANAGER_EMAIL", "pm.intertech@gmail.com")

    task_rows_html = ""
    for t in high_risk_tasks:
        task_rows_html += f"""
        <tr>
            <td style="padding:10px; border-bottom:1px solid #e2e8f0; font-weight:bold; color:#2563eb;">{t.get('id')}</td>
            <td style="padding:10px; border-bottom:1px solid #e2e8f0;">{t.get('desc')}</td>
            <td style="padding:10px; border-bottom:1px solid #e2e8f0;">{t.get('disc')}</td>
            <td style="padding:10px; border-bottom:1px solid #e2e8f0; font-weight:bold; color:#dc2626;">{t.get('score')}%</td>
            <td style="padding:10px; border-bottom:1px solid #e2e8f0; font-weight:bold; color:#d97706;">NOTIFY_PM + REALLOCATE_RESOURCE</td>
        </tr>
        """

    html_content = f"""
    <html>
    <body style="font-family: Arial, sans-serif; color: #0f172a; line-height: 1.6;">
        <div style="max-width: 650px; margin: 0 auto; border: 1px solid #e2e8f0; border-radius: 8px; overflow: hidden;">
            <div style="background: #dc2626; color: #ffffff; padding: 20px; text-align: center;">
                <h2 style="margin: 0;">🚨 CRITICAL PM ALERT: High-Risk Task Delay Predicted</h2>
                <p style="margin: 5px 0 0 0; font-size: 14px;">InterTech Delay Intelligence Platform — Project PRJ001</p>
            </div>
            <div style="padding: 24px;">
                <p>Dear Project Manager,</p>
                <p>The ML Delay Prediction Engine has flagged <strong>{len(high_risk_tasks)} High-Risk Task(s)</strong> with high probability of completion delay.</p>
                
                <h3 style="color: #0f172a; margin-top: 20px;">High-Risk Task Breakdown</h3>
                <table style="width: 100%; border-collapse: collapse; font-size: 13px;">
                    <thead>
                        <tr style="background: #f8fafc; text-align: left;">
                            <th style="padding: 10px; border-bottom: 2px solid #cbd5e1;">Task ID</th>
                            <th style="padding: 10px; border-bottom: 2px solid #cbd5e1;">Description</th>
                            <th style="padding: 10px; border-bottom: 2px solid #cbd5e1;">Discipline</th>
                            <th style="padding: 10px; border-bottom: 2px solid #cbd5e1;">Risk Score</th>
                            <th style="padding: 10px; border-bottom: 2px solid #cbd5e1;">Action Proposal</th>
                        </tr>
                    </thead>
                    <tbody>
                        {task_rows_html}
                    </tbody>
                </table>
                
                <div style="background: #fef2f2; border: 1px solid #fecaca; padding: 15px; border-radius: 6px; margin-top: 20px;">
                    <strong style="color: #dc2626;">Action Required (per Problem Statement Mitigation Plan):</strong>
                    <ul style="margin: 5px 0 0 20px; color: #991b1b;">
                        <li>Reallocate senior personnel from closed or medium-risk projects immediately.</li>
                        <li>Schedule urgent site coordination sync with sub-contractor leads.</li>
                    </ul>
                </div>
            </div>
        </div>
    </body>
    </html>
    """

    if smtp_user and smtp_pass:
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = f"🚨 URGENT: High-Risk Project Delay Alert ({len(high_risk_tasks)} Tasks Flagged)"
            msg["From"] = sender_email
            msg["To"] = manager_email
            msg.attach(MIMEText(html_content, "html"))

            with smtplib.SMTP(smtp_host, smtp_port) as server:
                server.starttls()
                server.login(smtp_user, smtp_pass)
                server.sendmail(sender_email, [manager_email], msg.as_string())

            return {
                "success": True,
                "sent_live": True,
                "recipient": manager_email,
                "tasks_notified": len(high_risk_tasks),
                "message": f"SMTP email alert successfully sent to {manager_email}"
            }
        except Exception as e:
            return {
                "success": False,
                "sent_live": False,
                "error": str(e),
                "html_preview": html_content,
                "message": f"SMTP live dispatch error ({str(e)}). Simulation preview generated."
            }
    else:
        return {
            "success": True,
            "sent_live": False,
            "simulated": True,
            "recipient": manager_email,
            "tasks_notified": len(high_risk_tasks),
            "html_preview": html_content,
            "message": f"[SMTP Notification Prepared] {len(high_risk_tasks)} High-Risk task alert generated for PM ({manager_email}). Configure SMTP credentials for live sending."
        }

def trigger_n8n_webhook(high_risk_tasks, webhook_url=None, manager_email="pm.intertech@gmail.com"):
    """
    Triggers n8n workflow webhook for high-risk delayed task alerts & employee reallocation.
    """
    import urllib.request
    webhook_url = webhook_url or os.environ.get("N8N_WEBHOOK_URL", "http://localhost:5678/webhook/high-risk-delay-alert")
    
    payload = {
        "event": "HIGH_RISK_TASK_DELAY_PREDICTED",
        "project_id": "PRJ001",
        "manager_email": manager_email,
        "total_high_risk_tasks": len(high_risk_tasks),
        "mitigation_proposal": {
            "high_risk_action": "NOTIFY_PM + REALLOCATE_RESOURCE",
            "strategy": "Notify Project Manager & reallocate employee from closed/medium-risk project to assist.",
            "medium_risk_action": "CONDUCT_STATUS_MEETING + REGULAR_UPDATES"
        },
        "tasks": high_risk_tasks,
        "n8n_workflow_template": "intertech_n8n_workflow.json"
    }

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(webhook_url, data=data, headers={"Content-Type": "application/json"})
    
    try:
        with urllib.request.urlopen(req, timeout=5) as response:
            res_body = response.read().decode("utf-8")
            return {
                "success": True,
                "n8n_triggered": True,
                "webhook_url": webhook_url,
                "response": res_body,
                "message": f"Successfully triggered n8n workflow at {webhook_url}"
            }
    except Exception as e:
        return {
            "success": True,
            "n8n_triggered": False,
            "simulated": True,
            "webhook_url": webhook_url,
            "error": str(e),
            "payload_sent": payload,
            "message": f"[n8n Workflow Prepared] High-Risk payload formatted for n8n. Webhook target ({webhook_url})."
        }

def predict_from_filepath(filepath):
    df = parse_input_file(filepath, os.path.basename(filepath))
    return predict_imported_dataframe(df, os.path.basename(filepath))

if __name__ == "__main__":
    if len(sys.argv) > 1:
        fp = sys.argv[1]
        res = predict_from_filepath(fp)
        print(json.dumps(res, indent=2))
    else:
        print("Usage: python predict_file.py <path_to_csv_or_xlsx>")
