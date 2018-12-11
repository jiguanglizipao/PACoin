import sqlite3
import pickle

import PACoin_block
import PACrypto
import PACoin_utils as utils

def list_peers(db, db_mutex, num=-1):
    db_mutex.acquire()
    cursor = db.cursor()
    if num >= 0:
        cursor.execute(
            "SELECT host FROM peers ORDER BY random() ASC LIMIT ?", (num, ))
    else:
        cursor.execute(
            "SELECT host FROM peers ORDER BY random() ASC")
#        print(cursor.fetchone())
    arr = [r[0] for r in cursor.fetchall()]
    cursor.close()
    db_mutex.release()
    return arr


def delete_peer(db, db_mutex, peer):
    db_mutex.acquire()
    cursor = db.cursor()
    cursor.execute(
        "DELETE FROM peers WHERE host = ?", (peer, ))
    cursor.close()
    db_mutex.release()


def init_latency(db, db_mutex, peer, timeout, bind, port):
    if peer == "%s:%d" % (bind, port):
        return
    db_mutex.acquire()
    cursor = db.cursor()
    cursor.execute("SELECT * FROM peers WHERE host = ?", (peer, ))
    if not cursor.fetchone():
        cursor.execute(
            "INSERT INTO peers (host, latency) VALUES (?, ?)", (peer, timeout, ))
#        print(cursor.fetchone())
    cursor.close()
    db_mutex.release()


def update_latency(db, db_mutex, peer, latency, bind, port):
    if peer == "%s:%d" % (bind, port):
        return
    db_mutex.acquire()
    cursor = db.cursor()
    cursor.execute(
        "UPDATE peers SET latency = ? WHERE host = ?", (latency, peer))
    if cursor.rowcount == 0:
        cursor.execute(
            "INSERT INTO peers (host, latency) VALUES (?, ?)", (peer, latency))
#        cursor.execute("SELECT * FROM peers WHERE host = ?", (peer, ))
#        print(cursor.fetchone())
    cursor.close()
    db_mutex.release()


def write_transaction(db, db_mutex, verified, transaction):
    db_mutex.acquire()
    cursor = db.cursor()
    data = transaction.serialized()
    hash = utils.PACoin_hash(data)
    cursor.execute(
        "INSERT INTO transactions (hash, verified, data) VALUES (?, ?)", (hash, verified, data, ))
    db.commit()
    cursor.close()
    db_mutex.release()


def update_verified_transaction(db, db_mutex, transaction_list, flag_list):
    assert len(transaction_list) == len(flag_list)
    db_mutex.acquire()
    cursor = db.cursor()
    for (t, f) in zip(transaction_list, flag_list):
        h = utils.PACoin_hash(t)
        cursor.execute(
            "UPDATE transactions SET verified = %d WHERE hash = %s" % (f, h))
    db.commit()
    cursor.close()
    db_mutex.release()


def write_block(db, db_mutex, block_index, block):
    # TODO: not tested
    db_mutex.acquire()
    cursor = db.cursor()
    cursor.execute(
        "SELECT block FROM blocks WHERE block_index = ?", (block_index, ))
    ret = False
    if not cursor.fetchone():
        cursor.execute(
            "INSERT INTO blocks (block_index, block) VALUES (?, ?)", (block_index, block, ))
        ret = True
    db.commit()
    cursor.close()
    db_mutex.release()

    return ret


def erase_block(db, db_mutex, block_index):
    # TODO: not tested
    db_mutex.acquire()
    cursor = db.cursor()
    cursor.execute(
        "DELETE FROM blocks WHERE block_index = ?", (block_index, ))
    db.commit()
    cursor.close()
    db_mutex.release()


def erase_block_range(db, db_mutex, block_index_range):
    # TODO: not tested
    db_mutex.acquire()
    cursor = db.cursor()
    cursor.execute(
        "DELETE FROM blocks WHERE (block_index >= ? and block_index < ?)", block_index_range)
    db.commit()
    cursor.close()
    db_mutex.release()


def get_block(db, db_mutex, block_index):
    db_mutex.acquire()
    cursor = db.cursor()
    cursor.execute(
        "SELECT block FROM blocks WHERE block_index = ?", (block_index, ))
    ret = None
    res = cursor.fetchone()
    if res:
       ret = res[0]

    db.commit()
    cursor.close()
    db_mutex.release()
    return ret


# block_index_range [l, r)
def get_block_range(db, db_mutex, base, num):
    db_mutex.acquire()
    cursor = db.cursor()
    cursor.execute(
        "SELECT block FROM blocks WHERE (block_index >= ? AND block_index < ?) ORDER BY block_index ASC",
        (base, base + num)
    )
    ret = cursor.fetchall()
    if len(ret) != num or ret[0][0] != base:
        # Not enough blocks or blocks don't begin with block_index_range[0]
        return []
    ret = [r[0] for r in ret]
    db.commit()
    cursor.close()
    db_mutex.release()
    return ret


def get_total_block_num(db, db_mutex):
    db_mutex.acquire()
    cursor = db.cursor()
    cursor.execute(
        "SELECT block_index FROM blocks ORDER BY block_index DESC LIMIT 1")
    res = cursor.fetchone()
    if not res:
        num = 0
    else:
        num = res[0] + 1
    db.commit()
    cursor.close()
    db_mutex.release()
    return num

    
def get_transaction(db, db_mutex, hash):
    db_mutex.acquire()
    cursor = db.cursor()
    cursor.execute(
        "SELECT data FROM transactions WHERE hash=%s" % hash)
    res = cursor.fetchone()
    db.commit()
    cursor.close()
    db_mutex.release()
    if not res:
        return None
    return utils.deserialize(res)


def get_last_block_idx_hash(db, db_mutex,):
    # TODO: not tested
    db_mutex.acquire()
    cursor = db.cursor()
    cursor.execute(
        "SELECT block_index, block FROM blocks ORDER BY block_index DESC LIMIT 1")
    res = cursor.fetchone()
    if not res:
        index = -1
        block_hash = utils.generate_zero(128)
    else:
        index = res[0]
        block_hash = utils.PACoin_hash(res[1])
    db.commit()
    cursor.close()
    db_mutex.release()
    return (index, block_hash)


def get_unverified_transactions(db, db_mutex,):
    db_mutex.acquire()
    cursor = db.cursor()
    sql = """
            SELECT data
            FROM transactions
            WHERE verified = 0 """
    res = cursor.execute(sql)
    transaction_list = []
    for row in res:
        data = utils.deserialize(row[0])
        transaction_list.append(data)
    db.commit()
    cursor.close()
    db_mutex.release()
    return transaction_list

