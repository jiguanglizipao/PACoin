import pickle
import random
import time

import PACrypto as crypto
import PACoin_block

pickle_protocol = 2

def serialize(data):
    return pickle.dumps(data, protocol=pickle_protocol)

def deserialize(bin):
    return pickle.loads(bin)

def PACoin_hash(data):
    if isinstance(data, bytes):
        return crypto.generate_hash(data)
    return crypto.generate_hash(serialize(data))

def generate_random_transaction():
    priv_key1 = crypto.generate_private_key()
    pub_key1 = crypto.generate_public_key(priv_key1)
    addr1 = crypto.generate_address(pub_key1)
    priv_key2 = crypto.generate_private_key()
    pub_key2 = crypto.generate_public_key(priv_key2)
    addr2 = crypto.generate_address(pub_key2)

    amount = random.randint(0, 1e10)
    t = PACoin_block.Transaction(addr1, addr2, amount, int(amount*0.01), time.time(), pub_key1)
    return t

def validate_hash(hash_value, threshold):
    if hash_value <= threshold:
        return True
    return False