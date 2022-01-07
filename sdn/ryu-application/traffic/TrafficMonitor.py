#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Base Application:
from BaseController13 import BaseController13
from ryu.controller.controller import Datapath

# WSGI / REST API
import json
from ryu.app.wsgi import WSGIApplication, ControllerBase, Response, route
from ryu.lib import dpid as dpid_lib

# Event
from ryu.ofproto import ofproto_v1_3
from ryu.controller import ofp_event
from ryu.controller.handler import set_ev_cls, MAIN_DISPATCHER, DEAD_DISPATCHER, CONFIG_DISPATCHER
from ryu.ofproto.ofproto_parser import MsgBase

# Topology Method
from ryu.topology.api import get_link, get_switch, get_host
from ryu.topology.switches import Switch, Link, Host, Port

# Packet sender
from ryu.lib.packet import packet
from ryu.lib.packet import ethernet, ipv4, arp, ipv6, icmp
from ryu.lib.packet import ether_types, in_proto

# Thread
from ryu.lib import hub, mac

# Type hint
from typing import List, Dict

# Additional Libary:
import networkx as nx # Graph
from operator import attrgetter
import time

from ryu.app import simple_switch_14, simple_switch_13

APP_NAME = 'TrafficMonitor'
MONITOR_INTERVAL = 30
DISCOVER_INTERVAL = 5

class TrafficMonitor(simple_switch_14.SimpleSwitch14):

    # Version - Context
    _CONTEXTS = {'wsgi': WSGIApplication}

    def __init__(self, *_args, **_kwargs):
        super(TrafficMonitor, self).__init__(self, *_args, **_kwargs)
        
        # Register the WSGI application
        wsgi: WSGIApplication = _kwargs['wsgi']
        wsgi.register(TrafficMonitorRest, {APP_NAME: self})

        #thread
        self.monitor_thread = hub.spawn(self._monitor_thread)
        self.discover_thread = hub.spawn(self._discover_thread)
        
        # Topology and datapath
        self.topology_api_app = self
        self.datapaths: Dict[Datapath.id, Datapath] = {}  # Store switch in topology using OpenFlow
        self.hosts: List[Host]= []
        self.switches: List[Switch] = []
        self.links: List[Link] = []
        self.topology = []
        self.mac_to_port = {}

        # self.number_of_nodes = 0
        # self.number_of_links = 0
        # self.number_of_hosts = 0

        # Network Statistic:
        self.flow_stat = []
        self.port_stat = []
        self.links_packet_loss = []
        self.links_throughput = []

        # NetworkX graph
        self.net = nx.DiGraph()

            
    '''
        Seperate thread
    '''
    def _monitor_thread(self):
        while True:
            for dp in self.datapaths.values():
                self._requestStats(dp)
            hub.sleep(MONITOR_INTERVAL)
            
            # Clear up the statistics
            self.flow_stat = []
            self.port_stat = []
            
    def _discover_thread(self):
        while True:
            self.get_topology_data()
            hub.sleep(DISCOVER_INTERVAL)

    '''
        Request Send:
    '''
    def _requestStats(self, datapath):
        self.logger.debug('send stats request: %016x', datapath.id)
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        # Send OFP Flow Stat Request
        req = parser.OFPFlowStatsRequest(datapath)
        datapath.send_msg(req)

        # Send OFP Port Stat Request
        req = parser.OFPPortStatsRequest(datapath, 0, ofproto.OFPP_ANY)
        datapath.send_msg(req)
        
    '''
        Reply Handle
    '''
    @set_ev_cls(ofp_event.EventOFPStateChange, [MAIN_DISPATCHER, DEAD_DISPATCHER])
    def _state_change_handler(self, ev):
        datapath = ev.datapath
        if ev.state == MAIN_DISPATCHER:
            if datapath.id not in self.datapaths:
                self.logger.debug('register datapath: %016x', datapath.id)
                self.datapaths[datapath.id] = datapath
        elif ev.state == DEAD_DISPATCHER:
            if datapath.id in self.datapaths:
                self.logger.debug('unregister datapath: %016x', datapath.id)
                del self.datapaths[datapath.id]

    @set_ev_cls(ofp_event.EventOFPFlowStatsReply, MAIN_DISPATCHER)
    def _flow_stats_reply_handler(self, ev):

        msg: MsgBase = ev.msg
        datapath: Datapath= msg.datapath
        body = msg.body
        
        for stat in sorted([flow for flow in body if flow.priority == 1],
                           key=lambda flow: (flow.match['in_port'],
                                             flow.match['eth_dst'])):
            self.flow_stat.append(
                {
                    'dpid': datapath.id,
                    'in_port': stat.match['in_port'],
                    'out_port': stat.instructions[0].actions[0].port,
                    'eth_dst': stat.match['eth_dst'],
                    'packet': stat.packet_count,
                    'bytes': stat.byte_count
                }
            )
        self.flow_stat.sort(key=lambda x: x['dpid'])
        

    @set_ev_cls(ofp_event.EventOFPPortStatsReply, MAIN_DISPATCHER)
    def _portStatsReplyHandler(self, ev):

        msg: MsgBase = ev.msg
        body = msg.body
        
        for stat in sorted(body, key=attrgetter('port_no')):
            self.port_stat.append(
                {
                    'dpid': ev.msg.datapath.id,
                    'port': stat.port_no,
                    'rx_packet': stat.rx_packets,
                    'rx_byte:': stat.rx_bytes,
                    'rx_error': stat.rx_errors,
                    'tx_packet': stat.tx_packets,
                    'tx_byte': stat.tx_bytes,
                    'tx_error': stat.tx_errors
                }
            )
        self.port_stat.sort(key=lambda x: x['dpid'])
    
    '''
        Network additional statistic
    '''
    def _network_phaser(self):
        hosts_dict = [host.to_dict() for host in self.hosts]
        links_dict = [link.to_dict() for link in self.links]
        switches_dict = [switch.to_dict() for switch in self.switches]
        
        links = []
        for link in links_dict:
            links.append({
                'src_dpid': int(link['src']['dpid'], 16),
                'src_name': link['src']['name'],
                'src_port': int(link['src']['port_no']),
                
                'dst_dpid': int(link['dst']['dpid'], 16),
                'dst_name': link['dst']['name'],
                'dst_port': int(link['dst']['port_no']),
            })
        
        switches = []
        for switch in switches_dict:
            switches.append({
                'dpid': switch['dpid'],
            })
    
        hosts = [host['mac'] for host in hosts_dict]
        # for hosts in hosts_dict:
        return hosts, switches, links

    '''
        Packet loss:
            - By flow statistic
            - By port statistic
    '''
    def link_flow_packet_loss(self):
        hosts, _, links = self._network_phaser()
        links_packet_loss = []
        for host in hosts:
            for link in links:
                tx_packet = None
                for stat in self.flow_stat:
                    if stat['eth_dst'] == host:
                        
                        if stat['out_port'] == link['src_port'] and stat['dpid'] == link['src_dpid']:
                            tx_packet = stat['packet']

                        if stat['in_port'] == link['dst_port'] and stat['dpid'] == link['dst_dpid'] and tx_packet != None:
                            rx_packet = stat['packet']
                            if tx_packet != 0:
                                packet_loss = (tx_packet - rx_packet) / tx_packet
                                # if packet_loss < 0: packet_loss = 0
                                links_packet_loss.append({
                                    'src_dpid': link['src_dpid'],
                                    'src_port': link['src_port'],
                                    'dst_dpid': link['dst_dpid'],
                                    'dst_port': link['dst_port'],
                                    'packet_loss': packet_loss,
                                    'throughput': rx_packet / MONITOR_INTERVAL
                                })
                            break
        return links_packet_loss

    def link_port_packet_loss(self):
        _, _, links = self._network_phaser()
        links_packet_loss = []
        for link in links:
            for stat in self.port_stat:
                if stat['dpid'] == link['src_dpid'] and stat['port'] == link['src_port']:         
                    tx_packet = stat['tx_packet']
  
                if stat['dpid'] == link['dst_dpid'] and stat['port'] == link['dst_port']:
                    rx_packet = stat['rx_packet']
                    if tx_packet != 0:
                        packet_loss = (tx_packet - rx_packet) / tx_packet
                        # if packet_loss < 0: packet_loss = 0
                        links_packet_loss.append({
                            'src_dpid': link['src_dpid'],
                            'src_port': link['src_port'],
                            'dst_dpid': link['dst_dpid'],
                            'dst_port': link['dst_port'],
                            'packet_loss': packet_loss,
                            'throughput': rx_packet / MONITOR_INTERVAL
                        })
        return links_packet_loss
    
    def _link_utilization(self):
        pass
    
    def _link_bandwidth(self):
        pass
    
    def _link_delay(self):
        pass

    def _network_statistic(self):
        pass
    
    # Topology Part:
    def get_topology_data(self):
        hosts: list[Host] = get_host(self.topology_api_app, None)
        switches: list[Switch] = get_switch(self.topology_api_app, None)
        links: list[Link] = get_link(self.topology_api_app, None)
        
        self.hosts = sorted(hosts, key=lambda x: x.port.dpid)
        self.switches = sorted(switches, key=lambda x: x.dp.id)
        self.links = sorted(links, key=lambda x: (x.src.dpid, x.dst.dpid))
        return self.hosts, self.switches, self.links
    
class TrafficMonitorRest(ControllerBase):
    def __init__(self, req, link, data, **config):
        super().__init__(req, link, data, **config)
        self.data = data
        self.app: TrafficMonitor = data[APP_NAME]
    
    @route(APP_NAME, '/topology_data', methods=['GET'])
    def get_topology_data(self, req, **_kwargs):        
        hosts, switches, links,  = self.app.get_topology_data() 
        hosts_dict = [host.to_dict() for host in hosts]
        links_dict = [link.to_dict() for link in links]
        switches_dict = [switch.to_dict() for switch in switches]

        topo = [{'host': hosts_dict, 'switch': switches_dict, 'link': links_dict}]
        body = json.dumps(topo)
        return Response(content_type='application/json', body=body)
    
    @route(APP_NAME, '/port_stat', methods=['GET'])
    def get_port_stats(self, req, **kwargs):
        body = json.dumps(self.app.port_stat)
        return Response(content_type='application/json', body=body)

    @route(APP_NAME, '/flow_stat', methods=['GET'])
    def get_flow_stats(self, req, **kwargs):
        body = json.dumps(self.app.flow_stat)
        return Response(content_type='application/json', body=body)

    @route(APP_NAME, '/network_stat_port', methods=['GET'])
    def get_network_stats_port(self, req, **kwargs):
        body = json.dumps(self.app.link_port_packet_loss())
        return Response(content_type='application/json', body=body)
    
    @route(APP_NAME, '/network_stat_flow', methods=['GET'])
    def get_network_stats_flow(self, req, **kwargs):
        body = json.dumps(self.app.link_flow_packet_loss())
        return Response(content_type='application/json', body=body)
    
    @route(APP_NAME, '/add_flow', methods=['POST'], requirements=None)
    def add_flow(self, req, **kwargs):
        body = req.json
        # self.app.add_flow(body)
        # return Response(status=200)