import pickle
import random
import time
import base64

import PACrypto as crypto
import PACoin_block
import PACoin_txn
import Sqlite_utils as mysqlite

pickle_protocol = 2


def serialize(data):
    return pickle.dumps(data, protocol=pickle_protocol)


def deserialize(bin):
    return pickle.loads(bin)


def PACoin_hash(data):
    if isinstance(data, bytes):
        return crypto.generate_hash(data)
    return crypto.generate_hash(serialize(data))

# def generate_random_transaction():
#    priv_key1 = crypto.generate_private_key()
#    pub_key1 = crypto.generate_public_key(priv_key1)
#    addr1 = crypto.generate_address(pub_key1)
#    priv_key2 = crypto.generate_private_key()
#    pub_key2 = crypto.generate_public_key(priv_key2)
#    addr2 = crypto.generate_address(pub_key2)
#
#    amount = random.randint(0, 1e10)
#    t = PACoin_block.Transaction(addr1, addr2, amount, int(amount*0.01), time.time(), pub_key1)
#    return t


def validate_hash(hash_value, threshold):
    if threshold // 4 * 4 == threshold:
        str = ''.join(['0' for n in range(0, threshold // 4)]) + \
            ''.join(['f' for n in range(threshold // 4, 512 // 4)])
    else:
        str = ''.join(['0' for n in range(0, threshold)]) + \
            ''.join(['1' for n in range(threshold, 512)])
        str = '{:0>128x}'.format(int(str, 2))
    if hash_value <= str:
        return True
    return False


def generate_zero(num):
    str = ''.join(['0' for n in range(0, num)])
    return str


def validate_single_txin(txin, pre_t):
    addr = crypto.generate_address(txin.pre_txout_pubkey)
    if addr != pre_t.txouts[txin.pre_txout_idx].address:
        print("ERROR: address matching failed")
        return False
    s = bytes()
    for txout in pre_t.txouts:
        s += txout.serialized()
    sign_data = pre_t.serialized() + txin.pre_txout_idx.to_bytes(4, 'big') + s
    if not crypto.verify_sign(sign_data, txin.pre_txout_sign, txin.pre_txout_pubkey):
        print("ERROR: sign validation failed")
        return False
    return True


def validate_transaction(db, db_mutex, transaction):
    # TODO: not tested
    # TXin: pre_txn_hash, pre_txout_idx, pre_txout_pubkey, pre_txout_sign
    if len(transaction.txouts) < 1:
        return False
    balance = 0
    for txin in transaction.txins:
        h = txin.pre_txn_hash
        pre_t = mysqlite.get_transaction(db, db_mutex, h)
        if not pre_t:
            print("ERROR: pre txn not found")
            return False
        if not validate_single_txin(txin, pre_t):
            return False
        balance += pre_t.txouts[txin.pre_txout_idx].value
    if transaction.txouts[0].address != generate_zero(88):
        print(transaction.txouts[0].address)
        print("ERROR: not pay for tips")
        return False
    if transaction.txouts[0].value != transaction.tips:
        print("ERROR: invalid tips value")
        return False
    consume = sum([txout.value for txout in transaction.txouts])
    if balance != consume:
        print("ERROR: in-out ")
        return False
    return True


def find_signs_in_block_chain(db, db_mutex, signs):
    block_num = mysqlite.get_total_block_num(db, db_mutex)
    for i in range(block_num):
        block = mysqlite.get_block(db, db_mutex, block_num-i)
        if isinstance(block, bytes):
            block = deserialize(block)
        for txn in block.transaction_list:
            for txin in txn.txins:
                if txin.pre_txout_sign in signs:
                    return True
    block_num_new = mysqlite.get_total_block_num(db, db_mutex)
    while block_num_new > block_num:
        for i in range(block_num+1, block_num_new+1):
            block = mysqlite.get_block(db, db_mutex, i)
            if isinstance(block, bytes):
                block = deserialize(block)
            for txn in block.transaction_list:
                for txin in txn.txins:
                    if txin.pre_txout_sign in signs:
                        return True
        block_num = block_num_new
        block_num_new = mysqlite.get_total_block_num(db, db_mutex)
    return False

# ==== Block ====
# self.version = version
# self.parent_hash = parent_hash
# self.index = index
# self.timestamp = timestamp

# self.myaddr = myaddr
# self.fee = mining_reward + sum(tips)
# self.transaction_list = [fee_txn] + transaction_list
# self.merkle_root = merkle_tree.root

# self.nonce = pow_n
# self.threshold = threshold

def validate_block(db, db_mutex, block, version, reward, threshold):
    # TODO: not tested
    # validate basic information
    if block.version != version:
        return False
    (index, pre_hash) = mysqlite.get_last_block_idx_hash(db, db_mutex)
    if block.parent_hash != pre_hash:
        return False
    if block.index != index + 1:
        return False

    # TODO: validate timestamp?

    # validate pow
    hash = PACoin_hash(block)
    if not validate_hash(hash, threshold):
        return False

    # validate transactions
    merkle_tree = PACoin_block.MerkelTree(block.transaction_list)
    if merkle_tree.root.value != block.merkle_root.value:
        return False
    transaction_list = block.transaction_list
    if len(transaction_list[0].txins) == 1 and  len(transaction_list[0].txouts) == 1:
        if transaction_list[0].txins[0].pre_txn_hash == generate_zero(128):
            # mining reward
            reward_txn = transaction_list[0]
            transaction_list = transaction_list[1:]
            fee = reward + sum([txn.tips for txn in transaction_list])
            if fee != reward_txn.txouts[0].value:
                return False
            if block.myaddr != reward_txn.txouts[0].address:
                return False
    signs = [] # do not allow the same sign
    for transaction in transaction_list:
        if not validate_transaction(db, db_mutex, transaction):
            return False
        for txin in transaction.txins:
            if txin.pre_txout_sign in signs:
                return False
            signs.append(txin.pre_txout_sign)
    if find_signs_in_block_chain(db, db_mutex, signs):
        return False
    return True


def bytes2Data(bs):
    return base64.b64encode(bs).decode("utf-8")


def data2Bytes(data: str):
    return base64.b64decode(data.encode("utf-8"))


