"""Synthetic dataplane for the separate Grafana integration test deployment."""
import json
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class Fixture(BaseHTTPRequestHandler):
    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
        status = 200
        if self.headers.get("Authorization") != "Bearer local-fixture-only" or body.get("agreementId") != "fixture-agreement":
            status, result = 403, {"error": "fixture authorization failed"}
        elif self.path == "/grafana/consumer/manifest":
            result = {"manifestVersion": "1.0", "dashboardId": "weather", "title": "Shared weather observations",
                      "panels": [{"id": 1, "title": "Temperature", "type": "timeseries", "queries": [{"refId": "A", "panelId": "1"}]}]}
        elif self.path == "/grafana/consumer/query":
            end = int(datetime.fromisoformat(body["timeRange"]["to"].replace("Z", "+00:00")).timestamp() * 1000)
            result = {"protocolVersion": "1.0", "requestId": body["requestId"], "dataFrames": [{
                "schema": {"refId": "A", "name": "temperature", "fields": [
                    {"name": "Time", "type": "time", "typeInfo": {"frame": "time.Time"}},
                    {"name": "Temperature", "type": "number", "typeInfo": {"frame": "float64"}}]},
                "data": {"values": [[end - 60000 * i for i in range(59, -1, -1)], [20 + (i % 10) * .2 for i in range(60)]]}}]}
        else:
            status, result = 404, {}
        encoded = json.dumps(result).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)


ThreadingHTTPServer(("0.0.0.0", 8000), Fixture).serve_forever()
