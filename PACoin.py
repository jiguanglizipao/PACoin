#!/usr/bin/env python3
import concurrent.futures
import time
import logging
import threading
import signal
import atexit
import argparse
import sqlite3
import random

import grpc
import PACoin_pb2
import PACoin_pb2_grpc
import PACoin_block
import PACrypto
import pickle
import Sqlite_utils as mysqlite
import PACoin_utils as utils


class PACoin:

    class P2PDiscoveryServicer(PACoin_pb2_grpc.P2PDiscoveryServicer):

        def __init__(self, pacoin):
            super().__init__()
            self.pacoin = pacoin

        def ping(self, request, context):
            ip = context.peer().split(':')[1]
#            print("receive ping: ", ip, request.port)
            mysqlite.init_latency(self.pacoin.db, self.pacoin.db_mutex, "%s:%d" % (ip, request.port),
                                  self.pacoin.timeout, self.pacoin.bind, self.pacoin.port)
            return PACoin_pb2.PingReply(ret=PACoin_pb2.SUCCESS)

        def pullPeers(self, request, context):
            ip = context.peer().split(':')[1]
#            print("receive pullPeers: ", ip, request.num)
            return PACoin_pb2.PullPeersReply(ret=PACoin_pb2.SUCCESS,
                                             hosts=mysqlite.list_peers(self.pacoin.db, self.pacoin.db_mutex, request.num))

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
        self.pkey = PACrypto.generate_private_key()
        self.pubkey = PACrypto.generate_public_key(self.pkey)
        self.address = PACrypto.generate_address(self.pubkey)
        atexit.register(self.cleanup)

        # ******* mining logic *******
        self.version = 0
        self.max_transaction_num = 10
        self.threshold = 12

    def cleanup(self):
        self.db.commit()
        self.db.close()

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
                mysqlite.update_latency(self.db, self.db_mutex, peer, 1000 * latency, self.bind, self.port)
        except Exception as e:
            mysqlite.delete_peer(self.db, self.db_mutex, peer)
            print(e)

    def pullPeers(self, peer):
        try:
            with grpc.insecure_channel(peer) as channel:
                stub = PACoin_pb2_grpc.P2PDiscoveryStub(channel)
                response = stub.pullPeers(
                    PACoin_pb2.PullPeersRequest(num=self.peer_num), timeout=self.timeout * 1e-3)
#                print("pullPeers ", peer, ", hosts = ", response.hosts)
                for host in response.hosts:
                    mysqlite.init_latency(self.db, self.db_mutex, host, self.timeout, self.bind, self.port)
        except Exception as e:
            mysqlite.delete_peer(self.db, self.db_mutex, peer)
            print(e)

    def update_peers(self):
        peers = mysqlite.list_peers(self.db, self.db_mutex, self.peer_num)
        for p in peers:
            self.ping(p)
            self.pullPeers(p)

        if len(mysqlite.list_peers(self.db, self.db_mutex, self.peer_num)) == 0:
            for peer in self.peers:
                mysqlite.update_latency(self.db, self.db_mutex, peer, 0.0, self.bind, self.port)

        print("Peers list size: ", len(mysqlite.list_peers(self.db, self.db_mutex)))

# *********************** mining logic *************************

    def update_block_header(self):
        note = "should be atomic......"
        transaction_list = mysqlite.get_unverified_transactions(
            self.db, self.db_mutex)
        transaction_list.sort(key=lambda t: -(t[1].transaction.tip))
        transaction_list = transaction_list[:self.max_transaction_num]
        transaction_list.sort(key=lambda t: t[1].transaction.timestamp)

        # TODO: verify those transactions
        # TODO: fetch parent hash from sqlite
        index, last_block_hash = mysqlite.get_last_block_idx_hash(
            self.db, self.db_mutex)
        self.block_on_trying = PACoin_block.Block(
            self.version, last_block_hash, transaction_list, self.threshold, int(time.time()), index + 1, self.address)

    def mine(self):
        retry = 2**self.threshold
        self.update_block_header()
        # TODO: need to be modified
        for i in range(0, retry):
            n = int(random.random() * pow(2, 64))
            self.block_on_trying.set_nonce(n)
            h = utils.PACoin_hash(self.block_on_trying.serialized())
            if utils.validate_hash(h, self.threshold):
                mysqlite.write_block(
                    self.db, self.db_mutex, self.block_on_trying.index, self.block_on_trying.serialized())
                print("{\n    " + "\n    ".join("{}: {}".format(k, v)
                      for k, v in self.block_on_trying.__dict__.items()) + "\n}")
                print("success", h)
                # success!
                return True
        return False

    def test_db(self):
        # for i in range(6):
        #     t = utils.generate_random_transaction()
        #     mysqlite.write_transaction(self.db, self.db_mutex, 1, t)
        # for i in range(4):
        #     t = utils.generate_random_transaction()
        #     mysqlite.write_transaction(self.db, self.db_mutex, 0, t)
        #
        # transaction_list = mysqlite.get_unverified_transactions(self.db, self.db_mutex)
        # transaction_list.sort(key=lambda t: -(t[1].transaction.tip))
        # transaction_list = transaction_list[:self.max_transaction_num]
        # transaction_list.sort(key=lambda t: t[1].transaction.timestamp)
        # flag_list = []
        # id_list = []
        # for t in transaction_list:
        #     flag_list.append(1)
        #     id_list.append(t[0])
        # mysqlite.update_transaction(self.db, self.db_mutex, id_list,
        # flag_list)
        pass


# *********************** end of mining logic *************************

# ********************* block transfer logic *******************

    class BlockTransfer(PACoin_pb2_grpc.BlockTransferServicer):
        def __init__(self, pacoin: PACoin):
            self.pacoin = pacoin

        def sendBlocks(self, request, context):
            my_curr = mysqlite.get_total_block_num(self.pacoin.db, self.pacoin.db_mutex)
            blk = PACoin_block.Block.unserialize(request.block.data)
            if blk is None:
                # FIXME: DDOS
                print("blk is None.")
                return PACoin_pb2.SendBlocksReply(ret=PACoin_pb2.ERROR)
            if blk.index == my_curr:
                # TODO: Update (interrupt minning)
                # Bcast to peers
                pass
            else:
                print("blk not useful: %d, my_curr: %d" % (blk.index, my_curr))
                
            return PACoin_pb2.SendBlocksReply(ret=PACoin_pb2.ERROR)

        def pullBlocks(self, request, context):
            blks = mysqlite.get_block_range(self.pacoin.db, self.pacoin.db_mutex, request.base, request.num)
            blks_data = [PACoin_pb2.Block(data=blk) for blk in blks]

            return PACoin_pb2.PullBlocksReply(ret=PACoin_pb2.SUCCESS, blocks=blks_data)

        def syncStatus(self, request, context):
            my_curr = mysqlite.get_total_block_num(self.pacoin.db, self.pacoin.db_mutex)
            return PACoin_pb2.SyncStatusReply(
                ret=PACoin_pb2.SUCCESS,
                curr=my_curr
            )

    def update_blocks_peer(self, peer):
        my_curr = mysqlite.get_total_block_num(self.db, self.db_mutex)
        try:
            with grpc.insecure_channel(peer) as channel:
                stub = PACoin_pb2_grpc.BlockTransferStub(channel)
                response = stub.syncStatus(
                    PACoin_pb2.SyncStatusRequest(curr=my_curr),
                    timeout=self.timeout * 1e-3)

                num = response.curr - my_curr
                if num > 0:
                    response = stub.pullBlocks(
                        PACoin_pb2.PullBlocksRequest(base=my_curr, num=num),
                        timeout=self.timeout * 1e-3
                    )
                    if response.ret != PACoin_pb2.SUCCESS:
                        print("Warning: pull blocks failed but expect not.")
                    else:
                        for blk in response.blocks:
                            if not mysqlite.write_block(self.db, self.db_mutex, my_curr, blk.data):
                                print("Warning: DB is modified unexpectedly.")
                            my_curr += 1

        except Exception as e:
            mysqlite.delete_peer(self.db, self.db_mutex, peer)
            print(e)

    def update_blocks(self):
        peers = mysqlite.list_peers(self.db, self.db_mutex, self.peer_num)
        for peer in peers:
            self.update_blocks_peer(peer)

    def loop(self, seconds, func, *args):
        func(*args)
        if not self.to_exit:
            timer = threading.Timer(seconds, self.loop, (seconds, func) + args)
            timer.start()

    def start(self):
        cursor = self.db.cursor()
        cursor.execute(
            "CREATE TABLE IF NOT EXISTS peers (host VARCHAR(128) PRIMARY KEY, latency REAL)")
        cursor.execute(
            "CREATE TABLE IF NOT EXISTS transactions (id INTEGER PRIMARY KEY AUTOINCREMENT, verified INTEGER, data BLOB)")
        cursor.execute(
            "CREATE TABLE IF NOT EXISTS blocks (block_index INTEGER, block BLOB)")
        self.db.commit()
        cursor.close()
        # self.test_db()
        for peer in self.peers:
            mysqlite.update_latency(self.db, self.db_mutex, peer, 0.0, self.bind, self.port)
        signal.signal(signal.SIGINT, self.KeyboardInterruptHandler)
        self.serve()
        self.loop(10, self.update_peers)
        self.loop(1, self.mine)
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
                        help='Maximum numbers of peers to send data')
    args = parser.parse_args()
    logging.basicConfig()

    pacoin = PACoin(
        server=grpc.server(concurrent.futures.ThreadPoolExecutor(max_workers=4)), bind=args.bind, port=args.port,
                    peers=args.peer, db=sqlite3.connect(args.db, check_same_thread=False), timeout=args.timeout, peer_num=args.peer_num)
    pacoin.start()
