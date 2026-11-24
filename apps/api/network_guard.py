"""Proxy local de denegación: jamás resuelve destinos ni reenvía tráfico."""
import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from packages.network_policy import install


class DenyProxy(BaseHTTPRequestHandler):
    def log_message(self,*args):
        pass

    def deny(self):
        health=self.command=="GET" and self.path=="/health"
        data=json.dumps({"mode":"deny-egress"} if health else {"error":"offline_network_denied"}).encode()
        self.send_response(200 if health else 403)
        self.send_header("Content-Type","application/json")
        self.send_header("Content-Length",str(len(data)))
        self.send_header("Connection","close")
        self.end_headers()
        self.wfile.write(data)
        self.close_connection=True

    do_GET=do_POST=do_PUT=do_DELETE=do_PATCH=do_CONNECT=do_HEAD=do_OPTIONS=deny


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port",type=int,default=8767)
    args=parser.parse_args()
    if not 1<=args.port<=65535:
        parser.error("Puerto inválido")
    install()
    with ThreadingHTTPServer(("127.0.0.1",args.port),DenyProxy) as server:
        print("Local deny proxy · 127.0.0.1:"+str(args.port),flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__=="__main__":
    main()
