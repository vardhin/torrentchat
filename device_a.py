import argparse
import asyncio
import hashlib
import base64
import socket
import struct
import time

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
        self.stop_grabber = False

        # Initialize peer discovery
        self.peer_discovery = set()  # Use this set to store discovered peers

        print(f"App initialized for {self.nik} on port {self.conf.port}")

    async def run(self):
        # Create the chat room before running tasks
        self.make_chat(self.conf.start_ping)
        
        # Create and run tasks
        tasks = [
            self.listener(),
            self.cli(),
        ]
        print("Starting tasks...")
        await asyncio.gather(*tasks)

    def make_chat(self, theme):
        room = ChatRoom(theme)
        self.rooms[room.theme] = room
        # Create tasks using asyncio.create_task within async context
        asyncio.create_task(self.spamer(room))
        print(f"Chat room '{theme}' created.")

    async def cli(self):
        while True:
            line = await asyncio.to_thread(input, "$ ")
            room = self.rooms.get(self.conf.start_ping)
            if room:
                message = self.new_message(room.theme, line)
                await room.postoffice.put(message)
                print(f"Message sent to room '{room.theme}': {line}")

    async def listener(self):
        addr = ('0.0.0.0', self.conf.port)
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind(addr)
        print(f"Listening for incoming messages on port {self.conf.port}")

        while True:
            data, addr = await asyncio.to_thread(sock.recvfrom, 4096)
            print(f"Received data from {addr}")
            await self.receive_msg(data, addr)

    async def receive_msg(self, buf, addr):
        msg = self.unpack_message(buf)
        room = self.rooms.get(msg['theme'])
        if room:
            await room.mailbox.put(msg)
            print(f"Message received in room '{msg['theme']}' from {addr}")
        else:
            print(f"Received message for unknown chat: {msg['theme']}")

    async def grab_peers(self):
        # Simple example: broadcast to a known set of peers
        while not self.stop_grabber:
            for peer in self.peer_discovery:
                # Placeholder for real peer discovery
                print(f"Grabbing peers for {peer}")
                pass
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
                    print(f"Spam message sent to peer {peer}: {msg['text']}")

    async def send_msg(self, msg, peer):
        addr = (peer, self.conf.dst_port)
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.sendto(self.pack_message(msg), addr)
        print(f"Message sent to {addr}: {msg['text']}")

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

    # Run the application using asyncio.run()
    asyncio.run(app.run())
