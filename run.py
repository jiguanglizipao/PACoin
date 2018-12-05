#!/usr/bin/env python

import signal
import random
from mininet.topolib import TreeNet
from mininet.net import Mininet
from mininet.node import OVSSwitch
from mininet.log import lg, info
from mininet.cli import CLI
from mininet.clean import cleanup
from mininet.util import pmonitor


def KeyboardInterruptHandler(signum, frame):
    global popens, net
    for host, fd in popens.iteritems():
        fd.send_signal(signal.SIGINT)
    for host, fd in popens.iteritems():
        fd.wait()
    net.stop()


if __name__ == '__main__':
    cleanup()
    lg.setLogLevel('info')

    global popens, net
    net = TreeNet(depth=3, fanout=4, switch=OVSSwitch)
    net.start()

    popens = {}
    for host in net.hosts:
        popens[host] = host.popen(
            'sudo -u vagrant python3 -u PACoin.py --bind %s --port 23333 --db %s --peer %s:23333 %s:23333 %s:23333' % (host.IP(), host.name + ".db", net.hosts[0].IP(), net.hosts[random.randint(0, len(net.hosts) - 1)].IP(), net.hosts[random.randint(0, len(net.hosts) - 1)].IP()))

    signal.signal(signal.SIGINT, KeyboardInterruptHandler)

    try:
        for host, line in pmonitor(popens):
            if host:
                info("<%s>: %s" % (host.name, line))
    except Exception as e:
        pass
