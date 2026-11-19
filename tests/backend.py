"""Private-CA HTTPS backend plus TCP echo server for integration tests."""
import http.server
import socketserver
import ssl
import threading


class Http(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"verified-private-ca-upstream")


class Echo(socketserver.BaseRequestHandler):
    def handle(self):
        self.request.sendall(self.request.recv(4096))


context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
context.load_cert_chain("/certs/fullchain.pem", "/certs/privkey.pem")
server = http.server.ThreadingHTTPServer(("0.0.0.0", 9443), Http)
server.socket = context.wrap_socket(server.socket, server_side=True)
threading.Thread(target=server.serve_forever, daemon=True).start()
socketserver.ThreadingTCPServer.allow_reuse_address = True
socketserver.ThreadingTCPServer(("0.0.0.0", 9001), Echo).serve_forever()
