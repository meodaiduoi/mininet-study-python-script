from mininet.topo import Topo
from mininet.net import Mininet
from mininet.node import CPULimitedHost
from mininet.link import TCLink
from mininet.util import dumpNodeConnections
from mininet.log import setLogLevel

class MyTopo( Topo ):
    "Simple topology example."

    def __init__( self ):
        "Create custom topo."

        # Initialize topology
        Topo.__init__( self )
        
        h1= self.addHost('h1', cpu=0.1, ip='10.0.0.1/8')
        h2= self.addHost('h2', cpu=0.1, ip='10.0.0.2/8')
        h3= self.addHost('h3', cpu=0.2, ip='10.0.0.3/8')
        # h4= self.addHost('h3', cpu=0.3, ip='10.0.0.4/8')
        # h6= self.addHost('h4', cpu=, ip='192.168.0.')

        s1 = self.addSwitch('s1')
        s2 = self.addSwitch('s2')
        s3 = self.addSwitch('s3')
        # s3 = self.addSwitch('s4')
        # s4 = self.addSwitch('s5')

        # Bandwith = Mbps
        # Host to Switch
        for d, s in [ (h1, s1), (h2, s2), (h3, s3) ]:
            self.addLink( d, s, use_htb=True, cls=TCLink )
        
        for d, s in [ (s1, s2) ]:
            self.addLink( d, s, bw=20, delay='0ms', loss=5, use_htb=True, cls=TCLink )
        for s, d in [ (s2, s3) ]:
            self.addLink( s, d, bw=30, delay='0ms', loss=10, use_htb=True, cls=TCLink )

       
	# sudo mn --custom topo_ln_delay_loss.py --topo=topo --controller=remote

topos = { 'topo': ( lambda: MyTopo() ) }