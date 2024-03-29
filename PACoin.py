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
import base64

import grpc
import PACoin_pb2
import PACoin_pb2_grpc
import PACoin_block
import PACoin_txn
import PACrypto as crypto
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
        self.pkey = crypto.generate_private_key()
        self.pubkey = crypto.generate_public_key(self.pkey)
        self.address = crypto.generate_address(self.pubkey)
        atexit.register(self.cleanup)

        # ******* mining logic *******
        self.version = 0
        self.max_transaction_num = 10
        self.threshold = 14
        self.mining_reward = 100

        # ******* test transaction logic *******
        self.collect_pkey = crypto.generate_private_key()
        self.collect_pubkey = crypto.generate_public_key(self.collect_pkey)
        self.collect_address = crypto.generate_address(self.collect_pubkey)
        self.mining_success_num = 0

        # ****** block transfer logic *****
        self.mutable_block_mutex = threading.Lock()
        self.to_send_blocks = []
        self.to_send_blocks_mutex = threading.Lock()

    def cleanup(self):
        self.db.commit()
        self.db.close()

    def serve(self):
        PACoin_pb2_grpc.add_P2PDiscoveryServicer_to_server(
            self.P2PDiscoveryServicer(self), self.server)
        PACoin_pb2_grpc.add_BlockTransferServicer_to_server(
            self.BlockTransfer(self), self.server)
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
                mysqlite.update_latency(
                    self.db, self.db_mutex, peer, 1000 * latency, self.bind, self.port)
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
                    mysqlite.init_latency(
                        self.db, self.db_mutex, host, self.timeout, self.bind, self.port)
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
                mysqlite.update_latency(
                    self.db, self.db_mutex, peer, 0.0, self.bind, self.port)

        print("Peers list size: ", len(
            mysqlite.list_peers(self.db, self.db_mutex)))

# *********************** mining logic *************************

    def update_block_header(self):
        unverified_transaction_list = mysqlite.get_unverified_transactions(
            self.db, self.db_mutex)
        unverified_transaction_list.sort(key=lambda t: -(t.tips))
        unverified_transaction_list = unverified_transaction_list[:self.max_transaction_num]
        # transaction_list.sort(key=lambda t: t[1].transaction.timestamp)
        transaction_list = []
        for txn in unverified_transaction_list:
            valid = utils.validate_transaction(self.db, self.db_mutex, txn)
            if valid:
                transaction_list.append(txn)
            else:
                print("unvalid!  " + utils.PACoin_hash(txn))
        index, last_block_hash = mysqlite.get_last_block_idx_hash(
            self.db, self.db_mutex)
        self.block_on_trying = PACoin_block.Block(
            self.version, last_block_hash, transaction_list, self.threshold, int(time.time()), index + 1, self.address, self.mining_reward)

    def mine(self):
        with self.mutable_block_mutex:
            retry = 2**(self.threshold // 2)
            self.update_block_header()
            # TODO: need to be modified
            for i in range(0, retry):
                n = int(random.random() * pow(2, 64))
                self.block_on_trying.set_nonce(n)
                blk_bytes = self.block_on_trying.serialized()
                h = utils.PACoin_hash(blk_bytes)
                if utils.validate_hash(h, self.threshold):
                    self.block_on_trying.set_timestamp(int(time.time()))
                    mysqlite.write_block(
                        self.db, self.db_mutex, self.block_on_trying.index, blk_bytes)
                    print("{\n    " + "\n    ".join("{}: {}".format(k, v)
                                                    for k, v in self.block_on_trying.__dict__.items()) + "\n}")
                    print("success", h)
                    self.mining_success_num += 1
                    # success!
                    self.send_block(blk_bytes)
                    mysqlite.update_verified_transaction(self.db, self.db_mutex, self.block_on_trying.transaction_list,
                                                         [1]*len(self.block_on_trying.transaction_list))

                    # transfer reward to collect account
                    pre_t = self.block_on_trying.transaction_list[0]
                    pre_t_hash = utils.PACoin_hash(pre_t)
                    sign = pre_t.sign(0, self.pkey)
                    txin =  PACoin_txn.Txin(pre_t_hash, 0, self.pubkey, sign)
                    tips = 1
                    assert self.mining_reward > tips
                    txout_tips = PACoin_txn.Txout(tips, utils.generate_zero(88))
                    txout = PACoin_txn.Txout(self.mining_reward-tips, self.collect_address)
                    txn = PACoin_txn.Transaction([txin], [txout_tips, txout], int(time.time()), tips)
                    mysqlite.write_transaction(self.db, self.db_mutex, 0, txn)

                    self.pkey = crypto.generate_private_key()
                    self.pubkey = crypto.generate_public_key(self.pkey)
                    self.address = crypto.generate_address(self.pubkey)

                    return True
            return False

    def PoR_mine(self):
        with self.mutable_block_mutex:
            retry = 10
            self.update_block_header()
            blk_bytes = self.block_on_trying.serialized()
            porthreshold = 1.0 / (2 ** self.threshold)
            for i in range(0, retry):
                time.sleep(1)
                r = random.random()
                if r < porthreshold:
                    self.block_on_trying.set_timestamp(int(time.time()))
                    mysqlite.write_block(
                        self.db, self.db_mutex, self.block_on_trying.index, blk_bytes)
                    print("{\n    " + "\n    ".join("{}: {}".format(k, v)
                                                    for k, v in self.block_on_trying.__dict__.items()) + "\n}")
                    print("success")
                    self.mining_success_num += 1
                    # success!
                    self.send_block(blk_bytes)
                    mysqlite.update_verified_transaction(self.db, self.db_mutex, self.block_on_trying.transaction_list,
                                                         [1]*len(self.block_on_trying.transaction_list))

                    # transfer reward to collect account
                    pre_t = self.block_on_trying.transaction_list[0]
                    pre_t_hash = utils.PACoin_hash(pre_t)
                    sign = pre_t.sign(0, self.pkey)
                    txin =  PACoin_txn.Txin(pre_t_hash, 0, self.pubkey, sign)
                    tips = 1
                    assert self.mining_reward > tips
                    txout_tips = PACoin_txn.Txout(tips, utils.generate_zero(88))
                    txout = PACoin_txn.Txout(self.mining_reward-tips, self.collect_address)
                    txn = PACoin_txn.Transaction([txin], [txout_tips, txout], int(time.time()), tips)
                    mysqlite.write_transaction(self.db, self.db_mutex, 0, txn)

                    self.pkey = crypto.generate_private_key()
                    self.pubkey = crypto.generate_public_key(self.pkey)
                    self.address = crypto.generate_address(self.pubkey)

                    return True
            return False


# *********************** end of mining logic *************************

# ********************* block transfer logic *******************


    class BlockTransfer(PACoin_pb2_grpc.BlockTransferServicer):
        def __init__(self, pacoin):
            self.pacoin = pacoin

        def sendBlocks(self, request, context):
            with self.pacoin.mutable_block_mutex:
                last_idx, last_hash = mysqlite.get_last_block_idx_hash(self.pacoin.db, self.pacoin.db_mutex)
                my_curr = last_idx + 1
                b_bytes = utils.data2Bytes(request.block.data)
                blk = PACoin_block.Block.unserialize(b_bytes)
                if blk is None:
                    # FIXME: DDOS
                    print("blk is None.")
                    return PACoin_pb2.SendBlocksReply(ret=PACoin_pb2.ERROR)

                if blk.index == my_curr and last_hash == blk.parent_hash:
                    # TODO: Verify block
                    mysqlite.write_block(
                        self.pacoin.db, self.pacoin.db_mutex, my_curr, b_bytes)
                    print("Recv blk %d" % my_curr)
                    with self.pacoin.to_send_blocks_mutex:
                        self.pacoin.to_send_blocks.append(b_bytes)
                else:
                    print("blk not useful: %d, my_curr: %d" %
                          (blk.index, my_curr))

            return PACoin_pb2.SendBlocksReply(ret=PACoin_pb2.SUCCESS)

        def pullBlocks(self, request, context):
            with self.pacoin.mutable_block_mutex:
                blk = mysqlite.get_block(
                    self.pacoin.db, self.pacoin.db_mutex, request.idx)
                if blk is None:
                    return PACoin_pb2.PullBlocksReply(ret=PACoin_pb2.ERROR)
                blk_data = PACoin_pb2.Block(data=utils.bytes2Data(blk))

                return PACoin_pb2.PullBlocksReply(ret=PACoin_pb2.SUCCESS, block=blk_data)

        def syncStatus(self, request, context):
            with self.pacoin.mutable_block_mutex:
                my_curr = mysqlite.get_total_block_num(self.pacoin.db, self.pacoin.db_mutex)
                return PACoin_pb2.SyncStatusReply(
                    ret=PACoin_pb2.SUCCESS,
                    curr=my_curr
                )

    def send_block(self, blk_bytes):
        print("send_block")
        for peer in mysqlite.list_peers(self.db, self.db_mutex, self.peer_num):
            try:
                with grpc.insecure_channel(peer) as channel:
                    stub = PACoin_pb2_grpc.BlockTransferStub(channel)
                    blk_data = PACoin_pb2.Block(data=utils.bytes2Data(blk_bytes))
                    stub.sendBlocks(
                        PACoin_pb2.SendBlocksRequest(block=blk_data),
                        timeout=self.timeout * 1e-3
                    )
            except Exception as e:
                print(e)
        

    def valblks(self, blks):
        parent_hash = None
        for blk in blks:
            b = PACoin_block.Block.unserialize(blk)
            if parent_hash is not None:
                if utils.PACoin_hash(blk) != parent_hash:
                    return False
            parent_hash = b.parent_hash
        return True

    def rollback(self, stub):
        # mysqlite.clear_block_table(self.db, self.db_mutex)
        # return False
        print("rollback")
        cur_idx = mysqlite.get_total_block_num(self.db, self.db_mutex) - 1
        fork_idx = cur_idx
        last_blk_bytes = mysqlite.get_block(self.db, self.db_mutex, cur_idx)
        last_blk = PACoin_block.Block.unserialize(last_blk_bytes)
        p_hash = last_blk.parent_hash

        blk_list = []
        try:
            while cur_idx != 0:
                response = stub.pullBlocks(
                    PACoin_pb2.PullBlocksRequest(idx=cur_idx)
                )
                if response.ret != PACoin_pb2.SUCCESS:
                    print("Peer not honest.")
                    return

                b_bytes = utils.data2Bytes(response.block.data)
                b = PACoin_block.Block.unserialize(b_bytes)

                # TODO: Verify block
                if b.index != cur_idx:
                    print("Peer not honest.")
                    return

                blk_list.append(b_bytes)

                if b.parent_hash == p_hash:
                    if not self.valblks(blk_list):
                        print("Peer not val.")
                        return False
                    print("fork,{},{},{}".format(fork_idx, p_hash, utils.PACoin_hash(b_bytes)))
                    for blk in blk_list:
                        b = PACoin_block.Block.unserialize(blk)
                        mysqlite.erase_block(self.db, self.db_mutex, b.index)
                        if not mysqlite.write_block(self.db, self.db_mutex, b.index, blk):
                            print("Cannot write")
                    return True
                
                cur_idx -= 1
                last_blk_bytes = mysqlite.get_block(self.db, self.db_mutex, cur_idx)
                last_blk = PACoin_block.Block.unserialize(last_blk_bytes)
                p_hash = last_blk.parent_hash

            return False
        except Exception as e:
            print(e)
            return False

    def update_blocks_peer(self, peer, num):
        print("update_blocks_peer, %s, %d" % (peer, num))
        try:
            with grpc.insecure_channel(peer) as channel:
                toRollback = True
                stub = PACoin_pb2_grpc.BlockTransferStub(channel)
                while num != 0:
                    my_curr = mysqlite.get_total_block_num(self.db, self.db_mutex)
                    response = stub.pullBlocks(
                        PACoin_pb2.PullBlocksRequest(idx=my_curr),
                        timeout=self.timeout * 1e-3
                    )

                    if response.ret != PACoin_pb2.SUCCESS:
                        print("Warning: pull blocks failed but expect not.")
                        return False

                    # Verify DB
                    idx, p_hash = mysqlite.get_last_block_idx_hash(
                        self.db, self.db_mutex)
                    if (idx + 1) != my_curr:
                        print("Warning: DB is modified unexpectedly.")
                        return False

                    # Verify
                    b_bytes = utils.data2Bytes(response.block.data)
                    b = PACoin_block.Block.unserialize(b_bytes)
                    # TODO: Verify block
                    if b.parent_hash != p_hash or b.index != my_curr:
                        print(b.parent_hash, p_hash)
                        print(b.index, my_curr)
                        if toRollback:
                            if self.rollback(stub):
                                print("rollback success!")
                                mysqlite.write_block(self.db, self.db_mutex, my_curr, b_bytes)
                                return True
                        else:
                            print("Warning: Peer is not consistent.")
                        return False
                    toRollback = False
                    p_hash = utils.PACoin_hash(b_bytes)

                    # Add in
                    if not mysqlite.write_block(self.db, self.db_mutex, my_curr, b_bytes):
                        print("Warning: DB is modified unexpectedly.")
                        return False

                    num -= 1
                    my_curr += 1
                    print("Update a block from %s, Remaining %d." %(peer, num))

        except Exception as e:
            mysqlite.delete_peer(self.db, self.db_mutex, peer)
            print(e)
            return False

    def update_blocks(self):
        to_exit = False
        with self.mutable_block_mutex:
            while not to_exit:
                my_curr = mysqlite.get_total_block_num(self.db, self.db_mutex)
                peers = mysqlite.list_peers(
                    self.db, self.db_mutex, self.peer_num)
                candidates = []
                for peer in peers:
                    try:
                        with grpc.insecure_channel(peer) as channel:
                            stub = PACoin_pb2_grpc.BlockTransferStub(channel)
                            response = stub.syncStatus(
                                PACoin_pb2.SyncStatusRequest(curr=my_curr),
                                timeout=self.timeout * 1e-3)

                            if response.ret == PACoin_pb2.SUCCESS:
                                num = response.curr - my_curr
                                if num > 0:
                                    candidates.append((peer, num))
                    except Exception as e:
                        mysqlite.delete_peer(self.db, self.db_mutex, peer)
                        print(e)

                num_max = 0
                for can in candidates:
                    if num_max < can[1]:
                        num_max = can[1]

                if num_max == 0:
                    to_exit = True
                    break

                cands = [can for can in candidates if can[1] == num_max]
                lucky_peer = random.choice(cands)
                to_exit = self.update_blocks_peer(*lucky_peer)

    def send_block_thread(self):
        with self.to_send_blocks_mutex:
            if len(self.to_send_blocks) == 0:
                return
            print("Bcast, #Blk %d" % len(self.to_send_blocks))
            blk = self.to_send_blocks.pop(0)

        peers = mysqlite.list_peers(self.db, self.db_mutex, self.peer_num)
        for peer in peers:
            try:
                with grpc.insecure_channel(peer) as channel:
                    stub = PACoin_pb2_grpc.BlockTransferStub(channel)
                    stub.sendBlocks(
                        PACoin_pb2.SendBlocksRequest(block=PACoin_pb2.Block(data=utils.bytes2Data(blk)))
                    )
            except Exception as e:
                mysqlite.delete_peer(self.db, self.db_mutex, peer)
                print(e)

# ************************* End of block transfer logic ************

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
            "CREATE TABLE IF NOT EXISTS transactions (hash VARCHAR(128) PRIMARY KEY , verified INTEGER, data BLOB)")
        cursor.execute(
            "CREATE TABLE IF NOT EXISTS blocks (block_index INTEGER, block BLOB)")
        self.db.commit()
        cursor.close()
        # self.test_db()
        for peer in self.peers:
            mysqlite.update_latency(
                self.db, self.db_mutex, peer, 0.0, self.bind, self.port)
        signal.signal(signal.SIGINT, self.KeyboardInterruptHandler)
        self.serve()
        self.loop(1, self.update_blocks)
        self.loop(0.1, self.mine)
        self.loop(1, self.send_block_thread)
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


