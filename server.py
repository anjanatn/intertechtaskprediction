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
