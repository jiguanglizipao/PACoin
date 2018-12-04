#!/usr/bin/env python3
from concurrent import futures
import time
import logging
import threading
import signal
import argparse
import grpc
import PACoin_pb2
import PACoin_pb2_grpc

parser = argparse.ArgumentParser(description='Process some arguments')
parser.add_argument('--port', type=int, default=23333, help='Listening port')
parser.add_argument('--bind', type=str, default="[::]", help='Listening ip')
parser.add_argument(
    '--peer', type=str, default="localhost:23333", help='First peer to connect')


def KeyboardInterruptHandler(signum, frame):
    global to_exit
    to_exit = True


class P2PDiscoveryServicer(PACoin_pb2_grpc.P2PDiscoveryServicer):

    def ping(self, request, context):
        ip = context.peer().split(':')[1]
        print("receive: ", ip, request.port)
        return PACoin_pb2.PingReply(ret=PACoin_pb2.SUCCESS)


def serve():
    global server
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=4))
    PACoin_pb2_grpc.add_P2PDiscoveryServicer_to_server(
        P2PDiscoveryServicer(), server)
    server.add_insecure_port("%s:%d" % (args.bind, args.port))
    server.start()


def ping():
    try:
        start_time = time.time()
        with grpc.insecure_channel(args.peer) as channel:
            stub = PACoin_pb2_grpc.P2PDiscoveryStub(channel)
            response = stub.ping(
                PACoin_pb2.PingRequest(port=args.port), timeout=1)
            latency = time.time() - start_time
            print("response = ", response.ret, ", latency = %.2f ms" %
                  (latency.real * 1e3))
    except Exception as e:
        print(e)


def loop(seconds, func):
    func()
    if not to_exit:
        timer = threading.Timer(seconds, loop, (seconds, func))
        timer.start()

if __name__ == '__main__':
    global to_exit
    to_exit = False
    signal.signal(signal.SIGINT, KeyboardInterruptHandler)

    global args
    args = parser.parse_args()
    logging.basicConfig()

    serve()
    loop(2, ping)
#    run()
