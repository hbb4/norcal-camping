#!/usr/bin/env python3
"""Lightweight HTTP & API Server for Ski Resort Snow Dashboard.

Serves the interactive dashboard and provides live data refresh endpoints:
- GET /                    -> dashboard.html
- GET /api/snow            -> returns latest consolidated JSON (snow + roads)
- GET /api/roads           -> returns latest Caltrans road conditions
- GET /api/refresh         -> triggers live collector refresh and returns updated JSON
- GET /api/resorts         -> returns active resort configuration

Usage:
    python3 server.py
    python3 server.py --port 8080
"""

import sys
import os
import json
import argparse
from pathlib import Path
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR.parent))
sys.path.insert(0, str(BASE_DIR))

from collectors.aggregator import SnowAggregator


class SnowDashboardHandler(SimpleHTTPRequestHandler):
    """Custom HTTP handler serving files and dynamic snow data API."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(BASE_DIR), **kwargs)

    def do_GET(self):
        parsed = urlparse(self.path)

        if parsed.path in ("/", "/dashboard", "/index.html"):
            self.path = "/dashboard.html"
            return super().do_GET()

        elif parsed.path == "/api/snow":
            self._handle_api_snow()
            return

        elif parsed.path == "/api/roads":
            self._handle_api_roads()
            return

        elif parsed.path == "/api/refresh":
            self._handle_api_refresh()
            return

        elif parsed.path == "/api/resorts":
            self._handle_api_resorts()
            return

        return super().do_GET()

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/refresh":
            self._handle_api_refresh()
            return
        self.send_error(404, "Endpoint not found")

    def _handle_api_snow(self):
        data_path = BASE_DIR / "data" / "live_snow_data.json"
        if not data_path.exists():
            aggregator = SnowAggregator(config_dir=BASE_DIR / "config")
            data = aggregator.run_aggregation()
            with open(data_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        else:
            with open(data_path, "r", encoding="utf-8") as f:
                data = json.load(f)

        self._send_json_response(data)

    def _handle_api_roads(self):
        data_path = BASE_DIR / "data" / "live_snow_data.json"
        if data_path.exists():
            with open(data_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._send_json_response(data.get("road_conditions", {}))
        else:
            self._handle_api_snow()

    def _handle_api_refresh(self):
        try:
            aggregator = SnowAggregator(config_dir=BASE_DIR / "config")
            data = aggregator.run_aggregation()
            data_path = BASE_DIR / "data" / "live_snow_data.json"
            data_path.parent.mkdir(parents=True, exist_ok=True)
            with open(data_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            self._send_json_response({"status": "success", "message": "Refreshed live snow and road data", "data": data})
        except Exception as e:
            self._send_json_response({"status": "error", "message": str(e)}, status_code=500)

    def _handle_api_resorts(self):
        resorts_path = BASE_DIR / "config" / "resorts.json"
        with open(resorts_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self._send_json_response(data)

    def _send_json_response(self, data: dict, status_code: int = 200):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)


def run_server(port: int = 8080):
    server_address = ("", port)
    httpd = HTTPServer(server_address, SnowDashboardHandler)
    print(f"❄️  Ski Resort Snow Dashboard running at http://localhost:{port}/")
    print(f"📊 Dashboard: http://localhost:{port}/dashboard.html")
    print(f"⚡ Live API:  http://localhost:{port}/api/snow")
    print(f"🚗 Road API:  http://localhost:{port}/api/roads")
    print("Press Ctrl+C to stop.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server.")
        httpd.server_close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run Ski Resort Snow Dashboard server.")
    parser.add_argument("--port", type=int, default=8080, help="Port to serve on (default: 8080)")
    args = parser.parse_args()
    run_server(args.port)
