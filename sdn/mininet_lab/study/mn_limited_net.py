'''
Self study about net delay and 

'''
from mininet.net import Mininet
from mininet.node import CPULimitedHost #cpu Related settings
from mininet.link import TCLink # addLink Related settings

net = Mininet(host=CPULimitedHost, link=TCLink) # If performance is not limited, the parameter is empty

# http://intronetworks.cs.luc.edu/current/html/mininet.html

h1 = net.addHost('h1')
h2 = net.addHost('h2')
h3 = net.addHost('h3')

s1 = net.addSwitch('s1', cpu=0.9)
s2 = net.addSwitch('s2', cpu=0.7)
s3 = net.addSwitch('s3', cpu=0.5)

net.addLink(h1, s1)
net.addLink(h2, s2)
net.addLink(h3, s3)

net.addLink(s1, s2)
net.addLink(s2, s3)

net.pingAll()