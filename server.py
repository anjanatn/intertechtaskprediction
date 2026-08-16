"""
InterTech PRJ001 — Delay Prediction & Mitigation System Server
Serves the web dashboard and REST API for project delay predictions.
"""

import os
import sys
import json
import webbrowser
from http.server import HTTPServer, SimpleHTTPRequestHandler
import subprocess

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def run_ml_pipeline():
    print("[*] Running ML Delay Prediction Pipeline...")
    script_path = os.path.join(BASE_DIR, "train_and_predict.py")
    if not os.path.exists(script_path):
        script_path = os.path.join(BASE_DIR, "Untitled-1.py")
    if os.path.exists(script_path):
        result = subprocess.run([sys.executable, script_path], cwd=BASE_DIR, capture_output=True, text=True, encoding="utf-8", errors="replace")
        if result.stdout:
            try:
                print(result.stdout)
            except UnicodeEncodeError:
                print(result.stdout.encode(sys.stdout.encoding or 'ascii', errors='replace').decode(sys.stdout.encoding or 'ascii'))
        if result.stderr:
            try:
                print("[Stderr]", result.stderr)
            except UnicodeEncodeError:
                print("[Stderr]", result.stderr.encode(sys.stdout.encoding or 'ascii', errors='replace').decode(sys.stdout.encoding or 'ascii'))

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
        elif self.path == "/api/data" or self.path == "/api/run":
            if self.path == "/api/run":
                run_ml_pipeline()
            json_path = os.path.join(BASE_DIR, "dashboard_data.json")
            if not os.path.exists(json_path):
                run_ml_pipeline()
            if os.path.exists(json_path):
                self.send_response(200)
                self.send_header("Content-type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                with open(json_path, "rb") as f:
                    self.wfile.write(f.read())
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
                
                # Check if JSON payload with base64 data
                content_type = self.headers.get('Content-Type', '')
                if 'application/json' in content_type:
                    payload = json.loads(body.decode('utf-8'))
                    filename = payload.get("filename", "uploaded_file.csv")
                    if "filedata_b64" in payload:
                        file_bytes = base64.b64decode(payload["filedata_b64"])
                    elif "csv_text" in payload:
                        file_bytes = payload["csv_text"].encode('utf-8')
                
                res = predict_file.predict_from_filepath(io.BytesIO(file_bytes)) if isinstance(file_bytes, bytes) else predict_file.predict_imported_dataframe(file_bytes, filename)
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
                
                email_res = predict_file.send_high_risk_delay_email(tasks, recipient, smtp_config)
                
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
    print(f" Data API:      {url}/api/data")
    print(f" Retrain API:   {url}/api/run")
    print(f"=======================================================\n")
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
