#!/usr/bin/env python3

import time
import pickle
import random
import PACrypto as crypto
import PACoin_utils as utils

# pickle protocol is forced to be 2
pickle_protocol = 2


class Transaction:

    class Txin:

        def __init__(self, pre_txn_hash, pre_txout_idx, pre_txout_pubkey, pre_txout_sign):
            # pre_txn_hash is in base16
            # pre_txn_sign is in base64
            assert isinstance(pre_txn_hash, str) and len(pre_txn_hash) == 128
            assert isinstance(
                pre_txout_idx, int) and pre_txout_idx < 2**32 and pre_txout_idx >= 0
            assert isinstance(pre_txout_pubkey, str) and len(
                pre_txout_pubkey) == 128
            assert isinstance(pre_txout_sign, str) and len(
                pre_txout_sign) == 96
            self.pre_txn_hash = pre_txn_hash
            self.pre_txout_idx = pre_txout_idx
            self.pre_txout_pubkey = pre_txout_pubkey
            self.pre_txout_sign = pre_txout_sign

    class Txout:

        def __init__(self, value, address):
            # address is in base64
            assert isinstance(value, int) and value >= 0
            assert isinstance(address, str) and len(address) == 88
            self.value = value
            self.address = address

    # The first txn of a block is mining reward. txins is coinbase, pre_txn_hash=0x000...000, pre_txout_idx=0, pre_txout_pubkey=pre_txout_sign=0x000...000.
    # Tips is the first txout, the address is coinbase ( 0x000...000 ).
    def __init__(self, txins, txouts, timestamp, tips):
        assert isinstance(txins, list)
        for i in txins:
            assert isinstance(i, Transaction.Txin)
        assert isinstance(txouts, list)
        for i in txouts:
            assert isinstance(i, Transaction.Txout)
        assert isinstance(timestamp, int) and timestamp >= 0
        assert isinstance(timestamp, int) and tips >= 0
        self.txins = txins
        self.txouts = txouts
        self.timestamp = timestamp
        self.tips = tips

    def get_outvalue(self, idx):
        return txouts[idx].value

    def serialized(self):
            return pickle.dumps(self, protocol=pickle_protocol)

    def sign(self, txout_idx, pkey):
        assert txout_idx < 2**32 and txout_idx >= 0
        return crypto.generate_sign(self.transaction.serialized() + txout_idx.to_bytes(4, 'big'), pkey)
