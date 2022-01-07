#!/usr/bin/python

import os
from mininet.topo import Topo
from mininet.net import Mininet
from mininet.node import Node, CPULimitedHost
from mininet.link import TCLink

from mininet.log import setLogLevel, info

from mininet.cli import CLI
from mininet.link import Intf

from mininet.node import Controller, OVSSwitch, RemoteController
from mininet.util import dumpNodeConnections

# Sflow

# Compile and run sFlow helper script
# - configures sFlow on OVS
# - posts topology to sFlow-RT
# filename = '/home/mininet/startup_scirpt/sflow-rt/sflow-rt/extras/sflow.py'
# exec(compile(open(filename, "rb").read(), filename, 'exec'))

# Rate limit links to 10Mbps
# link = customClass({'tc':TCLink}, 'tc,bw=10')

# Overriding Topo itself
class Network( Topo ):
    def build( self ):
        h0= self.addHost('h0', cpu=0.1, ip='192.168.0.1/28')
        h1= self.addHost('h1', cpu=0.3, ip='192.168.0.2/28')
        h2= self.addHost('h2', cpu=0.2, ip='192.168.0.3/28')
        # h3= self.addHost('h3', cpu=0.2, ip='192.168.0.4/28')
        # h4= self.addHost('h4', bw=, cpu=, ip='192.168.0.')

        s0 = self.addSwitch('s0')
        s1 = self.addSwitch('s1')
        s2 = self.addSwitch('s2')
        # s3 = self.addSwitch('s3')
        # s4 = self.addSwitch('s4')


        # Bandwith = Mbps
        # Host to Switch
        for d, s in [ (h0, s0), (h1, s1) ]:
            self.addLink( d, s, bw=10, delay='10ms', loss=5, use_htb=True )
        for d, s in [ (h2, s2) ]:
            self.addLink( d, s, bw=20, delay='30ms', loss=10, use_htb=True )
        
        # Host to Switch
        for d, s in [ (h0, s0), (h1, s1), (h2, s2) ]:
            self.addLink( d, s, bw=30, loss=0, delay='5ms', use_htb=True )


        # Switch to Switch
        for d, s in [ (s0, s1), (s1, s2) ]:
            self.addLink( d, s )

        # Special Link
        # for d, s in [ () ]:
        #     self.addLink(d, s, cls=TCLink, bw=10)

# Add controller Example: https://github.com/Sirozha1337/mininet-python/blob/master/test.py
def run():
    # add Controller: https://stackoverflow.com/questions/61778913/add-remote-controller-mininet-cod
    # c0= RemoteController('name', ip=, port=)
    net = Mininet(topo=Network(), host=CPULimitedHost, link=TCLink, autoStaticArp=True)
    net.addController('ryu', controller=RemoteController, ip='0.0.0.0', port=6633)
    
    net.start()
    # Get node and test
    dumpNodeConnections(net.hosts)
    
    # h1, h2 = net.getNodeByName('h1', 'h2')
    # net.iperf( ( h1, h2 ), l4Type='UDP' )

    # Start mininet CLI
    CLI(net)

    # Stop net and clean
    # net.stop()


if __name__ == '__main__':
    setLogLevel('info')
    run()


    
