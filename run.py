#!/usr/bin/env python

import signal
import random
from mininet.topo import Topo
from mininet.net import Mininet
from mininet.link import TCLink
from mininet.node import OVSSwitch
from mininet.log import lg, info
from mininet.cli import CLI
from mininet.clean import cleanup
from mininet.util import pmonitor


BW = 1  #Mbps
DELAY = '10ms'
LOSS = 2  #percents

class CircleTopo( Topo ):
    def build( self, k=2, n=1, **_opts):
        self.k = k
        self.n = n

        if n == 1:
            genHostName = lambda i, j: 'h%s' % i
        else:
            genHostName = lambda i, j: 'h%ss%d' % ( j, i )

        lastSwitch = None
        firstSwitch = None
        for i in irange( 1, k ):
            # Add switch
            switch = self.addSwitch( 's%s' % i )
            if not firstSwitch:
                firstSwitch = switch
            # Add hosts to switch
            for j in irange( 1, n ):
                host = self.addHost( genHostName( i, j ) )
                self.addLink( host, switch, bw=BW, delay=DELAY, loss=LOSS, use_htb=True )
            # Connect switch to previous
            if lastSwitch:
                self.addLink( switch, lastSwitch, bw=BW, delay=DELAY, loss=LOSS, use_htb=True )
            lastSwitch = switch

        if k > 1:
            self.addLink( lastSwitch, firstSwitch, bw=BW, delay=DELAY, loss=LOSS, use_htb=True )

class LinearNet( Topo ):
    def build( self, k=2, n=1, **_opts):
        self.k = k
        self.n = n

        if n == 1:
            genHostName = lambda i, j: 'h%s' % i
        else:
            genHostName = lambda i, j: 'h%ss%d' % ( j, i )

        lastSwitch = None
        for i in irange( 1, k ):
            # Add switch
            switch = self.addSwitch( 's%s' % i )
            # Add hosts to switch
            for j in irange( 1, n ):
                host = self.addHost( genHostName( i, j ) )
                self.addLink( host, switch, bw=BW, delay=DELAY, loss=LOSS, use_htb=True )
            # Connect switch to previous
            if lastSwitch:
                self.addLink( switch, lastSwitch, bw=BW, delay=DELAY, loss=LOSS, use_htb=True )
            lastSwitch = switch

class TreeTopo( Topo ):
    def build( self, depth=1, fanout=2 ):
        # Numbering:  h1..N, s1..M
        self.hostNum = 1
        self.switchNum = 1
        # Build topology
        self.addTree( depth, fanout )

    def addTree( self, depth, fanout ):
        """Add a subtree starting with node n.
           returns: last node added"""
        isSwitch = depth > 0
        if isSwitch:
            node = self.addSwitch( 's%s' % self.switchNum )
            self.switchNum += 1
            for _ in range( fanout ):
                child = self.addTree( depth - 1, fanout )
                self.addLink( node, child, bw=BW, delay=DELAY, loss=LOSS, use_htb=True )
        else:
            node = self.addHost( 'h%s' % self.hostNum )
            self.hostNum += 1
        return node

class TorusTopo( Topo ):
    def build( self, x, y, n=1 ):
        if x < 3 or y < 3:
            raise Exception( 'Please use 3x3 or greater for compatibility '
                             'with 2.1' )
        if n == 1:
            genHostName = lambda loc, k: 'h%s' % ( loc )
        else:
            genHostName = lambda loc, k: 'h%sx%d' % ( loc, k )

        hosts, switches, dpid = {}, {}, 0
        # Create and wire interior
        for i in range( 0, x ):
            for j in range( 0, y ):
                loc = '%dx%d' % ( i + 1, j + 1 )
                # dpid cannot be zero for OVS
                dpid = ( i + 1 ) * 256 + ( j + 1 )
                switch = switches[ i, j ] = self.addSwitch(
                    's' + loc, dpid='%x' % dpid )
                for k in range( 0, n ):
                    host = hosts[ i, j, k ] = self.addHost(
                        genHostName( loc, k + 1 ) )
                    self.addLink( host, switch, bw=BW, delay=DELAY, loss=LOSS, use_htb=True )
        # Connect switches
        for i in range( 0, x ):
            for j in range( 0, y ):
                sw1 = switches[ i, j ]
                sw2 = switches[ i, ( j + 1 ) % y ]
                sw3 = switches[ ( i + 1 ) % x, j ]
                self.addLink( sw1, sw2, bw=BW, delay=DELAY, loss=LOSS, use_htb=True )
                self.addLink( sw1, sw3, bw=BW, delay=DELAY, loss=LOSS, use_htb=True )

def LinearNet( k=1, n=1, **kwargs ):
    topo = LinearTopo( k, n )
    return Mininet( topo, **kwargs )

def CircleNet( k=1, n=1, **kwargs ):
    topo = LinearTopo( k, n )
    return Mininet( topo, **kwargs )

def TreeNet( depth=1, fanout=2, **kwargs ):
    topo = TreeTopo( depth, fanout )
    return Mininet( topo, **kwargs )

def StarNet( k=1, n=1, **kwargs ):
    topo = TreeTopo( 1, k )
    return Mininet( topo, **kwargs )

def TorusNet( x=1, y=1, n=1, **kwargs ):
    topo = TorusTopo( x, y, n )
    return Mininet( topo, **kwargs )

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
#    net = LinearNet(k=16, n=1, switch=OVSSwitch, link=TCLink)
#    net = CircleNet(k=16, n=1, switch=OVSSwitch, link=TCLink)
    net = TreeNet(depth=2, fanout=4, switch=OVSSwitch, link=TCLink)
#    net = StarNet(k=16, n=1, switch=OVSSwitch, link=TCLink)
#    net = TorusNet(x=4, y=4, n=1, switch=OVSSwitch, link=TCLink)
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
