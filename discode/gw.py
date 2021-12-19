import websockets
import asyncio
import json
import sys
import time
import zlib

from .intents import Intents
from .guild import Guild
from .member import Member
from . import utils
from .errors import GatewayError, PrivilegedIntentsRequired

class OP:
    DISPATCH = 0
    HEARTBEAT = 1
    IDENTIFY = 2
    PRESENCE = 3
    VOICE_STATE = 4
    VOICE_PING = 5
    RESUME = 6
    RECONNECT = 7
    REQUEST_MEMBERS = 8
    INVALID_SESSION = 9
    HELLO = 10
    HEARTBEAT_ACK = 11
    GUILD_SYNC = 12

class WS:
    def __init__(self, data):
        self.data = data
        self.loop = data.get("loop")
        self.http = data.get("http")
        self.session = self.http.session
        self.token = data.get("token")
        self.intents: Intents = data.get("intents") or Intents.default()
        self.message_cache = self.http.client.message_cache
        self.guilds = self.http.client.guilds
        self._ready = asyncio.Event(loop=self.loop)
        self._last_send = 0
        self._last_ack = 0
        self._event_listeners = []
        self.inflator = zlib.decompressobj()
        self.buffer = bytearray()
        self.ZLIB_SUFFIX = b'\x00\x00\xff\xff'

    def get_latency(self):
        return self._last_ack - self._last_send

    @property
    def is_closed(self) -> bool:
        return self.ws.closed
    
    @property
    def is_ready(self):
        return self._ready.is_set()

    async def dispatch(self, *args, **kwargs):
        _dispatch = self.data.get("dispatch")
        self.loop.create_task(_dispatch(*args, **kwargs))

    async def _get_gateway(self):
        _data = await self.http.request("GET", "/gateway")
        return _data.get("url") or "wss://gateway.discord.gg/?v=9&encoding=json&compress=zlib-stream"

    def wait_for(self, event):
        future = self.loop.create_future()
        listener = {
            "event": event,
            "future": future
        }
        self._event_listeners.append(listener)
        return future

    async def reconnect(self):
        try:
            await self.ws.close(code = 4002)
        except:
            pass
        _gateway_url = await self._get_gateway()
        self.ws = await websockets.connect(_gateway_url)
        await self.send_json(
            {
                "op": OP.RECONNECT,
                "d": {
                    "token": self.token,
                    "session_id": self.session_id,
                    "seq": self.seq,
                }
            }
        )

    async def get_ws(self):
        _gateway_url = await self._get_gateway()
        ws = await websockets.connect(_gateway_url)
        return ws

    async def handle(self):
        self.ws = await self.get_ws()
        self.seq = None
        await self.listen()

    async def wait_until_ready(self) -> None:
        await self._ready.wait()

    async def identify(self):
        data = {
            "op": OP.IDENTIFY,
            "d": {
                "token": self.token,
                "intents": self.intents.value,
                "properties": {
                    "$os": sys.platform,
                    "$browser": "discode",
                    "$device": "discode",
                }
            }
        }

        await self.send_json(data)

    async def _send(self, data):
        await self.ws.send(data)

    async def send(self, data):
        self.loop.create_task(self._send(str(data)))

    async def send_json(self, data):
        data = json.dumps(data)
        await self.send(data)

    async def receive(self):
        data = await self.ws.recv()
        if not data:
            return

        if isinstance(data, bytes):
            self.buffer.extend(data)

            if len(data) < 4 or data[-4:] != self.ZLIB_SUFFIX:
                self.buffer = bytearray()
                return

            data = self.inflator.decompress(self.buffer)
            data = data.decode("utf-8")
            self.buffer = bytearray()

        if isinstance(data, int):
            if data == 4014:
                raise PrivilegedIntentsRequired()

            else:
                fmt = (
                    "Disconnected with code {code} from the gateway!"
                ).format(code = data)
                raise GatewayError(fmt)

        try:
            data = json.loads(data)
        except json.decoder.JSONDecodeError:
            return
        return data

    async def listen(self):
        while not self.is_closed:
            data = await self.receive()
            if data:
                seq = data.get("s")
                event = data.get('t')
                op = data.get('op')

                if seq is not None:
                    self.seq = seq

                if op == OP.HELLO:
                    interval = data["d"]["heartbeat_interval"] / 1000.0
                    self.loop.create_task(self.heartbeat(interval))
                    await self.identify()

                elif op == OP.INVALID_SESSION:
                    raise Exception("Invalid Token")

                elif op == OP.HEARTBEAT:
                    await self.send_json(self.hb_payload)

                elif op == OP.HEARTBEAT_ACK:
                    self._last_ack = time.perf_counter()

                elif op == OP.DISPATCH:
                    await utils._check(self, data)
                    if event == "READY":
                        self.session_id = data["d"].get("session_id")
                        self._ready.set()
                        await self.dispatch("ready")

                    if event == "GUILD_CREATE":
                        gdata = data.get("d")
                        if self.http.client.chunk_guilds_at_startup:
                            await self.chunk_guild(int(gdata.get("id")))

                            gdata["http"] = self.http
                            guild = Guild(**gdata)
                            self.guilds.append(guild)

                    elif event == "GUILD_MEMBERS_CHUNK":
                        guild = self.http.client.get_guild(int(data["d"].get("guild_id")))
                        for member in data.get("d").get("members"):
                            member["http"] = self.http
                            mem = Member(**member)
                            try:
                                guild._members.append(mem)
                            except:
                                guild._members = [mem]

    @property
    def hb_payload(self):
        return {"op": OP.HEARTBEAT, "d": self.seq}

    async def heartbeat(self, interval: float):
        while True:
            if self._last_ack > (time.perf_counter() + 5):
                await self.reconnect()

            await self.send_json(self.hb_payload)
            self._last_send = time.perf_counter()
            await asyncio.sleep(interval)

    async def chunk_guild(self, _id: int, *, query: str = "", limit: int = 0, presences: bool = False, nonce = None):
        payload = {
            "op": OP.REQUEST_MEMBERS,
            "d": {
                "guild_id": str(_id),
                "query": query,
                "limit": limit,
            },
        }
        if nonce:
            payload["d"]["nonce"] = nonce
        if presences:
            payload["presenses"] = presences
        return await self.http.ws.send_json(payload)
