"""
serve_dashboards.py
One-click multi-port server for all 4 vehicle audition dashboards:
- Unified Portal: http://localhost:8080/
- Dodge Hellcat:  http://localhost:8088/
- Ferrari 458:   http://localhost:8089/
- Lexus LFA:     http://localhost:8090/
- Nissan GT-R:   http://localhost:8091/
"""

import http.server
import socketserver
import threading
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

SERVERS = [
    {"name": "Unified Portal", "dir": BASE_DIR, "port": 8080},
    {"name": "Dodge Hellcat", "dir": BASE_DIR / "s12-stage-ad-hellcat-closed-loop-v1", "port": 8088},
    {"name": "Ferrari 458", "dir": BASE_DIR / "s12-stage-ad-ferrari-458-closed-loop-v1", "port": 8089},
    {"name": "Lexus LFA", "dir": BASE_DIR / "s12-stage-ad-lfa-closed-loop-v1", "port": 8090},
    {"name": "Nissan GT-R", "dir": BASE_DIR / "s12-stage-ad-gtr-r35-closed-loop-v1", "port": 8091},
]

class CustomHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate')
        self.send_header('Access-Control-Allow-Origin', '*')
        super().end_headers()

def run_server(name, directory, port):
    def handler_factory(*args, **kwargs):
        return CustomHandler(*args, directory=str(directory), **kwargs)
    
    try:
        with socketserver.TCPServer(("", port), handler_factory) as httpd:
            print(f"[{name}] Serving at http://localhost:{port}/ (Directory: {directory})")
            httpd.serve_forever()
    except OSError as e:
        print(f"[{name}] Port {port} might already be active: {e}")

def main():
    print("=" * 60)
    print("🚀 S12 物理声学引擎 4车型对比评审服务启动器")
    print("=" * 60)
    threads = []
    for s in SERVERS:
        if s["dir"].exists():
            t = threading.Thread(target=run_server, args=(s["name"], s["dir"], s["port"]), daemon=True)
            t.start()
            threads.append(t)
        else:
            print(f"⚠️ Warning: Directory not found: {s['dir']}")
    
    print("\n👉 所有服务已在后台就绪，按 Ctrl+C 退出。")
    try:
        for t in threads:
            t.join()
    except KeyboardInterrupt:
        print("\n🛑 停止所有评审服务。")

if __name__ == "__main__":
    main()
