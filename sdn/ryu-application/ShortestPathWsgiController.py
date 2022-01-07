#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Base Application:
from ryu.base import app_manager
from ryu.controller.controller import Datapath
from ryu.lib import hub

# WSGI / REST API
import json
from ryu.app.wsgi import WSGIApplication, ControllerBase, Response, route
from ryu.lib import dpid as dpid_lib

# Event
from ryu.ofproto import ofproto_v1_3
from ryu.controller import event, ofp_event
from ryu.controller.handler import set_ev_cls, MAIN_DISPATCHER, CONFIG_DISPATCHER, DEAD_DISPATCHER
from ryu.ofproto.ofproto_parser import MsgBase

# Topology Method
from ryu.lib.packet import packet, ethernet
from ryu.topology import event
from ryu.topology.api import get_link, get_switch, get_host
from ryu.lib.mac import haddr_to_bin
from ryu.lib.packet import packet, ethernet
from ryu.lib import hub

# Type hint
from typing import Awaitable, List, Dict
from ryu.ofproto.ofproto_v1_3_parser import OFPFlowStatsReply

# Additional Libary:
import networkx as nx # Graph
from operator import attrgetter

from BaseController13 import BaseController13

APP_NAME = 'ShortestPathWsgiController'

class ShortestPathWsgiController(BaseController13.BaseController13):

    # Version - Context
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]
    _CONTEXTS = {'wsgi': WSGIApplication}

    def __init__(self, *_args, **_kwargs):
        super(ShortestPathWsgiController, self).__init__(self, *_args, **_kwargs)

        # Register the WSGI application
        wsgi: WSGIApplication = _kwargs['wsgi']
        wsgi.register(ControllerRestApi, {APP_NAME: self})

        #thread
        self.monitor_thread = hub.spawn(self._monitor)

        # Datapaths
        self.topology_api_app = self
        self.datapaths: Dict[Datapath.id, Datapath] = {}  # Store switch in topology using OpenFlow

        # Topology: hosts, swtiches, links
        self.hosts = {}
        self.switches = {}
        self.links = {}
        self.topology = []

        self.number_of_nodes = 0
        self.number_of_links = 0
        self.number_of_hosts = 0

        # Network Statistic:
        self.flow_stat = []
        self.port_stat = []
        self.net_statistic = []

        # NetworkX graph
        self.net = nx.DiGraph()


    def _packet_in_handler(self, ev):
        pass
    
    '''

    '''
    def getTopology(self):
        self.hosts = get_host(self)
        self.switches = get_switch(self)
        self.links = get_link(self)
        return self.hosts, self.switches, self.links

    # refactor: https://github.com/faucetsdn/ryu/blob/537f35f4b2bc634ef05e3f28373eb5e24609f989/ryu/app/rest_topology.py#L113
    @set_ev_cls(event.EventSwitchEnter)
    def getTopologyGraph(self, ev):
        # Get switch id from swtich_list
        switch_list = get_switch(self.topology_api_app, None)
        switches=[switch.dp.id for switch in switch_list]
        self.net.add_nodes_from(switches)

        # Get link src and dst id from link_list
        links_list = get_link(self.topology_api_app, None)
        links=[(link.src.dpid,link.dst.dpid,{'port':link.src.port_no}) for link in links_list]
        self.net.add_edges_from(links)

'''
Rest APi Interface:

'''
class ControllerRestApi(ControllerBase):
    def __init__(self, req, link, data, **config):
        super().__init__(req, link, data, **config)
        self.data = data
        self.app: ShortestPathWsgiController = data[APP_NAME]

    @route(APP_NAME, '/get_app', methods=['GET'])
    def getApps(self, req, **_kwargs):
        body = str(self.app)
        print(self.app)

    # TODO: REFACTOR THIS PART
    @route(APP_NAME, '/get_topology_graph', methods=['GET'])
    def getTopologyGraph(self, req, **_kwargs):
        topo = [{'Switches': self.app.switches, 'Links': self.app.links, 'Topo': str(self.app.net.edges())}]
        body = json.dumps(topo)
        return Response(content_type='application/json', body=body)

    @route(APP_NAME, '/get_topology', methods=['GET'])
    def get(self, req, **_kwargs):
        hosts, switches, links = self.app.getTopology()
        host_dict = [host.to_dict() for host in hosts]
        link_dict = [link.to_dict() for link in links]
        switch_dict = [switch.to_dict() for switch in switches]

        topo = [{'host': host_dict, 'switch': switch_dict, 'link': link_dict}]
        body = json.dumps(topo)
        return Response(content_type='application/json', body=body)

    # TODO: Construct this part
    @route(APP_NAME, '/set_flow', methods=['GET'], requirements={'dpid': dpid_lib.DPID_PATTERN})
    def addFlow(self, req, **_kwargs):
        self.app().addFlow()

    @route(APP_NAME, '/hello', methods=['GET'])
    def getHello(self, req, **kwargs):
        # body = json.dumps({'message': 'Ok - Hello!'})
        body = 'Hello!'
        return Response(body=body)
        # return Response(content_type='application/json', body=body)

    @route(APP_NAME, '/port_stat', methods=['GET'])
    def getPortStat(self, req, **kwargs):
        body = json.dumps(self.app.port_stat)
        return Response(content_type='application/json', body=body)

    @route(APP_NAME, '/flow_stat', methods=['GET'])
    def getFlowStat(self, req, **kwargs):
        body = json.dumps(self.app.flow_stat)
        return Response(content_type='application/json', body=body)
    
    # @route(APP_NAME, '/net_statistics', methods=['GET'])
    # def getNetStatistics(self, req, **kwargs):
    #     for i in len(self.app.net_statistic):
            
    #     body = json.dumps()
    #     return Response(content_type='application/json', body=body)

'''
Thêm số đo thực tế loss.
Add flow
Restful api điều khiển - getSwitch, getLink

NOTE: pingall before get_host and port_stat or flow_stat also net_statistics
SND CONTROLLER only communicate with switch not host. (https://stackoverflow.com/questions/46230905/how-to-send-data-from-ryu-controller-to-host)
'''
