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


class PACoin:

    class P2PDiscoveryServicer(PACoin_pb2_grpc.P2PDiscoveryServicer):

        def __init__(self, pacoin):
            super().__init__()
            self.pacoin = pacoin

        def ping(self, request, context):
            ip = context.peer().split(':')[1]
#            print("receive ping: ", ip, request.port)
            self.pacoin.init_latency("%s:%d" % (ip, request.port))
            return PACoin_pb2.PingReply(ret=PACoin_pb2.SUCCESS)

        def pullPeers(self, request, context):
            ip = context.peer().split(':')[1]
#            print("receive pullPeers: ", ip, request.num)
            return PACoin_pb2.PullPeersReply(ret=PACoin_pb2.SUCCESS, hosts=self.pacoin.list_peers(request.num))

    def KeyboardInterruptHandler(self, signum, frame):
        self.to_exit = True

    def __init__(self, server: grpc.Server, bind: str, port: int, peers: list, db: sqlite3.Connection, timeout: float, peer_num: int):
        self.to_exit = False
        self.server = server
        self.peers = peers
        self.bind = bind
        self.port = port
        self.db = db
        self.db_mutex = threading.Lock()
        self.timeout = timeout
        self.peer_num = peer_num
        atexit.register(self.cleanup)

    def cleanup(self):
        self.db.commit()
        self.db.close()

    def update_latency(self, peer, latency):
        if peer == "%s:%d" % (self.bind, self.port):
            return
        self.db_mutex.acquire()
        cursor = self.db.cursor()
        cursor.execute(
            "UPDATE peers SET latency = ? WHERE host = ?", (latency, peer))
        if cursor.rowcount == 0:
            cursor.execute(
                "INSERT INTO peers (host, latency) VALUES (?, ?)", (peer, latency))
#        cursor.execute("SELECT * FROM peers WHERE host = ?", (peer, ))
#        print(cursor.fetchone())
        cursor.close()
        self.db_mutex.release()

    def init_latency(self, peer):
        if peer == "%s:%d" % (self.bind, self.port):
            return
        self.db_mutex.acquire()
        cursor = self.db.cursor()
        cursor.execute("SELECT * FROM peers WHERE host = ?", (peer, ))
        if not cursor.fetchone():
            cursor.execute(
                "INSERT INTO peers (host, latency) VALUES (?, ?)", (peer, self.timeout))
#        print(cursor.fetchone())
        cursor.close()
        self.db_mutex.release()

    def list_peers(self, num=65536):
        self.db_mutex.acquire()
        cursor = self.db.cursor()
        cursor.execute(
            "SELECT host FROM peers ORDER BY latency ASC LIMIT ?", (num, ))
#        print(cursor.fetchone())
        arr = [r[0] for r in cursor.fetchall()]
        cursor.close()
        self.db_mutex.release()
        return arr

    def shrink_peers(self, num, if_print=False):
        self.db_mutex.acquire()
        cursor = self.db.cursor()
        cursor.execute(
            "DELETE FROM peers WHERE host NOT IN (SELECT host FROM peers ORDER BY latency ASC LIMIT ?)", (num, ))
        if if_print:
            cursor.execute("SELECT * FROM peers ORDER BY latency ASC")
            print("current peers: ", cursor.fetchall())
        cursor.close()
        self.db_mutex.release()

    def serve(self):
        PACoin_pb2_grpc.add_P2PDiscoveryServicer_to_server(
            self.P2PDiscoveryServicer(self), self.server)
        self.server.add_insecure_port("%s:%d" % (self.bind, self.port))
        self.server.start()

    def ping(self, peer):
        try:
            start_time = time.time()
            with grpc.insecure_channel(peer) as channel:
                stub = PACoin_pb2_grpc.P2PDiscoveryStub(channel)
                response = stub.ping(
                    PACoin_pb2.PingRequest(port=self.port), timeout=self.timeout * 1e-3)
                latency = time.time() - start_time
#                print("ping ", peer, ", latency = %.2f ms" %
#                      (latency.real * 1e3))
                self.update_latency(peer, 1000 * latency)
        except Exception as e:
            print(e)

    def pullPeers(self, peer):
        try:
            with grpc.insecure_channel(peer) as channel:
                stub = PACoin_pb2_grpc.P2PDiscoveryStub(channel)
                response = stub.pullPeers(
                    PACoin_pb2.PullPeersRequest(num=self.peer_num), timeout=self.timeout * 1e-3)
#                print("pullPeers ", peer, ", hosts = ", response.hosts)
                for host in response.hosts:
                    self.init_latency(host)
        except Exception as e:
            print(e)

    def update_peers(self):
        self.shrink_peers(self.peer_num)
        for p in self.list_peers(self.peer_num):
            self.pullPeers(p)
        for p in self.list_peers(self.peer_num * (self.peer_num + 1)):
            self.ping(p)
        self.shrink_peers(self.peer_num, True)

    def loop(self, seconds, func, *args):
        func(*args)
        if not self.to_exit:
            timer = threading.Timer(seconds, self.loop, (seconds, func) + args)
            timer.start()

    def start(self):
        cursor = self.db.cursor()
        cursor.execute(
            "CREATE TABLE IF NOT EXISTS peers (host VARCHAR(128) PRIMARY KEY, latency REAL)")
        cursor.close()
        for peer in self.peers:
            self.update_latency(peer, 0.0)
        signal.signal(signal.SIGINT, self.KeyboardInterruptHandler)
        self.serve()
        self.loop(10, self.update_peers)
        while not self.to_exit:
            time.sleep(1)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Process some arguments')
    parser.add_argument('--port', type=int, default=23333,
                        help='Listening port')
    parser.add_argument('--bind', type=str,
                        default="[::]", help='Listening ip')
    parser.add_argument(
        '--peer', type=str, nargs='+', default=["127.0.0.1:23333"], help='Peers to connect')
    parser.add_argument('--db', type=str, default="PACoin.db",
                        help='Database file name')
    parser.add_argument('--timeout', type=float,
                        default=2000.0, help='Threshold for timeout')
    parser.add_argument('--peer_num', type=int, default=5,
                        help='Maximum numbers of peers')
    args = parser.parse_args()
    logging.basicConfig()

    pacoin = PACoin(
        server=grpc.server(concurrent.futures.ThreadPoolExecutor(max_workers=4)), bind=args.bind, port=args.port,
                    peers=args.peer, db=sqlite3.connect(args.db, check_same_thread=False), timeout=args.timeout, peer_num=args.peer_num)
    pacoin.start()
