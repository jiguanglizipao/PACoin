#!/bin/sh
python3 -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. PACoin.proto
autopep8 PACoin_block.py PACoin.py PACoin_txn.py PACoin_utils.py PACrypto.py run.py Sqlite_utils.py -i
