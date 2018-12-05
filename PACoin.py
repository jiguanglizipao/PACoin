#!/usr/bin/env python3
import concurrent.futures
import time
import logging
import threading
import signal
import atexit
import argparse
import sqlite3

import grpc
import PACoin_pb2
import PACoin_pb2_grpc

class P2PDiscoveryServicer(PACoin_pb2_grpc.P2PDiscoveryServicer):
    def ping(self, request, context):
        ip = context.peer().split(':')[1]
        print("receive: ", ip, request.port)
        return PACoin_pb2.PingReply(ret=PACoin_pb2.SUCCESS)

class PACoin:
    def KeyboardInterruptHandler(self, signum, frame):
        self.to_exit = True

    def __init__(self, server:grpc.Server, bind:str, port:int, first_peer:str, db:sqlite3.Connection):
        self.to_exit = False
        self.server = server
        self.first_peer = first_peer
        self.bind = bind
        self.port = port
        self.db = db
        atexit.register(self.cleanup)

    def cleanup(self):
        self.db.commit()
        self.db.close()

    def serve(self):
        PACoin_pb2_grpc.add_P2PDiscoveryServicer_to_server(
            P2PDiscoveryServicer(), self.server)
        self.server.add_insecure_port("%s:%d" % (self.bind, self.port))
        self.server.start()

    def ping(self, peer):
        try:
            start_time = time.time()
            with grpc.insecure_channel(peer) as channel:
                stub = PACoin_pb2_grpc.P2PDiscoveryStub(channel)
                response = stub.ping(
                    PACoin_pb2.PingRequest(port=self.port), timeout=1)
                latency = time.time() - start_time
                print("ping ", peer, ", latency = %.2f ms" %
                      (latency.real * 1e3))
        except Exception as e:
            print(e)

    def loop(self, seconds, func, *args):
        func(*args)
        if not self.to_exit:
            timer = threading.Timer(seconds, self.loop, (seconds, func, *args))
            timer.start()

    def start(self):
        signal.signal(signal.SIGINT, self.KeyboardInterruptHandler)
        self.serve()
        self.loop(2, self.ping, self.first_peer)
        while not self.to_exit:
            time.sleep(1)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Process some arguments')
    parser.add_argument('--port', type=int, default=23333, help='Listening port')
    parser.add_argument('--bind', type=str, default="[::]", help='Listening ip')
    parser.add_argument(
        '--peer', type=str, default="localhost:23333", help='First peer to connect')
    parser.add_argument('--db', type=str, default="PACoin.db", help='Database file name')
    args = parser.parse_args()
    logging.basicConfig()

    pacoin = PACoin(server=grpc.server(concurrent.futures.ThreadPoolExecutor(max_workers=4)), bind=args.bind, port=args.port, first_peer=args.peer, db=sqlite3.connect(args.db))
    pacoin.start()
