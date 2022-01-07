from mininet.topo import Topo

class MyTopo( Topo ):
    "Simple topology example."

    def __init__( self ):
        "Create custom topo."

        # Initialize topology
        Topo.__init__( self )

        # Add hosts 
        A = self.addHost('h1')
        B = self.addHost('h2')
        C = self.addHost('h3')
        D = self.addHost('h4')
	# add swich
        sA=self.addSwitch('s1')
        sB=self.addSwitch('s2')
        sC=self.addSwitch('s3')
        sD=self.addSwitch('s4')
       
                 
        # Add links
        self.addLink (sA, sB)
        self.addLink (sA, sC)
        self.addLink (sB, sD)
        self.addLink (sC, sD)

	# add 
        self.addLink(A,sA)
        self.addLink(B,sA)
        self.addLink(C,sD)
        self.addLink(D,sD)
       
	# sudo mn --controller=remote,ip=127.0.0.1,port=6653 --custom code2.py --topo tp

topos = { 'tp': ( lambda: MyTopo() ) }
#sudo mn --custom code2.py --topo tp --controller=remote,ip=192.168.187.128,port=6633
#sudo mn --controller=remote,ip=127.0.0.1,port=6653 --custom code2.py,sflow-rt/extras/sflow.py --topo tp
