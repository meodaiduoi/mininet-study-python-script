from ryu.base import app_manager
from ryu.ofproto import ofproto_v1_3

# REST API
import json
from ryu.app.wsgi import WSGIApplication, ControllerBase, Response, route
from ryu.lib import dpid as dpid_lib

APP_NAME = 'BaseRest'

class BaseWsgiApp(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]
    _CONTEXTS = {'wsgi': WSGIApplication}

    def __init__(self, *args, **kwargs):
        super(BaseWsgiApp, self).__init__(*args, **kwargs)
        wsgi: WSGIApplication = kwargs['wsgi']
        wsgi.register(BaseRest, {APP_NAME: self})
    
class BaseRest(ControllerBase):
    def __init__(self, req, link, data, **config):
        super().__init__(req, link, data, **config)
        self.data = data
    
    @route(APP_NAME, '/status', methods=['GET'], requirements=None)
    def getStatus(self, req, **kwargs):
        body = json.dumps({"status": "OK - Hello Handsome Dude"})
        return Response(content_type='application/json', body=body)