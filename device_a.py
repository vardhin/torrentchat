import argparse
import asyncio
import hashlib
import base64
import socket
import struct
import time

import libtorrent as lt

class Config:
    def __init__(self, port, dst_port, dht_port, start_ping):
        self.port = port
        self.dst_port = dst_port
        self.dht_port = dht_port
        self.start_ping = start_ping

class App:
    def __init__(self, nik, conf):
        self.nik = nik
        self.conf = conf
        self.rooms = {}
        self.msgid = 0

        self.dht = lt.session()
        self.dht.listen_on(self.conf.dht_port, self.conf.dht_port + 10)
        self.stop_grabber = False

        self.loop = asyncio.get_event_loop()

    async def run(self):
        self.loop.create_task(self.grab_peers())
        self.loop.create_task(self.listener())
        self.loop.create_task(self.cli())
        await asyncio.sleep(10000)  # Run for a long time

    def make_chat(self, theme):
        room = ChatRoom(theme)
        self.rooms[room.theme] = room
        self.loop.create_task(self.spamer(room))

    async def cli(self):
        while True:
            line = await self.loop.run_in_executor(None, input, "$ ")
            room = self.rooms.get(self.conf.start_ping)
            if room:
                message = self.new_message(room.theme, line)
                await room.postoffice.put(message)

    async def listener(self):
        addr = ('0.0.0.0', self.conf.port)
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind(addr)

        while True:
            data, addr = await self.loop.run_in_executor(None, sock.recvfrom, 4096)
            await self.receive_msg(data, addr)

    async def receive_msg(self, buf, addr):
        msg = self.unpack_message(buf)
        room = self.rooms.get(msg['theme'])
        if room:
            await room.mailbox.put(msg)
        else:
            print(f"Received message for unknown chat: {msg['theme']}")

    async def grab_peers(self):
        while not self.stop_grabber:
            for room in self.rooms.values():
                ihash = lt.sha1_hash(room.theme.encode())
                self.dht.dht_get_peers(ihash)
            await asyncio.sleep(10)

    def new_message(self, theme, text):
        self.msgid += 1
        return {
            'theme': theme,
            'id': self.msgid,
            'author': self.nik,
            'time': int(time.time()),
            'text': text
        }

    def pack_message(self, msg):
        data = base64.b64encode(msg['text'].encode()).decode()
        return struct.pack("!32sI32sI{}s".format(len(data)),
                           msg['theme'].encode(),
                           msg['id'],
                           msg['author'].encode(),
                           msg['time'],
                           data.encode())

    def unpack_message(self, buf):
        theme, msg_id, author, timestamp, data = struct.unpack("!32sI32sI{}s".format(len(buf) - 72), buf)
        return {
            'theme': theme.decode().strip('\x00'),
            'id': msg_id,
            'author': author.decode().strip('\x00'),
            'time': timestamp,
            'text': base64.b64decode(data).decode()
        }

    async def spamer(self, room):
        while True:
            await asyncio.sleep(10)
            for peer in room.peers:
                for msg in room.hist.values():
                    if time.time() - msg['time'] > 86400:
                        continue
                    await self.send_msg(msg, peer)

    async def send_msg(self, msg, peer):
        addr = (peer, self.conf.dst_port)
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.sendto(self.pack_message(msg), addr)

class ChatRoom:
    def __init__(self, theme):
        self.theme = hashlib.sha1(theme.encode()).hexdigest()
        self.hist = {}
        self.mailbox = asyncio.Queue()
        self.new_peers = asyncio.Queue()
        self.postoffice = asyncio.Queue()
        self.peers = []

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=3300)
    parser.add_argument('--dstport', type=int, default=3301)  # Port for device B
    parser.add_argument('--dhtport', type=int, default=6881)
    parser.add_argument('--nodes', type=str, default='')
    parser.add_argument('--nik', type=str, default='deviceA')
    parser.add_argument('--room', type=str, default='chatik')

    args = parser.parse_args()

    conf = Config(args.port, args.dstport, args.dhtport, args.nodes)
    app = App(args.nik, conf)
    app.make_chat(args.room)

    asyncio.run(app.run())
