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
    cursor.execute(
            "INSERT INTO blocks (block_index, block) VALUES (?, ?)", (block_index, block, ))
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

def get_last_block_hash(db, db_mutex,):
    # TODO: not tested
    db_mutex.acquire()
    cursor = db.cursor()
    sql = """
            SELECT block
            FROM blocks
            ORDER BY block_index DESC
            LIMIT 1"""
    res = cursor.execute(sql)
    block_bin = res[0][0]
    db.commit()
    cursor.close()
    db_mutex.release()
    return utils.PACoin_hash(block_bin)



