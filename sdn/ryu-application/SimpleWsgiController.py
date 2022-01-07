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

APP_NAME = 'SimpleWsgiController'

class SimpleWsgiController(app_manager.RyuApp):

    # Version - Context
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]
    _CONTEXTS = {'wsgi': WSGIApplication}

    def __init__(self, *_args, **_kwargs):
        super(SimpleWsgiController, self).__init__(self, *_args, **_kwargs)

        # Register the WSGI application
        wsgi: WSGIApplication = _kwargs['wsgi']
        wsgi.register(ControllerRestApi, {APP_NAME: self})

        #thread
        self.monitor_thread = hub.spawn(self._monitor)

        self.topology_api_app = self

        # Datapaths
        self.datapaths: Dict[Datapath.id, Datapath] = {}  # Store switch in topology using OpenFlow

        # Topology: hosts, swtiches, links
        self.hosts = {}
        self.switches = {}
        self.links = {}
        self.mac_to_port = {}
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

    '''
    addFlow(self, datapath: Datapath, priority, match, actions, buffer_id=None):

    - Match:
    Bao gồm các thông tin về packet header và ingress port
    dùng để so khớp các gói tin, khi một gói tin match với một flow entry thì gói tin đó
    sẽ được xử lý bằng các hành động đã được định nghĩa trong flow entry đó.

    - Priority:
    Mức độ ưu tiên của flow entry đó. Mỗi gói tin có thể match với nhiều
    flow entry khi đó gói tin sẽ được xử lý bởi flow entry có priority cao hơn.
    '''
    def addFlow(self, datapath: Datapath, priority, match, actions, buffer_id=None):
        # msg      : the information of packet-in (including switch, in_port number, etc.)
        # datapath : the switch in the topology using OpenFlow
        # ofproto  : get the protocol using in the switch
        # parser   : get the communication between switch and Ryu controller
        # inst     : the instruction that need to be executed
        # mod      : the flow-entry that need to add into the switch
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS, actions)]
        mod = parser.OFPFlowMod(
            datapath=datapath,
            priority=priority,
            match=match,
            instructions=inst,
            command=ofproto.OFPFC_ADD,
            idle_timeout=0,
            hard_timeout=0,
            cookie=0)
        datapath.send_msg(mod)

    '''
    Network monitoring:
    '''
    # Create a monitoring thread on each 10 second
    def _monitor(self):
        while True:
            for dp in self.datapaths.values():
                self._requestStats(dp)
            hub.sleep(10)

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

    @set_ev_cls(ofp_event.EventOFPFlowStatsReply, MAIN_DISPATCHER)
    def _flowStatsReplyHandler(self, ev):

        msg: MsgBase = ev.msg
        datapath: Datapath= msg.datapath
        body = msg.body
        flows = []
        
        for stat in sorted([flow for flow in body if flow.priority == 1],
                           key=lambda flow: (flow.match['in_port'],
                                             flow.match['eth_dst'])):
            flows.append(
                {
                    'datapath': datapath.id,
                    'datapath_addr': datapath.address, 
                    'in_port': stat.match['in_port'],
                    'out_port': stat.instructions[0].actions[0].port,
                    'eth_dst': stat.match['eth_dst'],
                    'packet': stat.packet_count,
                    'bytes': stat.byte_count
                }
            )
        self.flow_stat = flows

    # Network statistic
    @set_ev_cls(ofp_event.EventOFPPortStatsReply, MAIN_DISPATCHER)
    def _portStatsReplyHandler(self, ev):

        msg: MsgBase = ev.msg
        body = msg.body

        ports = []
        for stat in sorted(body, key=attrgetter('port_no')):
            ports.append(
                {
                    'datapath': ev.msg.datapath.id,
                    'port': stat.port_no,
                    'recive_packet': stat.rx_packets,
                    'recive_byte:': stat.rx_bytes,
                    'recive_error': stat.rx_errors,
                    'transmit_packet': stat.tx_packets,
                    'transmit_byte': stat.tx_bytes,
                    'transmit_error': stat.tx_errors
                    # 'packet_loss:': ((stat.tx_packets - stat.rx_packets) / (stat.tx_packets))
                }
            )

        self.port_stat = ports

    '''
    Packet-in handler event

    '''
    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def _packetInHandler(self, ev):
        msg: MsgBase = ev.msg
        datapath: Datapath = msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        # get Datapath ID to identify OpenFlow switches.
        dpid = datapath.id
        self.mac_to_port.setdefault(dpid, {})

        # analyse the received packets using the packet library.
        pkt = packet.Packet(msg.data)
        eth_pkt = pkt.get_protocol(ethernet.ethernet)
        dst = eth_pkt.dst
        src = eth_pkt.src

        # get the received port number from packet_in message.
        in_port = msg.match['in_port']

        # Logger
        # self.logger.info("packet in %s %s %s %s", dpid, src, dst, in_port)

        # learn a mac address to avoid FLOOD next time.
        self.mac_to_port[dpid][src] = in_port

        # if the destination mac address is already learned,
        # decide which port to output the packet, otherwise FLOOD.
        if dst in self.mac_to_port[dpid]:
            out_port = self.mac_to_port[dpid][dst]
        else:
            out_port = ofproto.OFPP_FLOOD

        # construct action list.
        actions = [parser.OFPActionOutput(out_port)]

        # install a flow to avoid packet_in next time.
        if out_port != ofproto.OFPP_FLOOD:
            match = parser.OFPMatch(in_port=in_port, eth_dst=dst)
            self.addFlow(datapath, 1, match, actions)

        # construct packet_out message and send it.
        out = parser.OFPPacketOut(datapath=datapath,
                                  buffer_id=ofproto.OFP_NO_BUFFER,
                                  in_port=in_port, actions=actions,
                                  data=msg.data)
        datapath.send_msg(out)

    '''
    Handle state chanege of switch and link

    '''
    @set_ev_cls(ofp_event.EventOFPStateChange, [MAIN_DISPATCHER, DEAD_DISPATCHER])
    def _stateChangeHandler(self, ev):
        datapath: Datapath = ev.datapath
        if ev.state == MAIN_DISPATCHER:
            if datapath.id not in self.datapaths:
                self.logger.debug('register datapath: %016x', datapath.id)
                self.datapaths[datapath.id] = datapath
        elif ev.state == DEAD_DISPATCHER:
            if datapath.id in self.datapaths:
                self.logger.debug('unregister datapath: %016x', datapath.id)
                del self.datapaths[datapath.id]

    '''
    - Context:
    After handshake with the OpenFlow switch is completed, the Table-miss
    flow entry is added to the flow table to get ready to receive the Packet-In message.

    - Table-miss flow entry: https://techhub.hpe.com/eginfolib/networking/docs/switches/5940/5200-1028b_openflow_cg/content/491966856.htm
    Every flow table must support a table-miss flow entry to process table misses. The table-miss
    flow entry specifies how to process packets that were not matched by other flow entries in the flow table.
    The table-miss flow entry wildcards all match fields (all fields omitted) and has the lowest priority 0.
    The table-miss flow entry behaves in most ways like any other flow entry.
    '''
    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def _switch_features_handler(self, ev):
        msg: MsgBase = ev.msg
        datapath: Datapath = msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        # install the table-miss flow entry.
        match = parser.OFPMatch()
        actions = [parser.OFPActionOutput(ofproto.OFPP_CONTROLLER,
                                          ofproto.OFPCML_NO_BUFFER)]
        self.addFlow(datapath, 0, match, actions)

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
        self.app: SimpleWsgiController = data[APP_NAME]

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
    

'''
Thêm số đo thực tế loss.
Add flow
Restful api điều khiển - getSwitch, getLink

NOTE: pingall before get_host and port_stat or flow_stat also net_statistics
SND CONTROLLER only communicate with switch not host. (https://stackoverflow.com/questions/46230905/how-to-send-data-from-ryu-controller-to-host)
'''
