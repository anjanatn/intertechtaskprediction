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
 df_base["Target"] = pd.to_datetime(df_base["Target"], errors="coerce")
 
 priority_map = {"High": 2, "Medium": 1, "Low": 0}
 risk_map = {"High": 2, "Medium": 1, "Low": 0}
 
 df_base["priority_enc"] = df_base["Priority"].map(priority_map).fillna(1)
 df_base["risk_enc"] = df_base["Risk"].map(risk_map).fillna(1)
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
 X_train = train_df[features].fillna(0)
 y_train = train_df["is_delayed"]
 
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

 task_ids = fetch_col(["TaskID", "ID", "Task_ID", "TaskId"], default=None)
 desc_series = fetch_col(["Description", "TaskDescription", "Desc", "Name", "TaskName"], default="Unspecified Task")
 disc_series = fetch_col(["ProjectDiscipline", "Discipline", "Department", "Disc"], default="General")
 prio_series = fetch_col(["Priority", "Prio"], default="Medium")
 risk_series = fetch_col(["Risk", "RiskLevel"], default="Medium")
 hrs_series = fetch_col(["Hours", "WorkHours", "PlannedHours", "DurationHours"], default=40)
 created_s = fetch_col(["Created", "CreatedDate", "StartDate"], default=pd.Timestamp.today().strftime("%Y-%m-%d"))
 target_s = fetch_col(["Target", "TargetDate", "DueDate", "EndDate"], default=(pd.Timestamp.today() + pd.Timedelta(days=7)).strftime("%Y-%m-%d"))
 status_s = fetch_col(["Status", "TaskStatus"], default="Open")
 location_s = fetch_col(["Location", "Site"], default="Site")

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
 proc_df["Risk"] = proc_df["Risk"].str.title().apply(lambda x: x if x in ["High", "Medium", "Low"] else "Medium")

 priority_map = {"High": 2, "Medium": 1, "Low": 0}
 risk_map = {"High": 2, "Medium": 1, "Low": 0}

 proc_df["priority_enc"] = proc_df["Priority"].map(priority_map).fillna(1)
 proc_df["risk_enc"] = proc_df["Risk"].map(risk_map).fillna(1)
 proc_df["high_pri_high_risk"] = ((proc_df["priority_enc"] == 2) & (proc_df["risk_enc"] == 2)).astype(int)

 proc_df["planned_duration"] = (proc_df["Target"] - proc_df["Created"]).dt.days.clip(lower=1)
 proc_df["hours_per_day"] = (proc_df["Hours"] / proc_df["planned_duration"].replace(0, np.nan)).fillna(0)
 proc_df["disc_hist_delay_rate"] = proc_df["ProjectDiscipline"].map(disc_delay_rate).fillna(overall_delay_rate)

 # Discipline one-hot matching feature matrix
 for col in disc_cols:
 disc_name = col.replace("disc_", "")
 proc_df[col] = (proc_df["ProjectDiscipline"] == disc_name).astype(int)

 X_imp = proc_df[features].fillna(0)

 # Model Prediction
 probs = model.predict_proba(X_imp)[:, 1]
 proc_df["delay_prob"] = probs
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
 med_count = 0
 low_count = 0
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
 "id": str(row["TaskID"]),
 "desc": str(row["Description"]),
 "disc": str(row["ProjectDiscipline"]),
 "location": str(row["Location"]),
 "status": str(row["Status"]),
 "priority": str(row["Priority"]),
 "risk": str(row["Risk"]),
 "hours": float(row["Hours"]),
 "created": row["Created"].strftime("%Y-%m-%d") if pd.notna(row["Created"]) else "",
 "target": row["Target"].strftime("%Y-%m-%d") if pd.notna(row["Target"]) else "",
 "actual_date": "—",
 "planned_days": int(row["planned_duration"]),
 "score": float(row["delay_score"]),
 "cat": cat,
 "shap_drivers": drivers,
 "action": action
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

def send_high_risk_delay_email(high_risk_tasks, manager_email=None, smtp_config=None, alert_type=None):
    """Send the four-phase high-risk response email from the local server."""
    import datetime as dt
    import html
    import smtplib
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText
    from zoneinfo import ZoneInfo

    if not high_risk_tasks:
        return {"success": False, "message": "No high-risk delayed tasks to notify."}

    smtp_config = smtp_config or {}
    smtp_host = smtp_config.get("host") or os.environ.get("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(smtp_config.get("port") or os.environ.get("SMTP_PORT", 587))
    smtp_user = smtp_config.get("user") or os.environ.get("SMTP_USER", "")
    smtp_pass = smtp_config.get("pass") or os.environ.get("SMTP_PASS", "")
    sender_email = smtp_config.get("sender") or os.environ.get("SMTP_SENDER", smtp_user or "alerts@intertech.com")
    manager_email = manager_email or smtp_config.get("recipient") or os.environ.get("MANAGER_EMAIL", "pm.intertech@gmail.com")
    is_response = alert_type in (None, "high_risk_response")
    is_meeting = alert_type in ("schedule_meeting", "site_inspection_meeting")
    first = high_risk_tasks[0]
    task_id = first.get("id") or first.get("task_id") or first.get("TaskID") or "HIGH-RISK-TASK"
    score = round(float(first.get("score") or first.get("delay_score") or 0))
    resource_manager = smtp_config.get("resource_manager_email") or os.environ.get("RESOURCE_MANAGER_EMAIL", "")
    task_lead = smtp_config.get("task_lead_email") or os.environ.get("TASK_LEAD_EMAIL", "")
    attendees = list(dict.fromkeys(email for email in [manager_email, resource_manager, task_lead] if email and "@" in email))

    rows = "".join(
        f"<tr><td style='padding:10px;border-bottom:1px solid #e2e8f0;font-weight:700;color:#2563eb'>{html.escape(str(t.get('id') or t.get('TaskID') or ''))}</td>"
        f"<td style='padding:10px;border-bottom:1px solid #e2e8f0'>{html.escape(str(t.get('desc') or t.get('description') or t.get('Description') or ''))}</td>"
        f"<td style='padding:10px;border-bottom:1px solid #e2e8f0'>{html.escape(str(t.get('disc') or t.get('discipline') or t.get('ProjectDiscipline') or 'General'))}</td>"
        f"<td style='padding:10px;border-bottom:1px solid #e2e8f0;font-weight:800;color:#dc2626'>{round(float(t.get('score') or t.get('delay_score') or 0))}%</td>"
        f"<td style='padding:10px;border-bottom:1px solid #e2e8f0;font-weight:700;color:#b45309'>{html.escape(str(t.get('action') or 'NOTIFY_PM + REALLOCATE_RESOURCE'))}</td></tr>"
        for t in high_risk_tasks
    )
    table = f"<h3>High-Risk Task Breakdown</h3><table style='width:100%;border-collapse:collapse;font-size:13px'><thead><tr style='background:#f8fafc;text-align:left'><th style='padding:10px'>Task ID</th><th style='padding:10px'>Description</th><th style='padding:10px'>Discipline</th><th style='padding:10px'>Risk score</th><th style='padding:10px'>Action</th></tr></thead><tbody>{rows}</tbody></table>"
    due_at = dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=2)

    if is_response:
        subject = f"{task_id} HIGH RISK"
        phase_html = f"""
        <div style='border-left:4px solid #dc2626;background:#fef2f2;padding:14px 16px;margin-top:18px'><strong>PHASE 1 — IMMEDIATE ALERT (Hour 0)</strong><ul><li>PM alert issued: <strong>{html.escape(task_id)} HIGH RISK</strong>.</li><li>Action notification issued by email: <strong>Needs action NOW</strong>.</li><li>Create Jira ticket: <strong>URGENT: Reallocate resources for {html.escape(task_id)}</strong>.</li></ul></div>
        <div style='border-left:4px solid #2563eb;background:#eff6ff;padding:14px 16px;margin-top:12px'><strong>PHASE 2 — STRUCTURED ACTION (Hour 1)</strong><ul><li>15-minute Resource Review Call invitation attached for PM, Resource Manager, and task lead.</li><li>Agenda: who to reallocate; daily stand-ups; escalation path if no resources are available.</li><li>Calendar reminder included.</li></ul></div>
        <div style='border-left:4px solid #b45309;background:#fffbeb;padding:14px 16px;margin-top:12px'><strong>PHASE 3 — EXECUTION TRACKING (Hour 2+)</strong><ul><li>Record who moved, date/time, and why in the ticket.</li><li>Daily 9:00 AM stand-up for two weeks attached.</li><li>Alert if hours are above 80% while completion remains below 75%.</li><li>Escalate if PM confirmation is missing after two hours.</li></ul></div>
        <div style='border-left:4px solid #475569;background:#f8fafc;padding:14px 16px;margin-top:12px'><strong>PHASE 4 — ONGOING MONITORING</strong><ul><li>Log stand-up notes and review weekly hours versus plan.</li><li>Log the outcome for model-retraining review when the task completes.</li></ul></div>"""
        heading = f"{html.escape(task_id)} HIGH RISK ({score}%)"
        intro = f"The model has flagged <strong>{html.escape(task_id)}</strong> as <strong style='color:#b91c1c'>HIGH RISK ({score}%)</strong>. This email is the immediate action notification in place of Slack."
    else:
        subject = f"ACTION REQUIRED: Schedule Status Meeting ({len(high_risk_tasks)} Task{'s' if len(high_risk_tasks) != 1 else ''})" if is_meeting else f"URGENT: High-Risk Project Delay Alert ({len(high_risk_tasks)} Tasks Flagged)"
        heading = "ACTION REQUIRED: Schedule Status Meeting" if is_meeting else "CRITICAL PM ALERT: High-Risk Task Delay Predicted"
        intro = "Schedule a status meeting to review the delay risk, owners, and update cadence." if is_meeting else f"The ML Delay Prediction Engine has flagged <strong>{len(high_risk_tasks)} High-Risk Task(s)</strong> with a high probability of completion delay."
        phase_html = "<div style='background:#fef2f2;border:1px solid #fecaca;padding:15px;border-radius:6px;margin-top:20px'><strong style='color:#dc2626'>Action required:</strong><ul><li>Reallocate senior personnel from closed or medium-risk tasks.</li><li>Schedule an urgent coordination sync with delivery leads.</li></ul></div>"

    html_content = f"""<html><body style='font-family:Arial,sans-serif;color:#0f172a;line-height:1.55'><div style='max-width:680px;margin:0 auto;border:1px solid #fecaca;border-radius:9px;overflow:hidden'><div style='background:#b91c1c;color:#fff;padding:22px;text-align:center'><h1 style='font-size:24px;margin:0'>{heading}</h1><p style='margin:5px 0 0;font-size:13px'>InterTech Delay Intelligence Platform — PRJ001</p></div><div style='padding:24px'><p>Dear Project Manager,</p><p>{intro}</p>{table}{phase_html}</div></div></body></html>"""

    if not (smtp_user and smtp_pass):
        return {"success": False, "sent_live": False, "simulated": True, "requires_credentials": True, "recipient": manager_email, "tasks_notified": len(high_risk_tasks), "html_preview": html_content, "message": f"SMTP credentials are missing. Add an SMTP username and app password before sending the {task_id} response."}

    try:
        msg = MIMEMultipart("mixed")
        msg["Subject"] = subject
        msg["From"] = sender_email
        msg["To"] = manager_email
        if resource_manager or task_lead:
            msg["Cc"] = ", ".join(email for email in [resource_manager, task_lead] if email and email != manager_email)
        alternative = MIMEMultipart("alternative")
        alternative.attach(MIMEText(html_content, "html"))
        msg.attach(alternative)

        if is_response:
            timezone_name = smtp_config.get("calendar_timezone") or os.environ.get("CALENDAR_TIMEZONE", "Asia/Kolkata")
            try:
                tz = ZoneInfo(timezone_name)
            except Exception:
                timezone_name, tz = "UTC", dt.timezone.utc
            now = dt.datetime.now(dt.timezone.utc)
            review_start, review_end = now + dt.timedelta(hours=1), now + dt.timedelta(hours=1, minutes=15)
            local_tomorrow = (dt.datetime.now(tz) + dt.timedelta(days=1)).date()
            standup_start = dt.datetime.combine(local_tomorrow, dt.time(9), tzinfo=tz).astimezone(dt.timezone.utc)
            standup_end = standup_start + dt.timedelta(minutes=15)
            def ics_time(value): return value.strftime("%Y%m%dT%H%M%SZ")
            def invite(uid, summary, description, start, end, recurrence=""):
                people = "\r\n".join(f"ATTENDEE;ROLE=REQ-PARTICIPANT;RSVP=TRUE:mailto:{email}" for email in attendees)
                return "\r\n".join(["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//InterTech//High Risk Response//EN", "METHOD:REQUEST", "BEGIN:VEVENT", f"UID:{uid}", f"DTSTAMP:{ics_time(now)}", f"DTSTART:{ics_time(start)}", f"DTEND:{ics_time(end)}", f"SUMMARY:{summary}", f"DESCRIPTION:{description}", f"ORGANIZER:mailto:{sender_email}", people, recurrence, "BEGIN:VALARM", "TRIGGER:-PT15M", "ACTION:DISPLAY", f"DESCRIPTION:{summary}", "END:VALARM", "END:VEVENT", "END:VCALENDAR"])
            review_ics = invite(f"{task_id}-resource-review-{int(review_start.timestamp())}@intertech", f"Resource Review Call — {task_id} HIGH RISK", "Agenda: reallocate from closed/medium-risk tasks; daily stand-ups; escalation path.", review_start, review_end)
            standup_ics = invite(f"{task_id}-daily-standup-{int(standup_start.timestamp())}@intertech", f"Daily Stand-up — {task_id} Resource Recovery", f"Daily 9:00 AM {timezone_name} stand-up for the next two weeks.", standup_start, standup_end, "RRULE:FREQ=DAILY;COUNT=14")
            for filename, content in [(f"{task_id}-resource-review.ics", review_ics), (f"{task_id}-daily-standup.ics", standup_ics)]:
                part = MIMEText(content, "calendar", "utf-8")
                part.add_header("Content-Disposition", "attachment", filename=filename)
                msg.attach(part)

        recipients = list(dict.fromkeys([manager_email] + [email for email in [resource_manager, task_lead] if email]))
        if smtp_port == 465:
            with smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=15) as server:
                server.login(smtp_user, smtp_pass)
                server.sendmail(sender_email, recipients, msg.as_string())
        else:
            with smtplib.SMTP(smtp_host, smtp_port, timeout=15) as server:
                server.starttls()
                server.login(smtp_user, smtp_pass)
                server.sendmail(sender_email, recipients, msg.as_string())
        return {"success": True, "sent_live": True, "recipient": manager_email, "tasks_notified": len(high_risk_tasks), "subject": subject, "workflow": {"phase1": {"pm_email": "sent", "jira_ticket": {"created": False, "status": "configure Jira in the Vercel API for ticket creation"}}, "phase2": {"resource_review_invite": "sent", "attendees": attendees}, "phase3": {"daily_standup_invite": "sent", "confirmation_due_at": due_at.isoformat(), "tracking_rule": "Alert if Hours >80% without task completion >75%"}} if is_response else None, "message": f"SMTP high-risk response sent to {manager_email}."}
    except Exception as exc:
        return {"success": False, "sent_live": False, "error": str(exc), "html_preview": html_content, "message": f"SMTP dispatch error ({exc}). Check the SMTP host, port, user, and app password."}

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
