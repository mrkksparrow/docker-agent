#$Id$
'''
Created on Feb 17, 2015

@author: root
'''


import json
from time import time
from six.moves.urllib.error import URLError
from six.moves.urllib.parse import urlencode
from six.moves.urllib.request import OpenerDirector, Request


from com.manageengine.monagent.logger import AgentLogger
from com.manageengine.monagent.docker_old.UnixConn import UnixConnectionHandler, UnixHTTPConnection
from com.manageengine.monagent.docker_old import DockUtils


DOCKER_DEFAULT_TIME_OUT = 10
DOCKER_DEFAULT_VERSION = 1.16
DOCKER_DEFAULT_BASE_URL = "unix://var/run/docker.sock"

class DockerRemoteAPI:
    
    def __init__(self, base_url = DOCKER_DEFAULT_BASE_URL, timeout = DOCKER_DEFAULT_TIME_OUT):

        self.base_url = DockUtils.parseUrl(base_url)
        self._timeout = timeout
        self.url_opener = OpenerDirector()
        UnixHTTPConnection.sock_timeout = self._timeout
        self.url_opener.add_handler(UnixConnectionHandler())
        version = self._dockerApiVersion()
        self._version = DOCKER_DEFAULT_VERSION if version is None else version
     
     
    
    def getApiVersion(self):
        return self._version
    
    def containers(self, all_cont = False, since = None, before = None, size = False, 
                   limit = 0, only_id = False):
        params = {
            'all'   : 1 if all_cont else 0,
            'size'  : 1 if size else 0,
            'limit' : limit
        }
        if since :
            params['since'] = since
        if before :
            params['before'] = before
        result = self._getResult(self._doGet(self._url("/containers/json"), params = params), True)
        if only_id :
            return [x['Id'] for x in result]
        return result   
    
    
    def events(self, since = int(time() - 300), until = int(time())):
        params = {
            'since' : since,
            'until' : until
        }
        return self._streamData(self._doGet(self._url("/events"), params = params, stream = True))
        
    def images(self, all_image = False):
        params = {
            'all' : 1 if all_image else 0
        }
        result = self._getResult(self._doGet(self._url("/images/json"), params = params), True)
        return result
        
    def imageHistory(self, uid):
        res = self._getResult(self._doGet(self._url("/images/{0}/history".format(uid))), True)
        #self._imageErrorMsg(uid, res) 
        return res
    
    def inspectContainer(self, cont_id):
        res = self._getResult( self._doGet(self._url("/containers/{0}/json".format(cont_id))), True)
        AgentLogger.debug(AgentLogger.STDOUT,'container data ---> {0}'.format(res))
        #self._containeErrorMsg(cont_id, res) 
        return res
    
    def inspectImage(self, image_id):
        return self._getResult( self._doGet(self._url("/images/{0}/json".format(image_id))), True)
           
    def killContainer(self, cont_id, signal = None):
        params = {}
        if signal :
            params['signal'] = signal
            
        res = self._doPost(self._url("/containers/{0}/kill".format(cont_id)), params=params)

        return res
    
    def pauseContainer(self, cont_id):
        
        res = self._doPost(self._url("/containers/{0}/pause".format(cont_id)))
        return res
    
    def processInContainer(self, cont_id, arg = None):
        params = {}
        if arg :
            params["ps_args"] = arg
            
        res = self._getResult( self._doGet(self._url("/containers/{0}/top".format(cont_id)), params = params), True)
        return res
    
    def removeContainer(self, cont_id, v = False, force = False):
        params = {
            'v'     : v,
            'force' :force
        }
        res  = self._doDelete(self._url('/containers/{0}'.format(cont_id)), params = params)
        return res
    
    def restartContainer(self, cont_id, timeout = 2):
        params = {
            't': timeout
        }
        res = self._doPost(self._url("/containers/{0}/restart".format(cont_id)), params=params)
        return res
    
    def startContainer(self, cont_id, binds = None, links = None, lxc_conf = None, port_bindings = None,
                        publish_all_ports = False, previleged = False, dns = None, dns_search = None,
                        volume_from = None, cap_add = None, cap_drop = None, restart_policy = None,
                        network_mode = None, devices = None ):
        ''' following are parameter details :
        
        cont_id           : Container Id
        binds             : A list of volume bindings for this container
                            format must be : 
                            ['/container_volume_path']                       : To create a volume inside container
                            ['/host_path:/container_path']     : to bind-mount a host path into the container
                            ['/host_path:/container_path:ro']  : to make the bind-mount read-only inside the container
                            ['/host_path:/container_path:rw']  : to make the bind-mount read-write inside the container
        links             : A list of links for the container. Each link entry should be of of the form "container_name:alias"
        lxc_conf          : A Dict for Lxc specific configuration Example : {"lxc.utsname":"docker"}
        publish_all_ports :
        '''
        config = {}
        if binds :
            if isinstance(binds, list):
                config["Binds"] = binds
        if links :
            if isinstance(links, list):
                config["Links"] = links
        if lxc_conf :
            if isinstance(lxc_conf, dict) :
                config["LxcConf"] = lxc_conf
        if port_bindings:
            config["PortBindings"] = DockUtils.convertPortBinds(port_bindings)
        
        config["PublishAllPorts"] = publish_all_ports
        config["Privileged"] =  previleged
        if dns:
            config["Dns"] = dns
        if dns_search :
            config["DnsSearch"] = dns_search
        if volume_from and isinstance(volume_from, list) :
            config["VolumesFrom"] = volume_from  
        if cap_add :
            config["CapAdd"] = cap_add
        if cap_drop :
            config["CapDrop"] = cap_drop
        if restart_policy and isinstance(restart_policy, dict) :
            config["RestartPolicy"] = restart_policy
        if network_mode :
            config["NetworkMode"] = network_mode
        if devices and isinstance(devices, list):
            config["Devices"] = DockUtils.parseDevices(devices)
        
        resp = self._postJson(self._url("/containers/{0}/start".format(cont_id)), data = config)
        return resp
    def statsContainer(self, cont_id):
        res = self._streamData(self._doGet(self._url("/containers/{0}/stats".format(cont_id)), stream = True), True)
        AgentLogger.debug(AgentLogger.STDOUT,' container stats ---> {0}'.format(res))
        return res
    
    def stopContainer(self, cont_id, timeout = 2):
        params = {
            't': timeout
        }
        resp = self._doPost(self._url("/containers/{0}/stop".format(cont_id)), params=params)
        return resp
    
    def unpauseContainer(self, cont_id):
        
        res = self._doPost(self._url("/containers/{0}/unpause".format(cont_id)))
        return res
        
    def version_info(self):
        
        res = self._getResult(self._doGet(self._url("/version")), True)
        return res 
        
    def _imageErrorMsg(self, image_id, res):
        if res and isinstance(res, dict):
            if 'RespStatus' in res :
                if res['RespStatus'] == 404:
                    AgentLogger.log(AgentLogger.COLLECTOR, "DOCKER_LOG: " + "{0} : image does not exist ".format(image_id))
        
    def _containeErrorMsg(self, cont_id, res):
        if res and isinstance(res, dict):
            if 'RespStatus' in res :
                if res['RespStatus'] == 304:
                    AgentLogger.log(AgentLogger.COLLECTOR, "DOCKER_LOG: " + "{0} : Container Already Stopped/started ".format(cont_id))
                elif res['RespStatus'] == 404:
                    AgentLogger.log(AgentLogger.COLLECTOR, "DOCKER_LOG: " + "{0} : Container does not exist ".format(cont_id))
        
    def _dockerApiVersion(self):
        res = self.version_info()
        if "ApiVersion" in res:
            return res['ApiVersion']
        
    def _streamData(self, resp, one_line = False):
        if not resp :
            return None
        try :
            data = bytes()
            if resp.status == 200 :
                data_part = resp.readline()
                if one_line :
                    data = data + data_part
                else :
                    while data_part:
                        data = data + data_part
                        data_part = resp.readline()#()#.read(1)
                
                data = data.decode('utf-8')
                
                if not data : 
                    data = "[]"
                elif "}{" in data :
                    data = "[{0}]".format(data.replace("}{", "},{"))
                elif not one_line :
                    data = "[{0}]".format(data)
                return json.loads(data)
        except Exception as e :
            AgentLogger.log(AgentLogger.COLLECTOR, "DOCKER_LOG: " + "Error in stream data : {0}".format(e))
            
            
    def _stream_helper(self, response):
        """Generator for data coming from a chunked-encoded HTTP response."""
        if not response :
            return None
        try:
            socket_fp = response.fp.raw._sock
        except AttributeError:
            AgentLogger.log(AgentLogger.COLLECTOR, "Attribute Error")
            return None
        socket_fp.setblocking(1)
        socket = socket_fp.makefile()
        while True:
            
            size_line = socket.readline()
            if size_line == '\r\n' or size_line == '\n':
                size_line = socket.readline()

            if len(size_line.strip()) > 0:
                size = int(size_line, 16)
            else:
                break

            if size <= 0:
                break
            data = socket.readline()
            if not data:
                break
            #yield data
            
    def _getResult(self, resp, json_resp = False, bin_resp = False):
        assert not (json_resp and bin_resp)
        try :
            if resp.status == 200 or resp.status == 201 or resp.status == 204:
                data = resp.read()
                data_str = data.decode("utf-8")
                if json_resp:
                    return json.loads(data_str)
                if bin_resp :
                    return data
                return data_str
            elif resp.status == 400:
                AgentLogger.log(AgentLogger.COLLECTOR, "DOCKER_LOG: " + "Bad Parameter : Please Correct")
            elif resp.status == 500:
                AgentLogger.log(AgentLogger.COLLECTOR, "DOCKER_LOG: " + "Server Error")
            elif resp.status == 999:
                AgentLogger.log(AgentLogger.COLLECTOR, "DOCKER_LOG: " + "Unknown Status Code")
            else :
                AgentLogger.log(AgentLogger.COLLECTOR, "DOCKER_LOG: " + "Unknown Status Code")
            
            retStatus = '{"RespStatus" :' + str(resp.status) + '}'
            return json.loads(retStatus)
        
        except Exception as e :
            AgentLogger.log(AgentLogger.COLLECTOR, "DOCKER_LOG: " + "Error in unix Response: {0}".format(e))
        
    def _postJson(self, url, data, **kwargs):
        '''Remove item from the dict whose value is None : serialization problem'''
        parsed_data = {}
        if data is not None :
            for key, val in data.items():
                if val is not None :
                    parsed_data[key] = val
        
        json_data = json.dumps(parsed_data)
        if 'headers' not in kwargs :
            kwargs['headers'] = {}
        kwargs['headers']['Content-Type'] = 'application/json'
        
        return self._doPost(url, json_data, **kwargs)
        
    def _doDelete(self, url, **kwargs):  
        ''' used for post request for docker daemon'''
        
        return self._do(url, method = "DELETE",  **kwargs) 
    
    def _doPost(self, url, data = None, **kwargs):  
        ''' used for post request for docker daemon'''
        
        return self._do(url, data=data, method = "POST",  **kwargs) 

    def _doGet(self, url, **kwargs):
        ''' return string data got as a response'''
        return self._do(url, **kwargs)

    def _url(self, path):
        ''' Forming full URL from base URL and path'''
        
        return "{0}{1}".format(self.base_url, path)  
    
    def _do(self, url, data = None, method = "GET",  **kwargs):
        ''' Function will be called by _do_get and _do_post 
        
        this eventually call unix_open and unix_response to get response from docker'''
        
        resp = None
        try:
            #Getting argument from kwargs
            params = kwargs.get("params", {}) 
            if params :
                url = "{0}?{1}".format(url, urlencode(params)) # if params has data build full url 
            headers = kwargs.get("headers", {})
                           
            req = Request(url, data, headers, method=method ) # build Request object
            
            stream = kwargs.get('stream', False)
            req.add_header('Stream', stream)
            
            resp = self.url_opener.open(req) # get response from server
            if resp == None or resp == "" :
                return Response()
        except URLError as ue :
            AgentLogger.log(AgentLogger.COLLECTOR, "DOCKER_LOG: " + "Unable to connect to socket, User must be a part of docker group {0}". format(ue))
        except Exception as te:
            AgentLogger.log(AgentLogger.COLLECTOR, "DOCKER_LOG: " + "Time out occured {0}".format(te))
        return resp


class Response:
    def __init__(self):
        self.status = 999
