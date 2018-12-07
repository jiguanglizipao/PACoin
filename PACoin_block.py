#!/usr/bin/env python3

import time
import pickle
import random
import PACrypto as crypto
import PACoin_utils as utils
import PACoin_txn

# pickle protocol is forced to be 2
pickle_protocol = 2


class MerkelTree:

    class Node:

        def __init__(self, node_type, depth, value, left_child=None, right_child=None):
            self.node_type = node_type  # define 0 as leaves and 1 as intermediate
            self.depth = depth  # 0 as root
            self.value = value
            self.left_child = left_child
            self.right_child = right_child

    def __init__(self, transaction_list):
        self.build_tree(transaction_list)

    def build_tree(self, transaction_list):
        self.transaction_num = len(transaction_list)
        self.node_list = []

        if(self.transaction_num == 0):
            return NULL

        n = 1
        depth = 0
        while(n < self.transaction_num):
            n *= 2
            depth += 1

        for transaction in transaction_list:
            assert isinstance(transaction, PACoin_txn.Transaction)
            value = utils.PACoin_hash(transaction)
            self.node_list.append(self.Node(0, depth, value))
        for i in range(self.transaction_num, n):
            self.node_list.append(self.node_list[-1])

        self.build(0, n, depth)
        self.root = self.node_list[-1]

    def build(self, start, end, depth):
        if depth == 0:
            return
        s = len(self.node_list)
        for i in range(start, end, 2):
            v1 = self.node_list[i].value
            v2 = self.node_list[i + 1].value
            m = str(v1) + str(v2)
            self.node_list.append(self.Node(1, depth - 1, utils.PACoin_hash(m),
                                            self.node_list[i], self.node_list[i - 1]))
        e = len(self.node_list)
        self.build(s, e, depth - 1)

    def serialized(self):
        return pickle.dumps(self, protocol=pickle_protocol)

    def print(self):
        i = 0
        for node in self.node_list:
            print(i, node.depth, node.value)
            i += 1


class Block:

    def __init__(self, version, parent_hash, transaction_list, threshold, timestamp, index, myaddr):
        assert isinstance(version, int) and version >= 0
        assert isinstance(parent_hash, str) and len(parent_hash) == 128
        assert isinstance(transaction_list, list)
        assert isinstance(threshold, int) and threshold >= 0
        assert isinstance(timestamp, int) and timestamp >= 0
        assert isinstance(index, int) and index >= 0
        assert isinstance(myaddr, str) and len(myaddr) == 88

        self.version = version
        self.parent_hash = parent_hash
        self.threshold = threshold
        self.timestamp = timestamp
        self.index = index
        self.fee = 1  # TODO: dynamic set base fee

        fee = self.fee
        for txn in transaction_list:
            self.fee += txn.tips

        fee_txin = PACoin_txn.Transaction.Txin(utils.generate_zero(128),
                                               0, utils.generate_zero(128), utils.generate_zero(96))
        fee_txout = PACoin_txn.Transaction.Txout(fee, myaddr)
        fee_txn = PACoin_txn.Transaction([fee_txin], [fee_txout], timestamp, 0)

        self.transaction_list = [fee_txn] + transaction_list

        merkle_tree = MerkelTree(self.transaction_list)
        self.merkle_root = merkle_tree.root

    def set_nonce(self, pow_n):
        self.nonce = pow_n

    def serialized(self):
        return pickle.dumps(self, protocol=pickle_protocol)

# if __name__ == '__main__':

#     l = []

#     for i in range(0, 12):
#         l.append('tran' + str(i))

#     tree = MerkelTree(l)
#     print(tree.transaction_num)
#     b = (0, 0, tree, time.time(), 0, 0)

#     tree.print()
