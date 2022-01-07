from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import set_ev_cls, CONFIG_DISPATCHER, MAIN_DISPATCHER, DEAD_DISPATCHER

from ryu.ofproto import ofproto_v1_3, ofproto_v1_3_parser
from ryu.ofproto.ofproto_parser import MsgBase
from ryu.controller.controller import Datapath

from ryu.lib.packet import packet, ethernet

class BaseController13(app_manager.RyuApp):
    
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]
    
    def __init__(self, *args, **kwargs):
        super(BaseController13, self).__init__(*args, **kwargs)
        self.mac_to_port = {}
        
    def add_flow(self, datapath: Datapath, priority, match, actions, buffer_id=None):
        # msg      : the information of packet-in (including switch, in_port number, etc.)
        # datapath : the switch in the topology using OpenFlow
        # ofproto  : get the protocol using in the switch
        # parser   : get the communication between switch and Ryu controller
        # inst     : the instruction that need to be executed
        # mod      : the flow-entry that need to add into the switch
        # cookie(0): An optional value specified by the controller and can be used as a filter condition when updating or deleting entries. This is not used for packet processing.
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
        
    
    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def _packet_in_handler(self, ev):
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
            self.add_flow(datapath, 1, match, actions)

        # construct packet_out message and send it.
        out = parser.OFPPacketOut(datapath=datapath,
                                  buffer_id=ofproto.OFP_NO_BUFFER,
                                  in_port=in_port, actions=actions,
                                  data=msg.data)
        datapath.send_msg(out)
        
        
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
        self.add_flow(datapath, 0, match, actions)
        
