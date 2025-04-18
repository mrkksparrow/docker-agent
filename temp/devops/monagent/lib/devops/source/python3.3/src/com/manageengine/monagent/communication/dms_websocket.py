# $Id$

from six.moves.urllib.parse import urlencode
import  json, time, ssl,threading
from com.manageengine.monagent.logger import AgentLogger
from com.manageengine.monagent import AgentConstants
from com.manageengine.monagent.util import AgentUtil
import traceback
import com
DMS = None

def initialize():
    global DMS
    AgentLogger.log(AgentLogger.STDOUT,"DMS Initialize block :: {}".format(DMS))
    if not DMS:
        DMS = DMSWsHandler()
        DMS.setDaemon(True)
        DMS.start()

def stop_dms():
    global DMS
    AgentLogger.log(AgentLogger.STDOUT,"DMS Stop block :: {}".format(DMS))
    if DMS:
        DMS.stop()

class DMSWebSocket(AgentConstants.WEBSOCKET_MODULE.WebSocketApp):
    def __init__(self, url, onMessage, onError, onPong, onClose):
        AgentConstants.WEBSOCKET_MODULE.WebSocketApp.__init__(self, url, on_message=onMessage, on_error=onError, on_pong=onPong, on_close=onClose, header={'user-agent': "Sie24x7 Linux Agent"})
        
    def _send_ping(self, interval, event):
        from datetime import datetime
        now = datetime.now()
        current_time = now.strftime("%H:%M:%S")
        while not event.wait(interval):
            self.last_ping_tm = time.time()
            if self.sock:
                try:
                    now = datetime.now()
                    current_time = now.strftime("%H:%M:%S")
                    self.sock.ping("-")
                except Exception as ex:
                    AgentLogger.log(AgentLogger.STDOUT,"web socket ping failure :: {}".format(ex))
                    break

class DMSWsHandler(threading.Thread):
    __ws = None
    __url = ""
    __sid = None    
    __uid = None    
    __zuid = None
    __agentid = None
    __prdid = None
    __devicekey = None
    __session_reconnect_time = None
    __retry_count = 0
    __disable_dms = False
    host = AgentConstants.DMS_PRIMARY_WS_HOST
    re_connect_interval = 1500 #in sec
    temp_ddos_retry_interval = 60 #in sec
    ack_code = 0
    reconnect_switch_code = -1
    reconnect_session_code = -11
    auth_failed_code = -5
    message_code = 650
    device_empty_code = -2
    ddos_code = 660

    def __init__(self):
        AgentLogger.log(AgentLogger.STDOUT,"initializing new dms connection")
        threading.Thread.__init__(self)
        self.name = 'DMS-WebSocket'
        self.__agentid = AgentUtil.AGENT_CONFIG.get('AGENT_INFO', 'agent_key')
        self.__prdid = AgentConstants.DMS_PRODUCT_CODE
        self.__devicekey = AgentConstants.CUSTOMER_ID
        
    def stop(self):
        self.__disable_dms = True
        self.close_connection()
    
    def run(self):
        try:
           self.initiate_connection()  
        except Exception as e:
            traceback.print_exc()
    
    @staticmethod
    def get_wms_server():
        return "wss://" + DMSWsHandler.host + "/wsconnect"

    def initiate_connection(self):
        req_params = {}
        req_params['prd'] = self.__prdid
        req_params['zuid'] = self.__agentid
        req_params['key'] = self.__devicekey
        req_params['config'] = 16
        req_params['authtype'] = 6
        req_params_encoded = urlencode(req_params)
        AgentLogger.log(AgentLogger.STDOUT,"DMS Connect :: prd :: " + req_params['prd'] +"  host :: " + DMSWsHandler.get_wms_server() + " agentid :: " + req_params['zuid'])
        self.__url = DMSWsHandler.get_wms_server() + "?" + req_params_encoded
        self.connect()

    def reconnect(self):
        if self.__sid != None:
            try:
                req_params = {}
                req_params['c'] = self.__uid
                req_params['i'] = self.__sid
                req_params['key'] = self.__devicekey
                AgentLogger.log(AgentLogger.STDOUT,"DMS ReConnect :: c :: " + self.__uid +"  i :: " + self.__sid)
                req_params_encoded = urlencode(req_params)
                self.__url = DMSWsHandler.get_wms_server() + "?" + req_params_encoded
                self.connect()
            except Exception as e:
                traceback.print_exc()
                AgentLogger.log(AgentLogger.STDOUT,"Exception while reconnecting")
        else:
            AgentLogger.log(AgentLogger.STDOUT,"Reconnect Session ID is empty could not connect dms service")

    def close_connection(self):
        try:
            AgentLogger.log(AgentLogger.STDOUT,"Closing WebSocket DMS connection")
            self.__ws.close()
        except Exception as e:
            AgentLogger.log(AgentLogger.STDOUT,"Exception while closing dms connection")

    def connect(self):
        try:
            ssl_opt={'cert_reqs':ssl.CERT_REQUIRED,'ca_certs':certifi.where()}
            self.__ws = DMSWebSocket(self.__url, self.on_message, self.on_error, self.on_pong, self.on_close)
            self.__ws.run_forever(ping_interval=25,sslopt=ssl_opt)
            AgentLogger.log(AgentLogger.STDOUT,"Web Socket DMS Connection Closed")
            if not self.__disable_dms:
                self.__retry_count+=1
                if self.__retry_count %2 != 0:
                    DMSWsHandler.host = AgentConstants.DMS_SECONDARY_WS_HOST
                else:
                    DMSWsHandler.host = AgentConstants.DMS_PRIMARY_WS_HOST
                AgentLogger.log(AgentLogger.STDOUT,"DMS Retry host :: {}".format(DMSWsHandler.host))
                self.retry_connection(DMSWsHandler.temp_ddos_retry_interval)
        except AgentConstants.WEBSOCKET_MODULE.WebSocketException as we:
            AgentLogger.log(AgentLogger.STDOUT,"WebSocket Exception occurred during dms connection :: {}".format(we))
            traceback.print_exc()
        except Exception as e:
            traceback.print_exc()
            AgentLogger.log(AgentLogger.STDOUT,"Exception occurred during dms connection :: {}".format(e))

    def set_reconnect_params(self, msg):
        try:
            details = msg['msg']
            self.__sid = details.get("sid")
            self.__uid = details.get("uid")
            self.__session_reconnect_time = time.time()
            AgentLogger.log(AgentLogger.STDOUT,"DMS connection successfully established ::: {} :: {}".format(self.__sid,self.__uid))
        except Exception as e:
            AgentLogger.log(AgentLogger.STDOUT,"Exception occurred while dms reconnect :: {}".format(e))
            traceback.print_exc()
    
    def switch_dc(self,msg):
        try:
            new_primary_dc = msg.get("primarydc")
            new_primary_dc_host = msg.get(new_primary_dc).strip()
            AgentLogger.log(AgentLogger.STDOUT,"dc switch :: new primary ::" +  str(new_primary_dc_host))
            DMSWsHandler.host = new_primary_dc_host
            self.initiate_connection()
        except Exception as e:
            AgentLogger.log(AgentLogger.STDOUT,"Exception occurred while dms : dc switch :: {}".format(e))
    
    def handle_ddos(self, msg):
        try:
            if msg['b'] == "temporary":
                self.retry_connection(DMSWsHandler.temp_ddos_retry_interval)
            elif msg['b'] == "permanent":
                self.__disable_dms = True
                self.close_connection()
        except Exception as e:
            AgentLogger.log(AgentLogger.STDOUT,"Exception occurred while handling ddos action :: {}".format(e))
            traceback.print_exc()
    
    def on_message(self,message=""):
        try:
            if message:
                arr = json.loads(message)
                AgentLogger.debug(AgentLogger.STDOUT,"DMS Acknowledgement :: " + str(arr))
                for message_from_dms in arr:
                    mtype = int(message_from_dms['mtype'])
                    if mtype == DMSWsHandler.ack_code:
                        AgentLogger.log(AgentLogger.STDOUT,"DMS event :: registration success :: " + str(message_from_dms))
                        self.set_reconnect_params(message_from_dms)
                    elif mtype == DMSWsHandler.reconnect_session_code:
                        AgentLogger.log(AgentLogger.STDOUT,"DMS event :: reconnect :: " + str(message_from_dms))
                        self.reconnect()
                    elif mtype == DMSWsHandler.reconnect_switch_code:
                        AgentLogger.log(AgentLogger.STDOUT,"DMS event :: switch dc:: " + str(message_from_dms))
                        self.switch_dc(message_from_dms)
                    elif mtype == DMSWsHandler.auth_failed_code:
                        AgentLogger.log(AgentLogger.STDOUT,"DMS event :: Authentication Failure :: " + str(message_from_dms))
                        self.__disable_dms = True
                        self.close_connection()
                    elif mtype == DMSWsHandler.device_empty_code:
                        AgentLogger.log(AgentLogger.STDOUT,"DMS event :: Device Key Empty :: " + str(message_from_dms))
                        self.__disable_dms = True
                        self.close_connection()
                    elif mtype == DMSWsHandler.message_code:
                        msg = message_from_dms['msg']
                        data = msg['data']
                        content = data['content']
                        if type(content) is not dict:
                            requestList = json.loads(content, 'UTF-8')['RequestList']
                        else:
                            requestList = content['RequestList']
                        com.manageengine.monagent.communication.DMSHandler.processTasks(requestList)
                    elif mtype == DMSWsHandler.ddos_code:
                        AgentLogger.log(AgentLogger.STDOUT,"WMS event :: DDOS :: " + str(message_from_dms))
                        self.handle_ddos(message_from_dms)
            else:
                self.check_for_reconnection()
        except Exception as e:
            AgentLogger.log(AgentLogger.STDOUT,"Exception while receiving dms message :: {}".format(e))

    def on_error(self,error=None):
        if error is not None:
            AgentLogger.log(AgentLogger.STDOUT,"Error occurred while processing dms connection :: " + str(error))

    def on_close(self, ws=None):
        try:
            AgentLogger.log(AgentLogger.STDOUT,"Connection close handler :: {}".format(ws))
            self.__ws.close()
            AgentLogger.log(AgentLogger.STDOUT,"Connection has been closed by DMS server for agent id  :: " + str(self.__agentid) + " session id :: " + str(self.__sid))
        except Exception as e:
            AgentLogger.log(AgentLogger.STDOUT,"Exception occurred during on close callback :: {}".format(e))
            traceback.print_exc()

    def on_pong(self, data=None):
        try:
            AgentLogger.debug(AgentLogger.STDOUT,"pong received" )
            self.check_for_reconnection()
        except Exception as e:
            AgentLogger.log(AgentLogger.STDOUT,"Exception occurred during on pong callback :: {}".format(e))

    def check_for_reconnection(self):
        if self.__session_reconnect_time is not None:
            if ((time.time() - self.__session_reconnect_time) > DMSWsHandler.re_connect_interval):
                self.__session_reconnect_time = time.time()
                AgentLogger.log(AgentLogger.STDOUT,"web socket session going to expire, session reconnect ::")
                self.reconnect()

    def retry_connection(self, retry_interval):
        time.sleep(retry_interval)
        self.initiate_connection()