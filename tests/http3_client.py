"""Require a real HTTP/3 response, with certificate verification and no fallback."""
import asyncio
import ssl
from aioquic.asyncio import QuicConnectionProtocol, connect
from aioquic.h3.connection import H3_ALPN, H3Connection
from aioquic.h3.events import DataReceived, HeadersReceived
from aioquic.quic.configuration import QuicConfiguration


class Client(QuicConnectionProtocol):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.http = H3Connection(self._quic)
        self.response = asyncio.get_running_loop().create_future()
        self.body = bytearray()
        self.status = None

    def quic_event_received(self, event):
        for http_event in self.http.handle_event(event):
            if isinstance(http_event, HeadersReceived):
                self.status = dict(http_event.headers).get(b":status")
            if isinstance(http_event, DataReceived):
                self.body.extend(http_event.data)
            if getattr(http_event, "stream_ended", False) and not self.response.done():
                self.response.set_result((self.status, bytes(self.body)))

    async def request(self):
        stream = self._quic.get_next_available_stream_id()
        self.http.send_headers(stream, [(b":method", b"GET"), (b":scheme", b"https"), (b":authority", b"localhost:8443"), (b":path", b"/")], end_stream=True)
        self.transmit()
        return await asyncio.wait_for(self.response, 15)


async def main():
    config = QuicConfiguration(is_client=True, alpn_protocols=H3_ALPN, server_name="localhost")
    config.verify_mode = ssl.CERT_REQUIRED
    config.load_verify_locations("/certs/ca-bundle.pem")
    async with connect("127.0.0.1", 8443, configuration=config, create_protocol=Client) as client:
        status, body = await client.request()
        assert status == b"200", status
        assert b"Nginx distroless is running" in body, body
        print("PASS: verified HTTP/3 response over QUIC (no HTTP/2 fallback)")


asyncio.run(main())
