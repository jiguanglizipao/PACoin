#!/usr/bin/env python3
from concurrent import futures
import time
import logging

import grpc

import PACoin_pb2
import PACoin_pb2_grpc

class P2PDiscoveryServicer(PACoin_pb2_grpc.P2PDiscoveryServicer):
    def ping(self, request, context):
        print("receive: ", request.host)
        return PACoin_pb2.PingReply(ret=PACoin_pb2.ERRNO(PACoin_pb2.ERRNO.SUCCESS))

def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=4))
    PACoin_pb2_grpc.add_P2PDiscoveryServicer_to_server(P2PDiscoveryServicer(), server)
    server.add_insecure_port('[::]:8888')
    server.start()

def run():
    with grpc.insecure_channel('localhost:8888') as channel:
        stub = PACoin_pb2_grpc.P2PDiscoveryStub(channel)
        response = stub.ping(PACoin_pb2.PingRequest(host="localhost:8888"))
        print("response: ", response.ret)

if __name__ == '__main__':
    logging.basicConfig()
    serve()
    time.sleep(100)
    run()
