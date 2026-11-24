"""Pruebas locales sin DNS externo ni conexiones de Internet."""
import http.client
import socket
import threading
import unittest
from http.server import ThreadingHTTPServer

from apps.api.network_guard import DenyProxy
from packages import network_policy as policy


class OfflinePolicy(unittest.TestCase):
    def test_python_blocks_external_dns_tcp_and_udp(self):
        policy.install()
        self.addCleanup(policy.restore)
        with self.assertRaises(PermissionError):
            socket.getaddrinfo("external-audit.invalid",443)
        with self.assertRaises(PermissionError),socket.socket() as stream:
            stream.connect(("198.51.100.1",443))
        with self.assertRaises(PermissionError),socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as stream:
            stream.sendto(b"SIMULATED offline probe",("198.51.100.1",53))
        self.assertTrue(policy.local_host("127.0.0.1"))
        self.assertTrue(policy.local_host("::1"))
        self.assertTrue(policy.local_host("::ffff:127.0.0.1"))
        self.assertFalse(policy.local_host("192.168.1.1"))

    def test_deny_proxy_serves_health_and_denies_http_and_connect(self):
        policy.install()
        self.addCleanup(policy.restore)
        with ThreadingHTTPServer(("127.0.0.1",0),DenyProxy) as server:
            thread=threading.Thread(target=server.serve_forever,args=(0.02,))
            thread.start()
            try:
                for method,target,status in [("GET","/health",200),("GET","https://external-audit.invalid/",403),
                                             ("CONNECT","external-audit.invalid:443",403)]:
                    c=http.client.HTTPConnection("127.0.0.1",server.server_port,timeout=3)
                    try:
                        c.request(method,target)
                        response=c.getresponse()
                        self.assertEqual(response.status,status)
                        response.read()
                    finally:
                        c.close()
            finally:
                server.shutdown()
                thread.join()
