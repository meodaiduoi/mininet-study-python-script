from flask import Flask, request
import json
import os
from mininet.net import Mininet
from mininet.node import Controller, OVSSwitch, RemoteController
from mininet.cli import CLI

#clear mang
os.system("sudo mn -c")

net = Mininet(controller=Controller, switch=OVSSwitch, waitConnected=False)

#add controller
c1 = net.addController("c1", controller=RemoteController, ip='172.19.0.2', port=6653)
c2 = net.addController("c2", controller=RemoteController, ip='172.19.0.3', port=6653)

#add host add switch
h1 = net.addHost("h1")
h2 = net.addHost("h2")
h3 = net.addHost("h3")
h4 = net.addHost("h4")

s1 = net.addSwitch("s1")
s2 = net.addSwitch("s2")
s3 = net.addSwitch("s3")
s4 = net.addSwitch("s4")

#them canh noi host -> switch, switch -> switch
net.addLink(h1, s1)
net.addLink(h2, s2)
net.addLink(h3, s3)
net.addLink(h4, s4)

net.addLink(s1, s2)
net.addLink(s2, s3)
net.addLink(s3, s4)

net.build() #sinh ip cho cac host

#====================map switch voi controller=========================
c1.start()
c2.start()

#switch nao start tren controller nao
s1.start([c1])
s2.start([c1])
s3.start([c2])
s4.start([c2])
#======================================================================

#net.start() #start toan bo switch, k nen dung lenh nay

app = Flask(__name__)

#http://192.168.254.135:5000/test
@app.route('/test', methods=['GET'])
def test():
    return json.dumps({})

#app.run(host='0.0.0.0', debug=True, use_reloader=False) #chay flash
CLI(net) #cli mininet
#net.stop()

#python3 -pip install mininet
#sudo python3 -E file.py
