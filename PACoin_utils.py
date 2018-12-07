import pickle
import random
import time

import PACrypto as crypto
import PACoin_block
import PACoin_txn

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
