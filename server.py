"""
InterTech PRJ001 — Delay Prediction & Mitigation System Server
Serves the web dashboard and REST API for project delay predictions.
"""

import os
import sys
import json
import time
import io
import webbrowser
from http.server import HTTPServer, SimpleHTTPRequestHandler
import subprocess

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# In-memory cache for /api/data (60-second TTL)
_data_cache = {"data": None, "expires": 0}


def run_ml_pipeline():
    print("[*] Running ML Delay Prediction Pipeline...")
    script_path = os.path.join(BASE_DIR, "train_and_predict.py")
    if not os.path.exists(script_path):
        script_path = os.path.join(BASE_DIR, "Untitled-1.py")
    if os.path.exists(script_path):
        result = subprocess.run([sys.executable, script_path], cwd=BASE_DIR,
                                capture_output=True, text=True, encoding="utf-8", errors="replace")
        if result.stdout:
            try:
                print(result.stdout)
            except UnicodeEncodeError:
                print(result.stdout.encode(sys.stdout.encoding or 'ascii',
                      errors='replace').decode(sys.stdout.encoding or 'ascii'))
        if result.stderr:
            try:
                print("[Stderr]", result.stderr)
            except UnicodeEncodeError:
                print("[Stderr]", result.stderr.encode(sys.stdout.encoding or 'ascii',
                      errors='replace').decode(sys.stdout.encoding or 'ascii'))


class CustomHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=BASE_DIR, **kwargs)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        if self.path == "/" or self.path == "/index.html":
            self.path = "/index.html"
        elif self.path == "/api/model_registry":
            reg_path = os.path.join(BASE_DIR, "model_registry", "registry.json")
            if os.path.exists(reg_path):
                with open(reg_path, "rb") as f:
                    reg_data = f.read()
            else:
                reg_data = b"[]"
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(reg_data)
            return
        elif self.path == "/api/data" or self.path == "/api/run":
            if self.path == "/api/run":
                run_ml_pipeline()
                _data_cache["expires"] = 0  # invalidate cache
            json_path = os.path.join(BASE_DIR, "dashboard_data.json")
            if not os.path.exists(json_path):
                run_ml_pipeline()
            now = time.time()
            if self.path != "/api/run" and _data_cache["data"] and now < _data_cache["expires"]:
                self.send_response(200)
                self.send_header("Content-type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("X-Cache", "HIT")
                self.end_headers()
                self.wfile.write(_data_cache["data"])
                return
            if os.path.exists(json_path):
                self.send_response(200)
                self.send_header("Content-type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("X-Cache", "MISS")
                self.end_headers()
                with open(json_path, "rb") as f:
                    payload = f.read()
                    _data_cache["data"] = payload
                    _data_cache["expires"] = now + 60
                    self.wfile.write(payload)
            else:
                self.send_response(500)
                self.send_header("Content-type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"error": "dashboard_data.json not found"}')
            return
        return super().do_GET()

    def do_POST(self):
        if self.path == "/api/predict_file":
            try:
                content_length = int(self.headers.get('Content-Length', 0))
                body = self.rfile.read(content_length)

                import base64
                import predict_file

                filename = "uploaded_file.csv"
                file_bytes = body

                content_type = self.headers.get('Content-Type', '')
                if 'application/json' in content_type:
                    payload = json.loads(body.decode('utf-8'))
                    filename = payload.get("filename", "uploaded_file.csv")
                    if "filedata_b64" in payload:
                        file_bytes = base64.b64decode(payload["filedata_b64"])
                    elif "csv_text" in payload:
                        file_bytes = payload["csv_text"].encode('utf-8')

                res = predict_file.predict_from_filepath(io.BytesIO(file_bytes)) if isinstance(
                    file_bytes, bytes) else predict_file.predict_imported_dataframe(file_bytes, filename)
                res["filename"] = filename

                response_bytes = json.dumps(res).encode('utf-8')
                self.send_response(200)
                self.send_header("Content-type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(response_bytes)
            except Exception as e:
                self.send_response(500)
                self.send_header("Content-type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                err_res = {"success": False, "error": str(e)}
                self.wfile.write(json.dumps(err_res).encode('utf-8'))
            return
        elif self.path == "/api/send_email":
            try:
                content_length = int(self.headers.get('Content-Length', 0))
                body = self.rfile.read(content_length)
                payload = json.loads(body.decode('utf-8')) if body else {}

                import predict_file
                tasks = payload.get("tasks", [])
                recipient = payload.get("recipient", "pm.intertech@gmail.com")
                smtp_config = payload.get("smtp_config", {})

                email_res = predict_file.send_high_risk_delay_email(
                    tasks, recipient, smtp_config)

                self.send_response(200)
                self.send_header("Content-type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(json.dumps(email_res).encode('utf-8'))
            except Exception as e:
                self.send_response(500)
                self.send_header("Content-type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                err_res = {"success": False, "error": str(e)}
                self.wfile.write(json.dumps(err_res).encode('utf-8'))
            return
        elif self.path == "/api/model_registry":
            try:
                content_length = int(self.headers.get('Content-Length', 0))
                body = self.rfile.read(content_length)
                payload = json.loads(body.decode('utf-8')) if body else {}
                activate_version = payload.get("activate_version")
                reg_path = os.path.join(BASE_DIR, "model_registry", "registry.json")
                if not os.path.exists(reg_path):
                    raise FileNotFoundError("registry.json not found")
                with open(reg_path) as f:
                    registry = json.load(f)
                target = next((r for r in registry if r["version"] == activate_version), None)
                if not target:
                    raise ValueError(f"Version {activate_version} not found in registry")
                snap_path = os.path.join(BASE_DIR, "model_registry", target["file"])
                import shutil
                shutil.copy(snap_path, os.path.join(BASE_DIR, "dashboard_data.json"))
                shutil.copy(snap_path, os.path.join(BASE_DIR, "public", "dashboard_data.json"))
                for r in registry:
                    r["active"] = (r["version"] == activate_version)
                with open(reg_path, "w") as f:
                    json.dump(registry, f, indent=2)
                _data_cache["expires"] = 0  # invalidate cache
                result = {"success": True, "activated_version": activate_version, "file": target["file"]}
                self.send_response(200)
                self.send_header("Content-type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(json.dumps(result).encode('utf-8'))
            except Exception as e:
                self.send_response(500)
                self.send_header("Content-type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(json.dumps({"success": False, "error": str(e)}).encode('utf-8'))
            return
        elif self.path == "/api/n8n_webhook":
            try:
                content_length = int(self.headers.get('Content-Length', 0))
                body = self.rfile.read(content_length)
                payload = json.loads(body.decode('utf-8')) if body else {}

                import predict_file
                tasks = payload.get("tasks", [])
                webhook_url = payload.get("webhook_url", "http://localhost:5678/webhook/high-risk-delay-alert")
                recipient = payload.get("recipient", "pm.intertech@gmail.com")

                n8n_res = predict_file.trigger_n8n_webhook(tasks, webhook_url, recipient)

                self.send_response(200)
                self.send_header("Content-type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(json.dumps(n8n_res).encode('utf-8'))
            except Exception as e:
                self.send_response(500)
                self.send_header("Content-type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                err_res = {"success": False, "error": str(e)}
                self.wfile.write(json.dumps(err_res).encode('utf-8'))
            return
        elif self.path == "/api/assistant":
            try:
                content_length = int(self.headers.get('Content-Length', 0))
                body = self.rfile.read(content_length)
                payload = json.loads(body.decode('utf-8')) if body else {}

                message = payload.get("message", "")
                dataset_mode = payload.get("dataset_mode", "test").lower()
                custom_tasks = payload.get("tasks", [])

                json_path = os.path.join(BASE_DIR, "dashboard_data.json")
                dashboard_data = {}
                if os.path.exists(json_path):
                    try:
                        with open(json_path, "r", encoding="utf-8") as f:
                            dashboard_data = json.load(f)
                    except Exception:
                        pass

                tasks = dashboard_data.get("tasks", [])
                if dataset_mode == "test" and custom_tasks:
                    tasks = custom_tasks

                is_test_data = (dataset_mode == "test")
                open_high_risk = [t for t in tasks if t.get("cat") == "HIGH"]
                lower = message.lower()

                if "high risk" in lower or "highest risk" in lower or "open task" in lower or "at risk" in lower:
                    reply = f"**High Risk Tasks Summary ({'Test Data' if is_test_data else 'Train Data'}):**\nThere are **{len(open_high_risk)} tasks** currently classified in the **HIGH Risk Tier** (Probability >= 70%).\n\nTop Priority Actions:\n" + \
                        ("\n".join([f"- **{t.get('id')} ({t.get('desc', 'Task')})**: Discipline: {t.get('disc', 'General')}, Risk Score: {t.get('score', 75)}%. *Action: {t.get('action', 'NOTIFY_PM + REALLOCATE_RESOURCE')}.*" for t in open_high_risk[:5]])
                         if open_high_risk else "No High Risk tasks flagged in this dataset.")
                elif "model" in lower or "xgboost" in lower or "random forest" in lower or "algorithm" in lower or "compare" in lower:
                    reply = f"**ML Model Status ({'Evaluated on Test Set' if is_test_data else 'Active Model'}):**\n\n" + \
                        "- **Predictive AI Engine**: Active task delay prediction model\n" + \
                        "  - Target: Binary Delay > 0 (1 = Delayed, 0 = On-time)\n" + \
                        "  - Priority Actions: High Risk (>=70%): Notify PM + Reallocate Resource; Medium Risk (40-69%): Schedule Status Meeting; Low Risk (<40%): Monitor Weekly.\n\n" + \
                        "For technical model validation and governance details, please open the Model Card on the top app bar."
                elif "delay rate" in lower or "discipline" in lower or "site" in lower or "mep" in lower:
                    disc_counts = {}
                    for t in tasks:
                        d = t.get("disc", "General")
                        if d not in disc_counts:
                            disc_counts[d] = {"total": 0, "high": 0}
                        disc_counts[d]["total"] += 1
                        if t.get("cat") == "HIGH":
                            disc_counts[d]["high"] += 1
                    lines = [f"- **{disc}**: {(info['high']/info['total']*100):.1f}% High-Risk rate ({info['high']} high-risk out of {info['total']} total tasks)" for disc, info in disc_counts.items() if info["total"] > 0]
                    reply = f"**Discipline Delay & Risk Rate Breakdown ({'Test Data' if is_test_data else 'Train Data'}):**\n" + "\n".join(lines)
                elif "mitigation" in lower or "action" in lower or "reallocate" in lower:
                    reply = "**Mitigation Protocols per Problem Statement:**\n" + \
                        "- **High-Risk Tasks (Probability >= 70%)**: Trigger action tag `NOTIFY_PM + REALLOCATE_RESOURCE`. Notify PM via SMTP alert and reallocate senior personnel from completed or low/medium-risk projects.\n" + \
                        "- **Medium-Risk Tasks (40% - 69%)**: Trigger action tag `SCHEDULE_STATUS_MEETING`. Schedule mandatory sync with discipline leads and require daily progress updates.\n" + \
                        "- **Low-Risk Tasks (< 40%)**: Monitor weekly in standard progress meetings."
                else:
                    reply = f"**Project PRJ001 Delay Intelligence Snapshot ({'Mode: Test Data' if is_test_data else 'Mode: Train Data'}):**\n" + \
                        f"- **Active Dataset**: {'Test Data (Imported Predictions)' if is_test_data else 'Train Data (Historical Dataset)'}\n" + \
                        f"- **Total Analyzed Tasks**: {len(tasks)}\n" + \
                        f"- **High-Risk Tasks**: {len(open_high_risk)}\n" + \
                        f"- **Engine Status**: Active Predictive AI Engine"

                res = {"reply": reply, "source": "local", "dataset_mode": dataset_mode}
                self.send_response(200)
                self.send_header("Content-type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(json.dumps(res).encode('utf-8'))
            except Exception as e:
                self.send_response(500)
                self.send_header("Content-type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                err_res = {"success": False, "error": str(e)}
                self.wfile.write(json.dumps(err_res).encode('utf-8'))
            return

        self.send_response(404)
        self.end_headers()


def start_server(port=8080):
    json_path = os.path.join(BASE_DIR, "dashboard_data.json")
    if not os.path.exists(json_path):
        run_ml_pipeline()

    server_address = ("", port)
    httpd = HTTPServer(server_address, CustomHandler)
    url = f"http://localhost:{port}"
    print(f"\n=======================================================")
    print(f" [SUCCESS] InterTech Delay Prediction Dashboard is Live!")
    print(f" Dashboard URL: {url}")
    print(f" Data API: {url}/api/data")
    print(f" Retrain API: {url}/api/run")
    print(f"=======================================================\n")

    try:
        webbrowser.open(url)
    except Exception:
        pass

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[*] Server stopped.")
        httpd.server_close()


if __name__ == "__main__":
    port = 8080
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            pass
    start_server(port)
