import sys
import os
import subprocess
import threading
import time
from flask import Flask, render_template, jsonify, Response, send_from_directory

app = Flask(__name__, template_folder=os.path.join(os.path.dirname(__file__), "templates"))
TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "templates")
ASSETS_DIR = os.path.join(os.path.dirname(__file__), "assets")

# Global manager state
class ServerManager:
    def __init__(self):
        self.process = None
        self.log_buffer = []
        self.max_log_lines = 1000
        self.lock = threading.RLock()
        self.clients = []
        self.reader_thread = None

    def log(self, line):
        with self.lock:
            # Avoid sending raw carriage returns or extra newlines in SSE JSON/text format
            clean_line = line.replace('\r', '')
            self.log_buffer.append(clean_line)
            if len(self.log_buffer) > self.max_log_lines:
                self.log_buffer.pop(0)
            
            # Broadcast to SSE clients
            for client_queue in list(self.clients):
                client_queue.put(clean_line)

    def reader_loop(self):
        while True:
            proc = None
            with self.lock:
                proc = self.process
            if not proc or proc.poll() is not None:
                break
                
            line = proc.stdout.readline()
            if not line:
                break
            
            try:
                line_str = line.decode('utf-8', errors='replace')
            except Exception:
                line_str = str(line)
            self.log(line_str)
        
        # Process has finished
        exit_code = "unknown"
        with self.lock:
            if self.process:
                exit_code = self.process.poll()
                self.process = None
        
        self.log(f"\n[SYSTEM] Game Server exited with code {exit_code}.\n")

    def start(self):
        with self.lock:
            if self.process and self.process.poll() is None:
                return False, "Server is already running"
            
            self.log("\n[SYSTEM] Starting Game Server...\n")
            try:
                # Run server.py in the same python environment with -u (unbuffered output)
                self.process = subprocess.Popen(
                    [sys.executable, "-u", "server.py"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    cwd=os.path.dirname(os.path.abspath(__file__))
                )
            except Exception as e:
                return False, f"Failed to launch process: {str(e)}"
            
            self.reader_thread = threading.Thread(target=self.reader_loop, daemon=True)
            self.reader_thread.start()
            return True, "Server started"

    def stop(self):
        with self.lock:
            if not self.process or self.process.poll() is not None:
                return False, "Server is not running"
            
            self.log("\n[SYSTEM] Stopping Game Server...\n")
            p = self.process
            p.terminate()
            
            # Watchdog thread to force kill if it doesn't shut down gracefully in 5s
            def force_kill_watchdog():
                time.sleep(5)
                if p.poll() is None:
                    p.kill()
            threading.Thread(target=force_kill_watchdog, daemon=True).start()
            
            self.process = None
            return True, "Server stopping"

    def get_status(self):
        with self.lock:
            if self.process and self.process.poll() is None:
                return "online"
            return "offline"

manager = ServerManager()

@app.route("/")
def index():
    return render_template("runner.html")

@app.route("/img/<path:path>")
def images(path):
    return send_from_directory(os.path.join(TEMPLATES_DIR, "img"), path)

@app.route("/assets/<path:path>")
def assets(path):
    local_path = os.path.join(ASSETS_DIR, path)
    if os.path.exists(local_path):
        return send_from_directory(ASSETS_DIR, path)
    download_assets_path = os.path.join(os.path.dirname(__file__), "download_assets", "assets")
    return send_from_directory(download_assets_path, path)

@app.route("/api/server/status")
def status():
    return jsonify({"status": manager.get_status()})

@app.route("/api/server/start", methods=["POST"])
def start_server():
    success, msg = manager.start()
    return jsonify({"success": success, "message": msg})

@app.route("/api/server/stop", methods=["POST"])
def stop_server():
    success, msg = manager.stop()
    return jsonify({"success": success, "message": msg})

@app.route("/api/server/restart", methods=["POST"])
def restart_server():
    manager.stop()
    time.sleep(1.5)
    success, msg = manager.start()
    return jsonify({"success": success, "message": msg})

@app.route("/api/server/logs")
def logs_stream():
    import queue
    q = queue.Queue()
    
    with manager.lock:
        # Pre-populate with existing logs
        for line in manager.log_buffer:
            q.put(line)
        manager.clients.append(q)
        
    def stream():
        try:
            while True:
                try:
                    line = q.get(timeout=10)
                    yield f"data: {line}\n\n"
                except queue.Empty:
                    yield "data: :ping\n\n"
        finally:
            with manager.lock:
                if q in manager.clients:
                    manager.clients.remove(q)

    return Response(stream(), mimetype="text/event-stream")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5051, debug=False, threaded=True)
