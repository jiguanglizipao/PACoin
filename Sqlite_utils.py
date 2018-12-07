import sqlite3
import pickle

import PACoin_block
import PACrypto
import PACoin_utils as utils


def write_transaction(db, db_mutex, verified, transaction):
    db_mutex.acquire()
    cursor = db.cursor()
    data = transaction.serialized()
    cursor.execute(
        "INSERT INTO transactions (verified, data) VALUES (?, ?)", (verified, data, ))
    db.commit()
    cursor.close()
    db_mutex.release()


def update_transaction(db, db_mutex, id_list, flag_list):
    db_mutex.acquire()
    cursor = db.cursor()
    assert(len(id_list) == len(flag_list))
    for (i, f) in zip(id_list, flag_list):
        cursor.execute(
            "UPDATE transactions SET verified = %d WHERE id = %d" % (f, i))
    db.commit()
    cursor.close()
    db_mutex.release()


def write_block(db, db_mutex, block_index, block):
    # TODO: not tested
    db_mutex.acquire()
    cursor = db.cursor()
    data = block.serialized()
    res = cursor.execute(
        "SELECT block FROM blocks WHERE block_index = ?", (block_index, ))
    if not cursor.fetchone():
        cursor.execute(
            "INSERT INTO blocks (block_index, block) VALUES (?, ?)", (block_index, block.serialized(), ))
    db.commit()
    cursor.close()
    db_mutex.release()


def get_unverified_transactions(db, db_mutex,):
    db_mutex.acquire()
    cursor = db.cursor()
    sql = """
            SELECT id, data
            FROM transactions
            WHERE verified = 0 """
    res = cursor.execute(sql)
    transaction_list = []
    for row in res:
        pair = (row[0], utils.deserialize(row[1]))
        transaction_list.append(pair)
    db.commit()
    cursor.close()
    db_mutex.release()
    return transaction_list


def get_last_block_idx_hash(db, db_mutex,):
    # TODO: not tested
    db_mutex.acquire()
    cursor = db.cursor()
    cursor.execute(
        "SELECT block_index, block FROM blocks ORDER BY block_index DESC LIMIT 1")
    res = cursor.fetchone()
    if not res:
        index = 0
        block_hash = utils.generate_zero(128)
    else:
        index = res[0]
        block_hash = utils.PACoin_hash(res[1])
    db.commit()
    cursor.close()
    db_mutex.release()
    return (index, block_hash)
