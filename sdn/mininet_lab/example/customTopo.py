from miniet.topo import Topo

def __init__(self):
    
    Topo.__init__(self)
    
    h1 = self.addHost('h1')
    h2 = self.addHost('h2')
    h3 = self.addHost('h3')

    s1 = self.addSwitch('s1')
    s2 = self.addSwitch('s2')

    self.addLink(h1, s1)
    self.addLink(h2, s2)
    self.addLink(h3, s2)
    self.addLink(s1, s2)
    
