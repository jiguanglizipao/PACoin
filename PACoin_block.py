#!/usr/bin/env python3

import time
import pickle
import random
import PACrypto as crypto

# pickle protocol is forced to be 2
pickle_protocol = 2

def PACoin_hash(data):
    if isinstance(data, bytes):
        return crypto.generate_hash(data)
    return crypto.generate_hash(pickle.dumps(data, protocol=pickle_protocol))

class MerkelTree:

    class Node:

        def __init__(self, node_type, depth, value, left_child=None, right_child=None):
            self.node_type = node_type # define 0 as leaves and 1 as intermediate
            self.depth = depth # 0 as root
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
            value = PACoin_hash(transaction)
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
            v2 = self.node_list[i+1].value
            m = str(v1) + str(v2)
            self.node_list.append( self.Node(1, depth-1, PACoin_hash(m),
                            self.node_list[i], self.node_list[i-1] ))
        e = len(self.node_list)
        self.build(s, e, depth-1)

    def serialized(self):
        return pickle.dumps(self, protocol=pickle_protocol)

    def print(self):
        i = 0
        for node in self.node_list:
            print(i, node.depth, node.value)
            i += 1

class Block:

    def __init__(self, version, parent_hash, transaction_list, timestamp, index):
        self.version = version
        self.parent_hash = parent_hash
        self.transaction_list = transaction_list
        self.timestamp = timestamp
        self.index = index

        merkle_tree = MerkelTree(self.transaction_list)
        self.merkle_root = merkle_tree.root

    def set_pow_n(pow_n):
        self.pow_n = pow_n

    def serialized(self):
        return pickle.dumps(self, protocol=pickle_protocol)

def select_transactions(transactions):
    # TODO: select those with high tips
    # TODO: limited number
    return transactions

def get_last_block_hash():
    # TODO: fetch from sqlite
    return PACoin_hash('a')

def mine(version, all_transactions, index, threshold, n_try):
    transaction_list = select(all_transactions)
    parent_hash = get_last_block_hash()
    block = Block(version, parent_hash, transaction_list, time.time(), index)
    
    for i in range(n):
        n = int(random.random() * pow(2, 64))
        block.set_pow_n(n)
        h = PACoin_hash(block.serialized())
        if h < threshold:
            return block

    return None




# if __name__ == '__main__':

#     l = []

#     for i in range(0, 12):
#         l.append('tran' + str(i))

#     tree = MerkelTree(l)
#     print(tree.transaction_num)
#     b = (0, 0, tree, time.time(), 0, 0)

#     tree.print()


