#!/usr/bin/env python3
"""Sierra Snow dashboard server.

On launch it starts a full data refresh in the background, so the page always
works from the latest model runs, observations and road reports. While it runs:

  full refresh   every 60 min  (models, ensembles, NWS, sensors, soundings, roads)
  roads refresh  every 5 min   (Caltrans chain controls only)

Endpoints
  GET  /                 dashboard
  GET  /api/snow         latest dataset (data/live_snow_data.json)
  GET  /api/status       refresh state: running, per-step progress, last run times
  POST /api/refresh      start a full refresh (returns immediately; poll /api/status)
  GET  /api/roads        road conditions only
  GET  /api/resorts      resort configuration

Usage
  python3 server.py --open            # start, refresh, open browser
  python3 server.py --port 8081
  python3 server.py --no-refresh      # serve existing data only
"""

import argparse
import json
import os
import sys
import threading
import time
from datetime import datetime, timezone
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, parse_qs

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR.parent))
sys.path.insert(0, str(BASE_DIR))

from collectors.aggregator import SnowAggregator  # noqa: E402

DATA_PATH = BASE_DIR / "data" / "live_snow_data.json"
FULL_EVERY_S = 60 * 60
ROADS_EVERY_S = 5 * 60


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class RefreshManager:
    def __init__(self):
        self.lock = threading.Lock()
        self.state = {"running": False, "kind": None, "started_at_utc": None, "finished_at_utc": None,
                      "steps": [], "last_error": None, "last_full_utc": None, "last_roads_utc": None,
                      "data_generated_at_utc": self._data_version()}
        self._last_full = 0.0
        self._last_roads = 0.0

    @staticmethod
    def _data_version():
        try:
            with open(DATA_PATH, "r", encoding="utf-8") as f:
                return json.load(f).get("metadata", {}).get("generated_at_utc")
        except Exception:
            return None

    def status(self):
        with self.lock:
            return json.loads(json.dumps(self.state))

    def _step(self, name, st):
        with self.lock:
            for s in self.state["steps"]:
                if s["name"] == name:
                    s["state"] = st
                    s["at"] = _now()
                    return
            self.state["steps"].append({"name": name, "state": st, "at": _now()})

    def start(self, kind="full") -> bool:
        with self.lock:
            if self.state["running"]:
                return False
            self.state.update({"running": True, "kind": kind, "started_at_utc": _now(), "steps": [], "last_error": None})
        threading.Thread(target=self._run, args=(kind,), daemon=True).start()
        return True

    def _write(self, data):
        DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
        tmp = DATA_PATH.with_suffix(".json.tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f)
        os.replace(tmp, DATA_PATH)

    def _run(self, kind):
        try:
            agg = SnowAggregator(config_dir=BASE_DIR / "config", data_dir=BASE_DIR / "data")
            if kind == "roads":
                self._step("Caltrans chain controls", "running")
                with open(DATA_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                data = agg.refresh_roads(data)
                self._write(data)
                self._step("Caltrans chain controls", "done" if data["road_conditions"].get("is_live_feed") else "stale")
                self._last_roads = time.time()
                with self.lock:
                    self.state["last_roads_utc"] = _now()
            else:
                data = agg.run_aggregation(progress=self._step)
                self._write(data)
                self._last_full = self._last_roads = time.time()
                with self.lock:
                    self.state["last_full_utc"] = self.state["last_roads_utc"] = _now()
        except Exception as e:
            with self.lock:
                self.state["last_error"] = f"{type(e).__name__}: {e}"
        finally:
            with self.lock:
                self.state.update({"running": False, "finished_at_utc": _now(), "data_generated_at_utc": self._data_version()})

    def scheduler(self):
        while True:
            time.sleep(30)
            now = time.time()
            if now - self._last_full >= FULL_EVERY_S:
                self.start("full")
            elif now - self._last_roads >= ROADS_EVERY_S and DATA_PATH.exists():
                self.start("roads")


REFRESH = RefreshManager()


class SnowDashboardHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(BASE_DIR), **kwargs)

    def log_message(self, fmt, *args):  # keep the terminal quiet except for errors
        if len(args) > 1 and str(args[1]).startswith(("4", "5")) and str(args[1]) != "404":
            super().log_message(fmt, *args)

    def end_headers(self):
        self.send_header("Cache-Control", "no-cache")
        super().end_headers()

    def do_GET(self):
        path = urlparse(self.path).path
        if path in ("/", "/dashboard", "/index.html"):
            self.path = "/dashboard.html"
            return super().do_GET()
        if path == "/api/snow":
            return self._file_json(DATA_PATH)
        if path == "/api/status":
            return self._json(REFRESH.status())
        if path == "/api/refresh":
            started = REFRESH.start("full")
            return self._json({"started": started, **REFRESH.status()}, 202 if started else 200)
        if path == "/api/roads":
            try:
                with open(DATA_PATH, "r", encoding="utf-8") as f:
                    return self._json(json.load(f).get("road_conditions", {}))
            except Exception:
                return self._json({"error": "no data yet"}, 503)
        if path == "/api/resorts":
            return self._file_json(BASE_DIR / "config" / "resorts.json")
        if path in ("/api/runs", "/api/run"):
            return self._runs(path, parse_qs(urlparse(self.path).query))
        return super().do_GET()

    def _runs(self, path, q):
        """/api/runs?resort=&model=  -> the model's archived runs, newest first (index.json)
        /api/run?resort=&model=&run=YYYYMMDDHH -> that run's full output"""
        import gzip
        import re
        resort, model, run = (q.get("resort") or [""])[0], (q.get("model") or [""])[0], (q.get("run") or [""])[0]
        if not re.fullmatch(r"[a-z_]+", resort) or not re.fullmatch(r"[a-z0-9_]+(\.corrected)?", model):
            return self._json({"error": "bad resort or model"}, 400)
        d = BASE_DIR / "data" / "models" / resort / "runs" / model
        if path == "/api/runs":
            idx = d / "index.json"
            return self._file_json(idx) if idx.exists() else self._json({"model": model, "runs": []})
        if not re.fullmatch(r"\d{10}", run):
            return self._json({"error": "bad run"}, 400)
        f = d / f"{run}.json.gz"
        if not f.exists():
            return self._json({"error": "run not archived"}, 404)
        body = gzip.decompress(f.read_bytes())
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        if urlparse(self.path).path == "/api/refresh":
            kind = "roads" if "roads" in self.path else "full"
            started = REFRESH.start(kind)
            return self._json({"started": started, **REFRESH.status()}, 202 if started else 200)
        self.send_error(404, "Endpoint not found")

    def _file_json(self, path: Path):
        try:
            body = path.read_bytes()
        except FileNotFoundError:
            return self._json({"error": "no data yet; a refresh is running"}, 503)
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _json(self, data, status=200):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def run_server(port: int = 8080, open_browser: bool = False, refresh: bool = True):
    try:
        httpd = ThreadingHTTPServer(("", port), SnowDashboardHandler)
    except OSError:
        print(f"Port {port} is already in use. Is the dashboard already running? Try: python3 server.py --port {port + 1}")
        sys.exit(1)
    print(f"Sierra Snow dashboard: http://localhost:{port}/")
    if refresh:
        REFRESH.start("full")
        threading.Thread(target=REFRESH.scheduler, daemon=True).start()
        print("Fetching the latest data in the background (full refresh every 60 min, roads every 5 min).")
    if open_browser:
        import webbrowser
        threading.Timer(0.6, lambda: webbrowser.open(f"http://localhost:{port}/")).start()
    print("Press Ctrl+C to stop.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
        httpd.server_close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the Sierra Snow dashboard server.")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--open", action="store_true", help="open the dashboard in your browser")
    parser.add_argument("--no-refresh", action="store_true", help="serve existing data without fetching")
    args = parser.parse_args()
    run_server(args.port, args.open, not args.no_refresh)
