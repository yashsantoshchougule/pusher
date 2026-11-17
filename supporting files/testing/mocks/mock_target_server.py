"""
Standalone Mock HTTP Target Server for Pusher Load Testing Verification
Binds to 0.0.0.0:8080 (accessible via localhost:8080 or LAN IP)

Provides endpoints to test Pusher's safety limits, circuit breaker, and rate-limiting:
  • GET /          - 200 OK fast response
  • GET /fast      - 200 OK immediate response
  • GET /slow      - 500ms delayed response (latency simulation)
  • GET /500       - 500 Internal Server Error (crash simulation)
  • GET /429       - 429 Too Many Requests (WAF rate limit simulation)
  • GET /cascade   - Cascading 5xx error after N requests
"""

import sys
import time
from http.server import HTTPServer, BaseHTTPRequestHandler

PORT = 8080
request_counter = 0

class MockTargetHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Concise logging
        sys.stdout.write(f"[{self.log_date_time_string()}] {format % args}\n")
        sys.stdout.flush()

    def do_GET(self):
        global request_counter
        request_counter += 1

        if self.path in ('/', '/fast'):
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(b'{"status":"ok","message":"Fast 200 OK"}\n')

        elif self.path == '/slow':
            time.sleep(0.5)
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(b'{"status":"ok","latency":"500ms"}\n')

        elif self.path == '/500':
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(b'{"error":"Internal Server Error","code":500}\n')

        elif self.path == '/429':
            self.send_response(429)
            self.send_header('Retry-After', '30')
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(b'{"error":"Too Many Requests","code":429}\n')

        elif self.path == '/cascade':
            # Returns 200 for the first 10 requests, then 503 Service Unavailable
            if request_counter % 20 < 10:
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(b'{"status":"ok","note":"Healthy phase"}\n')
            else:
                self.send_response(503)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(b'{"error":"Service Unavailable","note":"Cascading failure phase"}\n')

        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b'{"error":"Not Found"}\n')

def run(server_class=HTTPServer, handler_class=MockTargetHandler, port=PORT):
    server_address = ('0.0.0.0', port)
    httpd = server_class(server_address, handler_class)
    print(f"Mock target server running at http://0.0.0.0:{port} (Ctrl+C to stop)")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down mock target server.")
        httpd.server_close()

if __name__ == '__main__':
    run()
