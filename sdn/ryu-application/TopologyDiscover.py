#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# base:
from ryu.base import app_manager
from ryu.controller.handler import set_ev_cls
from ryu.ofproto import ofproto_v1_3

#component
from ryu.topology import event
from ryu.topology.api import get_host, get_switch, get_link
from ryu.app import simple_switch_13
# networkx libary for graph network
import networkx as nx

class TopologyDiscover(simple_switch_13.SimpleSwitch13):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]
    
    def __init__(self, *args, **kwargs ):
        super(TopologyDiscover, self).__init__(self, *args, **kwargs )
        self.topology_api_app = self
        self.net = nx.DiGraph()
        
    @set_ev_cls(event.EventSwitchEnter)
    def getTopologyData(self, ev):
        switch_list = get_switch(self.topology_api_app, None)   
        switches=[switch.dp.id for switch in switch_list]
        self.net.add_nodes_from(switches)
         
        #print "**********List of switches"
        #for switch in switch_list:
        #self.ls(switch)
        #print switch
        #self.nodes[self.no_of_nodes] = switch
        #self.no_of_nodes += 1
	
        links_list = get_link(self.topology_api_app, None)
        #print links_list
        links=[(link.src.dpid,link.dst.dpid,{'port':link.src.port_no}) for link in links_list]
        #print links
        self.net.add_edges_from(links)
        links=[(link.dst.dpid,link.src.dpid,{'port':link.dst.port_no}) for link in links_list]
        #print links
        self.net.add_edges_from(links)

        
        host_list = get_host(self.topology_api_app, None)
        hosts = [(host.mac, host.port.dpid, {'port': host.port.port_no}) for host in host_list]
        
        print("**********List of links")
        print(self.net.edges())
        
        # print('link: ', links)
        # print('switch: ',switches)
        # print('hosts:', hosts)
        
        print('swtichs:', get_switch(self.topology_api_app, None))
    
# Run application: 
