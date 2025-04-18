#$Id$
import traceback
import six.moves.urllib.request as urlconnection
from six.moves.urllib.parse import urlencode
from six.moves.urllib.error import URLError, HTTPError
from com.manageengine.monagent.util.DesignUtils import synchronized
try:
    from http.client import InvalidURL
except Exception as e:
    from httplib import InvalidURL
import json
import socket, errno
import ssl
import sys, os, time
import platform

import com
from com.manageengine.monagent import AgentConstants,AppConstants,module_object_holder
from com.manageengine.monagent.logger import AgentLogger
from com.manageengine.monagent.util import AgentUtil, AgentBuffer,MetricsUtil
from com.manageengine.monagent.security import AgentCrypt
from com.manageengine.monagent.framework.suite.id_guard import Patrol as id_patrol
from com.manageengine.monagent.util.AgentUtil import FileUtil
from com.manageengine.monagent.actions import settings_handler
from com.manageengine.monagent.container import container_monitoring


SERVER_INFO = None
SECONDARY_SERVER_INFO = None
PROXY_INFO = None

SSL_TIMEOUT_ERROR = 'the read operation timed out'

NETWORK_STATUS_CHECK_TIME = time.time()

NETWORK_STATUS_CHECK_URLS = [('www.wikipedia.org', AgentConstants.HTTPS_PROTOCOL, 443, 0),
                             ('www.oracle.com', AgentConstants.HTTP_PROTOCOL, 80, 0),
                             ('www.python.org', AgentConstants.HTTP_PROTOCOL, 80, 0),
                             ('www.google.com', AgentConstants.HTTPS_PROTOCOL, 443, 0),
                             ('www.bing.com', AgentConstants.HTTPS_PROTOCOL, 443, 0),
                             ]

WMS_REQID_SERVED_BUFFER = None

NETWORK_STATUS_CHECK_REACHABLE_URLS = []

def initialize():
    global SERVER_INFO, SECONDARY_SERVER_INFO, PROXY_INFO, WMS_REQID_SERVED_BUFFER
    WMS_REQID_SERVED_BUFFER = AgentBuffer.getBuffer(AgentConstants.WMS_REQID_SERVED_BUFFER,AgentConstants.MAX_WMS_REQID_BUFFER)
    SERVER_INFO = ServerInfo()
    SERVER_INFO.set_host(AgentUtil.AGENT_CONFIG.get('SERVER_INFO', 'server_name'))
    SERVER_INFO.set_port(AgentUtil.AGENT_CONFIG.get('SERVER_INFO', 'server_port'))
    SERVER_INFO.set_protocol(AgentConstants.HTTPS_PROTOCOL)
    SERVER_INFO.set_timeout(AgentUtil.AGENT_CONFIG.get('SERVER_INFO', 'server_timeout'))
    SECONDARY_SERVER_INFO = ServerInfo()
    SECONDARY_SERVER_INFO.set_host(AgentUtil.AGENT_CONFIG.get('SECONDARY_SERVER_INFO', 'server_name'))
    SECONDARY_SERVER_INFO.set_port(AgentUtil.AGENT_CONFIG.get('SECONDARY_SERVER_INFO', 'server_port'))
    SECONDARY_SERVER_INFO.set_protocol(AgentConstants.HTTPS_PROTOCOL)
    SECONDARY_SERVER_INFO.set_timeout(AgentUtil.AGENT_CONFIG.get('SECONDARY_SERVER_INFO', 'server_timeout'))
    updateProxyDetails()
    AgentLogger.log(AgentLogger.MAIN,'========================== SERVER DETAILS ========================== \n')
    AgentLogger.log(AgentLogger.MAIN,'SERVER INFO : '+str(SERVER_INFO)+'\n SECONDARY SERVER INFO : '+str(SECONDARY_SERVER_INFO)+'\n ')
    AgentLogger.debug(AgentLogger.MAIN,'PROXY INFO : '+str(PROXY_INFO)+'\n')
        
def updateProxyDetails():
    bool_toReturn = True
    agent_restart = False
    AgentLogger.debug(AgentLogger.STDOUT,'installer arguments -- {0}'.format(len(sys.argv)))
    if len(sys.argv) < 2:
        agent_restart = True
    str_proxyUserName = AgentUtil.AGENT_CONFIG.get('PROXY_INFO', 'proxy_user_name')
    str_proxyHost = AgentUtil.AGENT_CONFIG.get('PROXY_INFO', 'proxy_server_name')
    str_proxyPort = AgentUtil.AGENT_CONFIG.get('PROXY_INFO', 'proxy_server_port')
    if AgentUtil.AGENT_CONFIG.has_option('PROXY_INFO','proxy_password'):
        str_proxyPassword = AgentUtil.AGENT_CONFIG.get('PROXY_INFO', 'proxy_password')
        if agent_restart==True:
            if str_proxyPassword!='0':
                if AgentConstants.CRYPTO_MODULE:
                    str_proxyPassword = AgentCrypt.encrypt_with_proxy_key(str_proxyPassword)
                AgentLogger.debug(AgentLogger.STDOUT,'agent service restarts and change in proxy password /-- {0}'.format(str_proxyPassword))
    if AgentUtil.AGENT_CONFIG.has_option('PROXY_INFO','encrypted_proxy_password'):
        str_proxyPassword = AgentUtil.AGENT_CONFIG.get('PROXY_INFO', 'encrypted_proxy_password')
        AgentLogger.debug(AgentLogger.STDOUT,'proxy password -- {0}'.format(str_proxyPassword))
    try:
        # returns a tuple
        def splitStringOnLastIndex(strToSplit, str_delimiter):
            if str_delimiter in strToSplit:
                int_index = strToSplit.rindex(str_delimiter)
                return (strToSplit[:int_index], strToSplit[int_index+1:])
        # returns a tuple
        def splitString(strToSplit, str_delimiter):
            if str_delimiter in strToSplit:
                int_index = strToSplit.index(str_delimiter)
                return (strToSplit[:int_index], strToSplit[int_index+1:])
        #AgentLogger.log(AgentLogger.STDOUT,'Input arguments :'+ repr(sys.argv))
        str_proxyDetails = ''
        if len(sys.argv) >= 2:
            str_proxyDetails = sys.argv[1]
        if AgentConstants.IS_DOCKER_AGENT == "1":
            if os.environ and 'proxy' in os.environ:
                str_proxyDetails = os.environ['proxy']
            if os.environ and 'http_proxy' in os.environ:
                str_proxyDetails = os.environ['http_proxy'].replace('http://','')
            if os.environ and 'https_proxy' in os.environ:
                str_proxyDetails = os.environ['https_proxy'].replace('http://','')
        AgentLogger.debug(AgentLogger.STDOUT,'proxy info ::: {}'.format(str_proxyDetails)) 
        if '@' in str_proxyDetails:
            str_authDetails, str_proxyHostDetails = splitStringOnLastIndex(str_proxyDetails, '@')
            if ':' in str_authDetails:
                str_proxyUserName, str_proxyPassword = splitString(str_authDetails, ':')
                str_proxyPassword = str_proxyPassword if AgentConstants.CRYPTO_MODULE == None else AgentCrypt.encrypt_with_proxy_key(str_proxyPassword)
            else:
                str_proxyUserName = str_authDetails
                str_proxyPassword = '0'
            if ':' in str_proxyHostDetails:
                str_proxyHost, str_proxyPort = splitString(str_proxyHostDetails, ':')
        elif ':' in str_proxyDetails:
            str_proxyUserName = '0'
            str_proxyPassword = '0'
            str_proxyHost, str_proxyPort = splitString(str_proxyDetails, ':')
        if str_proxyPassword and not str_proxyPassword == '0':
            AgentLogger.debug(AgentLogger.COLLECTOR,'Proxy Password  :::'+ repr(str_proxyPassword))
        AgentUtil.AGENT_CONFIG.set('PROXY_INFO', 'proxy_server_name', str(str_proxyHost))
        AgentUtil.AGENT_CONFIG.set('PROXY_INFO', 'proxy_server_port', str(str_proxyPort))
        AgentUtil.AGENT_CONFIG.set('PROXY_INFO', 'proxy_user_name', str(str_proxyUserName))
        if AgentConstants.CRYPTO_MODULE:
            if str_proxyPassword!='0':
                if AgentUtil.AGENT_CONFIG.has_option('PROXY_INFO','proxy_password'):
                    AgentUtil.AGENT_CONFIG.remove_option('PROXY_INFO', 'proxy_password')    
                AgentUtil.AGENT_CONFIG.set('PROXY_INFO', 'encrypted_proxy_password', str(str_proxyPassword))
        else:
            AgentUtil.AGENT_CONFIG.set('PROXY_INFO', 'proxy_password', str(str_proxyPassword))
        AgentUtil.persistAgentInfo()
        setProxy(str_proxyPassword)
    except Exception as e:
        AgentLogger.log(AgentLogger.MAIN,' ************************* Exception while creating proxy profile ************************* '+ repr(e) + '\n')
        traceback.print_exc()
        bool_toReturn = False
    return bool_toReturn
    
def setProxy(str_proxyPassword):
    global PROXY_INFO
    if not AgentUtil.AGENT_CONFIG.get('PROXY_INFO', 'proxy_server_name') == '0':
        PROXY_INFO = ProxyInfo()
        PROXY_INFO.set_host(AgentUtil.AGENT_CONFIG.get('PROXY_INFO', 'proxy_server_name'))
        PROXY_INFO.set_port(AgentUtil.AGENT_CONFIG.get('PROXY_INFO', 'proxy_server_port'))
        if AgentUtil.AGENT_CONFIG.get('PROXY_INFO', 'proxy_server_protocol') != '0':
            PROXY_INFO.set_protocol(AgentUtil.AGENT_CONFIG.get('PROXY_INFO', 'proxy_server_protocol'))
        else:
            PROXY_INFO.set_protocol(AgentConstants.HTTP_PROTOCOL)
        PROXY_INFO.set_username(AgentUtil.AGENT_CONFIG.get('PROXY_INFO', 'proxy_user_name'))
        if str_proxyPassword!='0' and AgentConstants.CRYPTO_MODULE:
            PROXY_INFO.set_password(AgentUtil.AGENT_CONFIG.get('PROXY_INFO', 'encrypted_proxy_password'))
        else:
            PROXY_INFO.set_password(AgentUtil.AGENT_CONFIG.get('PROXY_INFO', 'proxy_password'))
            
def pingServer(str_loggerName = AgentLogger.STDOUT):
    hostIpAddress = None
    sockConn = None
    isSuccess = True
    try:
        AgentLogger.log([str_loggerName],'========================== GET IP USING PING ==========================\n')
        AgentLogger.log(str_loggerName,'PING: Trying To Reach The Server : '+AgentUtil.AGENT_CONFIG.get('SERVER_INFO', 'server_name')+' : '+AgentUtil.AGENT_CONFIG.get('SERVER_INFO', 'server_port'))
        sockConn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)    
        sockConn.settimeout(5)
        connectResult = sockConn.connect_ex((AgentUtil.AGENT_CONFIG.get('SERVER_INFO', 'server_name'), int(AgentUtil.AGENT_CONFIG.get('SERVER_INFO', 'server_port'))))
        if connectResult == 0:
            AgentLogger.log(str_loggerName,'PING: Established Connection To The Server : '+AgentUtil.AGENT_CONFIG.get('SERVER_INFO', 'server_name')+' : '+AgentUtil.AGENT_CONFIG.get('SERVER_INFO', 'server_port'))
            AgentLogger.log(str_loggerName,'PING: Socket Used For Communicating With The Server : '+repr(sockConn.getsockname()))
            hostIpAddress = sockConn.getsockname()[0]
        else:
            AgentLogger.log(str_loggerName,'PING: Unable To Reach The Server : '+AgentUtil.AGENT_CONFIG.get('SERVER_INFO', 'server_name')+' : '+AgentUtil.AGENT_CONFIG.get('SERVER_INFO', 'server_port'))
            AgentLogger.log(str_loggerName,'PING: Socket Used For Communicating With The Server : '+repr(sockConn.getsockname()))
            hostIpAddress = sockConn.getsockname()[0]
            isSuccess = False
    except socket.error as e:
        if e.errno == errno.ECONNREFUSED:
            AgentLogger.log([str_loggerName,AgentLogger.MAIN, AgentLogger.STDERR],'PING: ++++++++++++++++++++++++++++++++++ Unable To Reach Server, Connection Refused ++++++++++++++++++++++++++++++++++ \n')         
            isSuccess = False
    except Exception as e:
        AgentLogger.log([str_loggerName,AgentLogger.STDERR],'PING: *************************** Exception While Trying To Establish Connection With The Server *************************** '+ repr(e))
        traceback.print_exc()
        isSuccess = False
    finally:
        if not sockConn == None:
            sockConn.close()
    return isSuccess, hostIpAddress

def isServerReachable(int_retryCount = 10, int_retryInterval = 60, str_loggerName = AgentLogger.STDOUT):
    isSuccess = False
    int_attempt = 1
    AgentLogger.log([str_loggerName],'========================== COMMUNICATION CHECK ==========================\n')
    while not AgentUtil.TERMINATE_AGENT and int_attempt <= int_retryCount:
        int_attempt += 1
        AgentLogger.log([str_loggerName],'Trying To Reach The Server : '+AgentUtil.AGENT_CONFIG.get('SERVER_INFO', 'server_name')+' : '+AgentUtil.AGENT_CONFIG.get('SERVER_INFO', 'server_port')+'\n')
        requestInfo = RequestInfo()
        requestInfo.set_loggerName(AgentLogger.STDOUT)
        requestInfo.set_parseResponse(False)
        requestInfo.set_responseAction(dummy)
        requestInfo.set_method(AgentConstants.HTTP_GET)
        isSuccess, int_errorCode, dict_responseHeaders, dict_responseData = sendRequest(requestInfo)
        if isSuccess:
            AgentLogger.log([str_loggerName],'Established Connection To The Server '+AgentUtil.AGENT_CONFIG.get('SERVER_INFO', 'server_name')+' : '+AgentUtil.AGENT_CONFIG.get('SERVER_INFO', 'server_port')+'\n')
            isSuccess = True
            break
        else:
            AgentLogger.log([str_loggerName,AgentLogger.MAIN],'Unable To Reach The Server '+AgentUtil.AGENT_CONFIG.get('SERVER_INFO', 'server_name')+' : '+AgentUtil.AGENT_CONFIG.get('SERVER_INFO', 'server_port') + '\n')    
            isSuccess = False
            AgentUtil.TERMINATE_AGENT_NOTIFIER.wait(int_retryInterval)            
    return isSuccess

def set_ssl_context(bypass_ssl=False):
    try:
        if str(AgentConstants.CUSTOMER_ID).startswith("aa_") or str(AgentConstants.CUSTOMER_ID).startswith("ab_") or (AgentUtil.AGENT_CONFIG.has_option("AGENT_INFO","ssl_verify") and AgentUtil.AGENT_CONFIG.get("AGENT_INFO","ssl_verify") == "false") or bypass_ssl:
            AgentLogger.log(AgentLogger.MAIN,'==== local zoho corp account detected or ssl verification disabled in install param, SSL Verification disabled = {} ===='.format(bypass_ssl))
            AgentConstants.LOCAL_SSL_CONTEXT = ssl.create_default_context()
            AgentConstants.LOCAL_SSL_CONTEXT.check_hostname = False
            AgentConstants.LOCAL_SSL_CONTEXT.verify_mode = ssl.CERT_NONE
    except Exception as e:
        traceback.print_exc()

def getCaCertPath():
    if '32' in platform.architecture()[0]:
        return
    agent_cert_err_code = None
    try:
        CACERT_FILE_PATHS = [
            ('cacert_file', AgentConstants.AGENT_CERTIFI_CERT),                       # agent's in-built certifi module certicifate
            ('cacert_file', '/etc/ssl/certs/ca-certificates.crt'),                    # Debian/Ubuntu/Gentoo etc
            ('cacert_file', '/etc/pki/tls/certs/ca-bundle.crt'),                      # Fedora/RHEL 6
            ('cacert_file', '/etc/ssl/certs/ca-bundle.crt'),                          # CentOS 7
            ('cacert_file', '/etc/ssl/ca-bundle.pem'),                                # OpenSUSE
            ('cacert_file', '/etc/pki/tls/cacert.pem'),                               # OpenELEC
            ('cacert_file', '/etc/pki/ca-trust/extracted/pem/tls-ca-bundle.pem'),     # CentOS/RHEL 7
            ('cacert_file', '/etc/ssl/cert.pem'),                                     # Alpine Linux
            ('cacert_path', '/usr/local/share/certs/'),                               # FreeBSD
            ('cacert_path', '/etc/pki/tls/certs/'),                                   # Fedora/RHEL
            ('cacert_path', '/etc/openssl/certs/'),                                   # NetBSD
            ('cacert_path', '/var/ssl/certs/'),                                       # AIX
            ('cacert_path', '/etc/ssl/certs/'),                                       # SLES10/SLES11
        ]
        if AgentUtil.AGENT_CONFIG.has_option('AGENT_INFO', 'cacert_file'):
            CACERT_FILE_PATHS.append(('cacert_file', AgentUtil.AGENT_CONFIG.get('AGENT_INFO', 'cacert_file')))
        if AgentUtil.AGENT_CONFIG.has_option('AGENT_INFO', 'cacert_path'):
            CACERT_FILE_PATHS.append(('cacert_path', AgentUtil.AGENT_CONFIG.get('AGENT_INFO', 'cacert_path')))

        for ca_type, ca_path in CACERT_FILE_PATHS:
            if os.path.exists(ca_path):
                AgentLogger.log([AgentLogger.STDOUT],'CA Cert Path - {}'.format(ca_path))
                if ca_type == "cacert_path":
                    AgentConstants.CA_CERT_PATH = ca_path
                    AgentConstants.CA_CERT_FILE = None
                elif ca_type == "cacert_file":
                    AgentConstants.CA_CERT_PATH = None
                    AgentConstants.CA_CERT_FILE = ca_path

                requestInfo = RequestInfo()
                requestInfo.set_loggerName(AgentLogger.STDOUT)
                requestInfo.set_responseAction(dummy)
                requestInfo.set_parseResponse(False)
                requestInfo.set_timeout(5)
                requestInfo.set_method(AgentConstants.HTTP_GET)
                isSuccess, int_errorCode, dict_responseHeaders, dict_responseData = sendRequest(requestInfo)

                if not isSuccess and (isinstance(int_errorCode, ssl.SSLCertVerificationError) or isinstance(int_errorCode, ssl.SSLError)):
                    AgentConstants.CA_CERT_PATH = None
                    AgentConstants.CA_CERT_FILE = None
                    if ca_path == AgentConstants.AGENT_CERTIFI_CERT:
                        agent_cert_err_code = int_errorCode
                        try:
                            AgentLogger.logonce("001", [AgentLogger.PING],'SSL Verification Failed with all CaCert, Plus Domain Certificate Received - \n{}\n'.format(ssl.get_server_certificate((AgentUtil.AGENT_CONFIG.get('SERVER_INFO', 'server_name'), int(AgentUtil.AGENT_CONFIG.get('SERVER_INFO', 'server_port'))))))
                        except Exception as e:
                            traceback.print_exc()
                else:
                    break
            else:
                AgentLogger.log([AgentLogger.STDOUT],'CA Cert Path not found - {}'.format(ca_path))

        if AgentConstants.CA_CERT_PATH is None and AgentConstants.CA_CERT_FILE is None:
            set_ssl_context(True)
            message = str(agent_cert_err_code)+"::ssl verification failed, disabling ssl verification"
            informAgentStatus(message)
        elif agent_cert_err_code and (AgentConstants.CA_CERT_PATH or AgentConstants.CA_CERT_FILE):
            message = str(agent_cert_err_code)+"::ssl verification failed with agent cert but using server local cert"
            informAgentStatus(message)

    except Exception as e:
        AgentLogger.log([AgentLogger.MAIN,AgentLogger.STDERR],' ************************* Exception getting CA Cert Path for communication ************************* '+ repr(e))
        traceback.print_exc()

def informAgentStatus(message):
    dict_requestParameters = {}
    try:
        str_servlet = AgentConstants.DATA_AGENT_HANDLER_SERVLET
        dict_requestParameters["agentKey"] = AgentUtil.AGENT_CONFIG.get('AGENT_INFO', 'agent_key')
        dict_requestParameters["action"] = "AGENT_MESSAGE"
        dict_requestParameters["bno"] = AgentConstants.AGENT_VERSION
        dict_requestParameters["custID"] = AgentConstants.CUSTOMER_ID
        dict_requestParameters["message"] = str(message)
        str_requestParameters = urlencode(dict_requestParameters)
        str_url = str_servlet + str_requestParameters
        requestInfo = RequestInfo()
        requestInfo.set_loggerName(AgentLogger.MAIN)
        requestInfo.set_method(AgentConstants.HTTP_POST)
        requestInfo.set_url(str_url)
        requestInfo.set_timeout(30)
        requestInfo.add_header("Content-Type", 'application/json')
        requestInfo.add_header("Accept", "text/plain")
        requestInfo.add_header("Connection", 'close')
        bool_isSuccess, int_errorCode, dict_responseHeaders, dict_responseData = sendRequest(requestInfo)
        handleResponseHeaders(dict_responseHeaders, dict_responseData, 'FILE UPLOADER')
        if bool_isSuccess:
            AgentLogger.log([AgentLogger.MAIN], 'Successfully acknowledged agent status to the server')
        else:
            AgentLogger.log([AgentLogger.MAIN], '***** Failed to send agent status to the server ***** \n')
            checkNetworkStatus(AgentLogger.MAIN)
    except Exception as e:
        AgentLogger.log(AgentLogger.MAIN,'***** Exception while Sending Agent status ***** :: Error - {}'.format(e))
        traceback.print_exc()

def checkNetworkStatus(str_loggerName = AgentLogger.STDOUT):
    global NETWORK_STATUS_CHECK_TIME, NETWORK_STATUS_CHECK_REACHABLE_URLS
    bool_isSuccess = False
    networkStatusCheckTime = time.time()
    try:
        if NETWORK_STATUS_CHECK_REACHABLE_URLS != None:
            if not NETWORK_STATUS_CHECK_REACHABLE_URLS:
                for str_host, str_protocol, str_port, int_attemptCount in NETWORK_STATUS_CHECK_URLS:
                    if not AgentUtil.TERMINATE_AGENT:
                        AgentLogger.log([str_loggerName],'=============================== CHECK NETWORK STATUS ===============================')
                        AgentLogger.log(AgentLogger.STDOUT,'Trying to reach the host : '+repr(str_host))
                        requestInfo = RequestInfo()
                        requestInfo.set_loggerName(AgentLogger.STDOUT)
                        requestInfo.set_host(str_host)
                        requestInfo.set_port(str_port)
                        requestInfo.set_protocol(str_protocol)
                        requestInfo.set_responseAction(dummy)
                        requestInfo.set_parseResponse(False)
                        requestInfo.set_timeout(5)
                        requestInfo.set_method(AgentConstants.HTTP_GET)
                        isSuccess, int_errorCode, dict_responseHeaders, dict_responseData = sendRequest(requestInfo)
                        int_attemptCount+=1
                        if isSuccess:
                            AgentLogger.log([str_loggerName],'Established connection to the host '+repr(str_host))
                            bool_isSuccess = True
                            NETWORK_STATUS_CHECK_REACHABLE_URLS.append((str_host, str_protocol, str_port, int_attemptCount))
                            #break
                        else:
                            AgentLogger.log([str_loggerName],'Unable to reach the host : '+repr(str_host))
                if len(NETWORK_STATUS_CHECK_REACHABLE_URLS) == 0:
                    AgentLogger.log([AgentLogger.MAIN],'Unable to reach all network status check urls \n')
                    NETWORK_STATUS_CHECK_REACHABLE_URLS = None
            else:
                timeDiff = (networkStatusCheckTime - NETWORK_STATUS_CHECK_TIME)
                if timeDiff > AgentConstants.NETWORK_STATUS_CHECK_INTERVAL:
                    for str_host, str_protocol, str_port, int_attemptCount in NETWORK_STATUS_CHECK_REACHABLE_URLS:
                        if not AgentUtil.TERMINATE_AGENT:
                            AgentLogger.log([str_loggerName],'=============================== CHECK NETWORK STATUS ===============================')
                            AgentLogger.log(AgentLogger.STDOUT,'Trying to reach the host : '+repr(str_host))
                            requestInfo = RequestInfo()
                            requestInfo.set_loggerName(AgentLogger.STDOUT)
                            requestInfo.set_host(str_host)
                            requestInfo.set_port(str_port)
                            requestInfo.set_protocol(str_protocol)
                            requestInfo.set_responseAction(dummy)
                            requestInfo.set_parseResponse(False)
                            requestInfo.set_timeout(5)
                            requestInfo.set_method(AgentConstants.HTTP_GET)
                            isSuccess, int_errorCode, dict_responseHeaders, dict_responseData = sendRequest(requestInfo)
                            if isSuccess:
                                AgentLogger.log([str_loggerName],'Established connection to the host '+repr(str_host))
                                bool_isSuccess = True
                                break
                            else:
                                AgentLogger.log([str_loggerName],'Unable to reach the host : '+repr(str_host))
                    NETWORK_STATUS_CHECK_TIME = networkStatusCheckTime
                else:
                    AgentLogger.log([str_loggerName],'Network status check will be done after '+repr(AgentConstants.NETWORK_STATUS_CHECK_INTERVAL - timeDiff)+' seconds')
        else:
            AgentLogger.log([str_loggerName],'Reachable network status check urls is empty')
    except Exception as e:
        AgentLogger.log([str_loggerName, AgentLogger.STDERR], '*************************** Exception while checking network status ************************** '+ repr(e))
        traceback.print_exc()          
    return bool_isSuccess

def dummy():
    pass

class ServerInfo:
    def __init__(self):
        self.host = None
        self.port = None
        self.protocol = None
        self.timeout = None            
    def __str__(self):
        return 'SERVER INFO : Host : '+str(self.host)+' Port : '+str(self.port)+' Protocol : '+str(self.protocol)+' Timeout : '+str(self.timeout)    
    def set_host(self, host):
        self.host = host    
    def get_host(self):
        return self.host    
    def set_port(self, port):
        self.port = port        
    def get_port(self):
        return self.port        
    def set_protocol(self, protocol):
        self.protocol = protocol
    def get_protocol(self):
        return self.protocol
    def set_timeout(self, timeout):
        self.timeout = int(timeout)    
    def get_timeout(self):
        return self.timeout
         
class ProxyInfo:
    def __init__(self):
        self.host = None
        self.port = None
        self.protocol = AgentConstants.HTTP_PROTOCOL
        self.username = None
        self.password = None
    def __str__(self):
        return 'PROXY INFO : Host : '+str(self.host)+' Port : '+str(self.port)+' Protocol : '+str(self.protocol)+' User name : '+str(self.username)+' Password : '+str(self.password)      
    def set_host(self, host):
        self.host = host    
    def get_host(self):
        return self.host    
    def set_port(self, port):
        self.port = port        
    def get_port(self):
        return self.port        
    def set_protocol(self, protocol):
        self.protocol = protocol
    def get_protocol(self):
        return self.protocol
    def set_username(self, username):
        self.username = username
    def get_username(self):
        return self.username
    def set_password(self, password):
        self.password = password
    def get_password(self):
        return self.password
    def getUrl(self):
        str_urlToReturn = None
#         if self.username:
#             AgentLogger.log(AgentLogger.STDOUT,'Username : '+repr(self.username));
        if self.username != '0' and self.password == '0':
            str_urlToReturn = r''+self.protocol+'://'+self.username+'@'+self.host+':'+str(self.port)
        elif self.username != '0' and self.password != '0':
            if not AgentConstants.CRYPTO_MODULE == None:
                str_urlToReturn = r''+self.protocol+'://'+self.username+':'+AgentCrypt.decrypt_with_proxy_key(self.password)+'@'+self.host+':'+str(self.port)
            else:
                str_urlToReturn = r''+self.protocol+'://'+self.username+':'+self.password+'@'+self.host+':'+str(self.port)
        else:
            str_urlToReturn = r''+self.protocol+'://'+self.host+':'+str(self.port)
        return str_urlToReturn        

#
# Default request method is GET

class RequestInfo(object):
    def __init__(self):
        self.host = None
        self.port = None
        self.protocol = None
        self.timeout = None
        self.isSecondaryServer = False
        self.method = AgentConstants.HTTP_GET          
        self.url = ''
        self.data = ''
        self.dataType = None
        self.responseAction = None
        self.boolParseResponse = True
        self.headers = {}        
        self.customParams = {}    
        self.logger = AgentLogger
        self.loggerName = None
        self.str_uploadFilePath = None
        self.str_uploadFileName = None
        self.ssl_verification = True
        #proxy details    
        self.proxy = False
        self.proxy_host = None
        self.proxy_port = None
        self.proxy_user_name = None
        self.proxy_host = None
        self.byPassProxy = False
        if SERVER_INFO:
            self.host = SERVER_INFO.get_host()
            self.port = SERVER_INFO.get_port()
            self.protocol = SERVER_INFO.get_protocol()
            self.timeout = SERVER_INFO.get_timeout()            
        if PROXY_INFO:
            self.proxy = True
            self.proxy_host = PROXY_INFO.get_host()
            self.proxy_port = PROXY_INFO.get_port()
            self.proxy_user_name = PROXY_INFO.get_username()
            self.proxy_password = PROXY_INFO.get_password()
        self.add_header('User-Agent', AgentConstants.AGENT_NAME)
    def __str__(self):
        str_requestInfo = ''
        str_requestInfo += 'HOST : '+repr(self.host)
        str_requestInfo += ' PORT : '+repr(self.port)
        str_requestInfo += ' PROTOCOL : '+repr(self.protocol)
        str_requestInfo += ' TIMEOUT : '+repr(self.timeout)+'\n'
        str_requestInfo += ' IS SECONDARY SERVER : '+repr(self.isSecondaryServer)+'\n'
        str_requestInfo += 'METHOD : '+repr(self.method)
        str_requestInfo += ' URL : '+repr(self.url)+'\n'
        str_requestInfo += 'HEADERS : '+repr(self.headers)+'\n'
        str_requestInfo += 'RESPONSE ACTION : '+repr(self.responseAction)+'\n'
        str_requestInfo += 'CUSTOM PARAMETERS : '+repr(self.customParams)+'\n'
        if 'Content-Type' in self.headers and not self.headers['Content-Type'] == 'zip':            
            str_requestInfo += 'Request Body : '+repr(self.data)+'\n'
        elif 'content-type' in self.headers and not self.headers['content-type'] == 'zip':            
            str_requestInfo += 'Request Body : '+repr(self.data)+'\n'
        return str_requestInfo    
    def set_method(self, str_method):
        self.method = str_method
    def get_method(self):
        return self.method
    def set_url(self, url):
        self.url = url        
    def get_url(self):
        return self.url    
    def set_data(self, data):
        self.data = data
    def set_parseResponse(self, boolParseResponse):
        self.boolParseResponse = boolParseResponse
    def get_parseResponse(self):
        return self.boolParseResponse
    def set_responseAction(self, responseAction):
        self.responseAction = responseAction
    def get_responseAction(self):
        return self.responseAction
    def get_data(self):
        return self.data
    def set_dataType(self, str_dataType):
        self.dataType = str_dataType
    def get_dataType(self):
        return self.dataType
    def get_host(self):        
        return self.host
    def set_host(self, str_host):        
        self.host = str_host
    def get_port(self):        
        return self.port
    def set_port(self, str_port):        
        self.port = str_port
    def get_protocol(self):        
        return self.protocol
    def set_protocol(self, str_protocol):        
        self.protocol = str_protocol
    def get_timeout(self):        
        return self.timeout
    def set_timeout(self, timeout):        
        self.timeout = int(timeout)
    def add_header(self, key, val):
        self.headers[key.capitalize()] = val
    def get_headers(self):
        return self.headers
    def useSecondaryServer(self):
        self.isSecondaryServer = True
        if SECONDARY_SERVER_INFO:
            self.host = SECONDARY_SERVER_INFO.get_host()
            self.port = SECONDARY_SERVER_INFO.get_port()
            self.protocol = SECONDARY_SERVER_INFO.get_protocol()
            self.timeout = SECONDARY_SERVER_INFO.get_timeout()
    def add_custom_param(self, key, val):
        self.customParams[key] = val
    def bypass_proxy(self):
        self.byPassProxy = True
    def get_custom_params(self):
        return self.customParams
    def get_logger(self):
        return self.logger
    def set_logger(self, logger):
        self.logger = logger
    def get_loggerName(self):
        return self.loggerName
    def set_loggerName(self, loggerName):
        self.loggerName = loggerName
    def set_ssl_verification(self, ssl_verification):
        self.ssl_verification = ssl_verification
    def get_ssl_verification(self):
        return self.ssl_verification
    def get_uploadFilePath(self):
        return self.str_uploadFilePath
    def set_uploadFilePath(self, str_uploadFilePath):
        self.str_uploadFilePath = str_uploadFilePath
    def get_uploadFileName(self):
        return self.str_uploadFileName
    def set_uploadFileName(self, str_uploadFileName):
        self.str_uploadFileName = str_uploadFileName
    def preRequest(self):
        bool_toReturn = True
        if not self.get_uploadFileName() == None:
            bool_toReturn = self.getFileData()
        return bool_toReturn
    def postRequest(self):
        pass
    def getFileData(self):
        bool_toReturn = True        
        fileSysEncoding = sys.getfilesystemencoding()
        file_obj = None
        try:            
            if os.path.isfile(self.str_uploadFilePath):                
                file_obj = open(self.str_uploadFilePath,'rb')
                byte_data = file_obj.read()
                str_data = byte_data.decode(fileSysEncoding)
                my_dict = json.loads(str_data)#String to python object (dictionary)
                str_jsonData = json.dumps(my_dict)#python dictionary to json string
                #str_encodedJsonData = str_jsonData.encode('UTF-16LE')
                self.set_data(str_jsonData)
        except Exception as e:
            self.logger.log(self.loggerName, ' ************************* Exception while reading the file '+repr(self.str_uploadFilePath)+' ************************* '+ repr(e))
            traceback.print_exc()      
            bool_toReturn = False          
        finally:
            if file_obj:
                file_obj.close()
        return bool_toReturn
        
def sendRequest(requestInfo):
    bool_toReturn = True
    int_errorCode = 0
    dict_responseHeaders = None
    dict_responseData = None
    conn = None
    bool_print = True
    str_url = None
    dataToSend = None
    bool_isTimeoutError = False
    str_host = None
    str_port = None
    str_protocol = None
    try:
        str_host = requestInfo.get_host()
        str_port = str(requestInfo.get_port())
        str_protocol = requestInfo.get_protocol()
        if requestInfo.get_host() != AgentConstants.DMS_SERVER and requestInfo.get_loggerName() not in [AgentLogger.STDOUT,AgentLogger.PLUGINS]:
            AgentLogger.log(requestInfo.get_loggerName(),'================================= SEND REQUEST =================================')
        AgentLogger.debug(requestInfo.get_loggerName(),'REQUEST INFO : '+str(requestInfo))
        if requestInfo.byPassProxy == True:
            proxy = urlconnection.ProxyHandler({})
            bypassOpener = urlconnection.build_opener(proxy)
            urlconnection.install_opener(bypassOpener)
        if requestInfo.preRequest():
            if requestInfo.get_data() and requestInfo.get_dataType() == 'application/zip':
                dataToSend = requestInfo.get_data()
            elif requestInfo.get_data():
                AgentLogger.debug(requestInfo.get_loggerName(),'Request data : '+repr(requestInfo.get_data()))
                AgentLogger.debug(requestInfo.get_loggerName(),'Request data type : '+repr(type(requestInfo.get_data())))
                dataToSend = requestInfo.get_data().encode('UTF-16LE')
            if str_host != SERVER_INFO.get_host() and str_host != AgentConstants.DMS_SERVER:
                str_url = str_protocol+'://'+str_host+':'+str_port+requestInfo.get_url()
            else:
                str_url = AgentConstants.HTTPS_PROTOCOL+'://'+str_host+':'+str_port+requestInfo.get_url()  
            AgentLogger.debug(requestInfo.get_loggerName(),'Data to send : '+repr(dataToSend))         
            AgentLogger.debug(requestInfo.get_loggerName(),'REQUEST URL : '+str(str_url)) 
            requestObj = urlconnection.Request(str_url, dataToSend, requestInfo.get_headers())

            #currently used only for url checks
            if '32' in platform.architecture()[0]:
                if PROXY_INFO:
                    proxy = None
                    if str_host != SERVER_INFO.get_host() and str_host != AgentConstants.DMS_SERVER:
                        proxy = urlconnection.ProxyHandler({str_protocol: PROXY_INFO.getUrl()})
                    else:
                        proxy = urlconnection.ProxyHandler({AgentConstants.HTTPS_PROTOCOL: PROXY_INFO.getUrl()})
                    auth = urlconnection.HTTPBasicAuthHandler()
                    opener = urlconnection.build_opener(proxy, auth, urlconnection.HTTPSHandler)
                    urlconnection.install_opener(opener)
                response = urlconnection.urlopen(requestObj, timeout=requestInfo.get_timeout())
            elif not requestInfo.get_ssl_verification():
                local_ssl_context = ssl.create_default_context()
                local_ssl_context.check_hostname = False
                local_ssl_context.verify_mode = ssl.CERT_NONE
                response = urlconnection.urlopen(requestObj, timeout=requestInfo.get_timeout(), context=local_ssl_context)
            elif PROXY_INFO:
                if AgentConstants.LOCAL_SSL_CONTEXT:
                    context = AgentConstants.LOCAL_SSL_CONTEXT
                else:
                    context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH,
                                                         cafile=AgentConstants.CA_CERT_FILE,
                                                         capath=AgentConstants.CA_CERT_PATH)
                context.set_alpn_protocols(['http/1.1'])
                https_handler = urlconnection.HTTPSHandler(context=context)
                proxy = urlconnection.ProxyHandler({str_protocol: PROXY_INFO.getUrl()}) if str_host != SERVER_INFO.get_host() and str_host != AgentConstants.DMS_SERVER else urlconnection.ProxyHandler({AgentConstants.HTTPS_PROTOCOL: PROXY_INFO.getUrl()})
                auth = urlconnection.HTTPBasicAuthHandler()
                opener = urlconnection.build_opener(proxy, auth, https_handler)
                urlconnection.install_opener(opener)
                response = urlconnection.urlopen(requestObj, timeout=requestInfo.get_timeout())
            elif AgentConstants.LOCAL_SSL_CONTEXT is not None:
                response = urlconnection.urlopen(requestObj, timeout=requestInfo.get_timeout(), context=AgentConstants.LOCAL_SSL_CONTEXT)
            else:
                context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH,
                                                     cafile=AgentConstants.CA_CERT_FILE,
                                                     capath=AgentConstants.CA_CERT_PATH)
                context.set_alpn_protocols(['http/1.1'])
                https_handler = urlconnection.HTTPSHandler(context=context)
                opener = urlconnection.build_opener(https_handler)
                urlconnection.install_opener(opener)
                response = urlconnection.urlopen(requestObj, timeout=requestInfo.get_timeout())
            if response.getcode() == 200: 
                byte_responseData = None
                str_responseData = None
                if requestInfo.get_host() != AgentConstants.DMS_SERVER and AgentConstants.AGENT_STATUS_UPDATE_SERVLET not in requestInfo.get_url() and AgentConstants.AGENT_FILE_COLLECTOR_SERVLET not in requestInfo.get_url() and AgentConstants.PLUGIN_REGISTER_SERVLET not in requestInfo.get_url():
                    AgentLogger.log(requestInfo.get_loggerName(),'Page found successfully')    
                dict_responseHeaders = dict(response.headers)
                if requestInfo.get_parseResponse():
                    byte_responseData = response.read() 
                    if requestInfo.get_host() != AgentConstants.DMS_SERVER and 'Content-Type' in dict_responseHeaders:
                        AgentLogger.log(requestInfo.get_loggerName(),'Response content type : '+repr(dict_responseHeaders['Content-Type']))
                    elif requestInfo.get_host() != AgentConstants.DMS_SERVER and 'content-type' in dict_responseHeaders:
                        AgentLogger.log(requestInfo.get_loggerName(),'Response content type : '+repr(dict_responseHeaders['content-type']))
                    AgentLogger.debug(requestInfo.get_loggerName(),'Response data : '+repr(byte_responseData))
                    AgentLogger.debug(requestInfo.get_loggerName(),'Type of response data : '+repr(type(byte_responseData)))
                    if not byte_responseData == None:
                        if requestInfo.get_responseAction() == saveFile:
                            requestInfo.get_responseAction()(requestInfo, byte_responseData)
                        elif requestInfo.get_responseAction() == dummy:
                            pass
                        else:
                            if 'encoding' in dict_responseHeaders:
                                str_responseData = byte_responseData.decode('UTF-16LE')
                            elif 'Content-Type' in dict_responseHeaders and 'charset=UTF-16LE' in dict_responseHeaders['Content-Type']:
                                str_responseData = byte_responseData.decode('UTF-16LE')
                            elif "content-type" in dict_responseHeaders and 'charset=UTF-16LE' in dict_responseHeaders['content-type']:
                                str_responseData = byte_responseData.decode('UTF-16LE')
                            else:
                                str_responseData = byte_responseData.decode('UTF-8')
                            if not str_responseData == '':
                                if not requestInfo.get_responseAction() == None:
                                    requestInfo.get_responseAction()(requestInfo, str_responseData)
                                else:                  
                                    try:
                                        if AgentConstants.PYTHON_VERSION == 2:
                                            dict_responseData = str_responseData
                                        else:
                                            str_unicodeResponseData = str(str_responseData,'UTF-16LE')
                                            dict_responseData = json.loads(str_unicodeResponseData)
                                    except Exception as e:
                                        dict_responseData = str_responseData                    
            elif response.getcode() == 404:
                AgentLogger.log(requestInfo.get_loggerName(),'Response Status : '+repr(response.status)+', Page Not Found')
                bool_toReturn = False
            else:
                AgentLogger.log(requestInfo.get_loggerName(),'Response Status : '+repr(response.status)+' Reason : '+repr(response.reason))
                bool_toReturn = False
        else:
            AgentLogger.log(requestInfo.get_loggerName(),'************************* PRE-REQUEST OPERATION FAILED **********************')
            bool_toReturn = False
    except socket.timeout as e:
        if requestInfo.get_host() != AgentConstants.DMS_SERVER:
            AgentLogger.log(requestInfo.get_loggerName(),'++++++++++++++++++++++++++++++++++ The read operation timed out ++++++++++++++++++++++++++++++++++ ')
            AgentLogger.log(requestInfo.get_loggerName(),'Reason : '+repr(e))
        int_errorCode = e
        bool_toReturn = False  
        bool_print = False
        bool_isTimeoutError = True
    except URLError as e:
        if isinstance(e.reason, ssl.CertificateError):
            AgentLogger.log(requestInfo.get_loggerName(),'++++++++++++++++++++++++++++++++++ Unable To Reach Server, Connection Refused ++++++++++++++++++++++++++++++++++ ')
            AgentLogger.log(requestInfo.get_loggerName(),'Reason : '+repr(e.reason))
            int_errorCode = e.reason
            bool_toReturn = False
            bool_print = False
        elif isinstance(e.reason, socket.timeout):
            if requestInfo.get_host() != AgentConstants.DMS_SERVER:
                AgentLogger.log(requestInfo.get_loggerName(),'++++++++++++++++++++++++++++++++++ The read operation timed out ++++++++++++++++++++++++++++++++++ ')
                AgentLogger.log(requestInfo.get_loggerName(),'Reason : '+repr(e.reason))
            int_errorCode = e.reason
            bool_toReturn = False  
            bool_print = False
            bool_isTimeoutError = True
        elif isinstance(e.reason, OSError):
            AgentLogger.log([requestInfo.get_loggerName()],'++++++++++++++++++++++++++++++++++ OS error ++++++++++++++++++++++++++++++++++ '+repr(requestInfo.get_host()))
            AgentLogger.log([requestInfo.get_loggerName()],'Error No : '+str(e.reason.errno)+' Error Message : '+str(e.reason.strerror))
            int_errorCode = e.reason
            bool_toReturn = False  
            bool_print = False
        elif isinstance(e,HTTPError):
            AgentLogger.log([requestInfo.get_loggerName()],'++++++++++++++++++++++++++++++++++ HTTP Error raised ++++++++++++++')
            AgentLogger.log([requestInfo.get_loggerName()],'Reason : '+repr(e.reason)+'Code : '+ repr(e.code))
            int_errorCode = e.code
            bool_toReturn = False
            bool_print = False
        else:
            AgentLogger.log(requestInfo.get_loggerName(),'*************************** URLError While Sending Data To Server *************************** '+ repr(e))
            traceback.print_exc()
            AgentLogger.log(requestInfo.get_loggerName(),'Reason : '+repr(e.reason)+' Type : '+repr(type(e.reason)))
            bool_toReturn = False
    except InvalidURL as e:
        AgentLogger.log(requestInfo.get_loggerName(),'++++++++++++++++++++++++++++++++++ Invalid URL exception raised ++++++++++++++')
        AgentLogger.log(requestInfo.get_loggerName(),'Exception:' + repr(e) )
        int_errorCode = 404
        bool_toReturn = False
        bool_print = False 
    except ssl.SSLError as e:
        AgentLogger.log(requestInfo.get_loggerName(),'*************************** SSL Error While Sending Data To Server *************************** '+ repr(e))
        traceback.print_exc()
        AgentLogger.log(requestInfo.get_loggerName(),' Error Number : '+repr(e.errno))
        int_errorCode = e
        bool_toReturn = False      
        AgentLogger.log(requestInfo.get_loggerName(),'REQUEST INFO : '+str(requestInfo))             
    except socket.error as e:
        if e.errno == errno.ECONNREFUSED:
            AgentLogger.log(requestInfo.get_loggerName(),'++++++++++++++++++++++++++++++++++ Unable To Reach Server, Connection Refused ++++++++++++++++++++++++++++++++++ ')
            int_errorCode = e.errno
            bool_toReturn = False
            bool_print = False
        else:
            AgentLogger.log(requestInfo.get_loggerName(),'*************************** Exception While Sending Data To Server *************************** '+ repr(e))
            traceback.print_exc()
            AgentLogger.log(requestInfo.get_loggerName(),' Error While trying to reach server : '+repr(e.errno))
            int_errorCode = e.errno
            bool_toReturn = False
        AgentLogger.log(requestInfo.get_loggerName(),'REQUEST INFO : '+str(requestInfo))
    except Exception as e:    
        AgentLogger.log(requestInfo.get_loggerName(),'*************************** Exception While Sending Data To Server *************************** '+ repr(e))
        traceback.print_exc()
        bool_toReturn = False
        AgentLogger.log(requestInfo.get_loggerName(),'REQUEST INFO : '+str(requestInfo)) 
    finally:
        if not conn == None:
            conn.close()
        if requestInfo.get_host() == AgentConstants.DMS_SERVER and not bool_isTimeoutError:
            AgentLogger.debug(requestInfo.get_loggerName(),'Return status : '+repr(bool_toReturn)+' Error code : '+repr(int_errorCode)+' Response Data : '+repr(dict_responseData))
            AgentLogger.debug(requestInfo.get_loggerName(),'Response Headers : '+repr(dict_responseHeaders))
        elif requestInfo.get_host() != AgentConstants.DMS_SERVER and AgentConstants.AGENT_STATUS_UPDATE_SERVLET not in requestInfo.get_url() and AgentConstants.AGENT_FILE_COLLECTOR_SERVLET not in requestInfo.get_url() and AgentConstants.PLUGIN_REGISTER_SERVLET not in requestInfo.get_url():
            AgentLogger.log(requestInfo.get_loggerName(),'Return status : '+repr(bool_toReturn)+' Error code : '+repr(int_errorCode))
            AgentLogger.debug(requestInfo.get_loggerName(),'Response Data : '+repr(dict_responseData))
            AgentLogger.debug(requestInfo.get_loggerName(),'Response Headers : '+repr(dict_responseHeaders))
        requestInfo = None
    return bool_toReturn, int_errorCode, dict_responseHeaders, dict_responseData

def format_headers_case(response_headers_dict, response_header_attributes):
    for attr in response_header_attributes:
        if attr.lower() in response_headers_dict:
            response_headers_dict[attr] = response_headers_dict[attr.lower()]
            response_headers_dict.pop(attr.lower())

def handleResponseHeaders(dict_responseHeaders, dict_responseData, str_invoker, upload_dir=None):
    bool_isSuccess = True
    try:
        if dict_responseHeaders:
            AgentLogger.debug(AgentLogger.MAIN,'headers - {0}'.format(dict_responseHeaders))
        if dict_responseHeaders and AgentConstants.PYTHON_VERSION == 2:
            format_headers_case(dict_responseHeaders, [AgentConstants.WMS_FAILED_REQ, AgentConstants.SUSPEND_UPLOAD_FLAG, AgentConstants.PEER_VALIDATE, AgentConstants.PEER_SCHEDULE,\
                                                   AgentConstants.DISABLE_AGENT_SERVICE, AgentConstants.SUSPEND_MONITORING, AgentConstants.GENERATE_RCA, AgentConstants.GENERATE_NETWORK_RCA,\
                                                   AgentConstants.INITIATE_AGENT_UPGRADE, AgentConstants.INITIATE_PATCH_UPGRADE, AgentConstants.UPDATE_AGENT_CONFIG, AgentConstants.DOCKER_DATA_COLLECTOR_REPONSE,\
                                                   'GET_CONSOLIDATED_REQUESTS', 'UPTIME_MONITORING', 'APPLOG_ENABLED','HADOOP_STOP_DC_FOR_NODES',AgentConstants.HADOOP_DATA_COLLECTOR_REPONSE,'SUSPEND_UPLOAD_TIME',AgentConstants.STOP_MONITORING,AgentConstants.SERVER_SETTINGS])
        if dict_responseHeaders:
            for key , value in dict_responseHeaders.items():
                if key in AgentConstants.RESPONSE_HEADERS_VIA_DMS:
                    dict_task = {}
                    dict_task[key] = value
                    com.manageengine.monagent.communication.DMSHandler.execute_action(key,dict_task)
        if (dict_responseHeaders and (AgentConstants.UPDATE_AGENT_CONFIG in dict_responseHeaders)):
            if dict_responseHeaders[AgentConstants.UPDATE_AGENT_CONFIG] == "true":
                apps_config = False
                if dict_responseHeaders and 'apps' in dict_responseHeaders:
                    apps_config = True
                com.manageengine.monagent.collector.DataConsolidator.updateAgentConfig(False,apps_config)
        if dict_responseHeaders and AgentConstants.DOCKER_DATA_COLLECTOR_REPONSE in dict_responseHeaders :
            id_patrol().commit("docker", dict_responseData)
        if dict_responseHeaders and 'pluginkey' in dict_responseHeaders:
            pluginDict=dict_responseHeaders['pluginkey']
            AgentLogger.log(AgentLogger.PLUGINS,'plugin response --- {0}'.format(pluginDict))
            module_object_holder.plugins_util.updatePluginJson(pluginDict)
            d = json.loads(pluginDict)
            for k in d:
                AgentLogger.log([AgentLogger.MAIN,AgentLogger.PLUGINS],'Plugin Registered Successfully =====>'+repr(k)+'\n')
                AgentConstants.UPDATE_PLUGIN_INVENTORY=True 
                plug_name = k
                module_object_holder.plugins_obj.removePluginFromIgnoreList(plug_name)
                if AgentConstants.PLUGIN_DEPLOY_CONFIG and plug_name in AgentConstants.PLUGIN_DEPLOY_CONFIG:
                    AgentConstants.PLUGIN_DEPLOY_CONFIG.pop(plug_name,None)
        if dict_responseHeaders and 'error' in dict_responseHeaders:
            error_dict=json.loads(dict_responseHeaders['error'])
            AgentLogger.log([AgentLogger.MAIN,AgentLogger.PLUGINS],'Error For Plugin  : {} / msg  : {} '.format(error_dict['plugin_name'],error_dict['error_msg'])+'\n')
            e_dict={}
            e_dict[error_dict['plugin_name']]={}
            e_dict[error_dict['plugin_name']]['status']=2
            e_dict[error_dict['plugin_name']]['error_msg']=error_dict['error_msg']
            module_object_holder.plugins_obj.populateIgnorePluginsList(error_dict['plugin_name'],error_dict['error_msg'])
            module_object_holder.plugins_util.updatePluginJson(json.dumps(e_dict))
        if dict_responseHeaders and 'GET_CONSOLIDATED_REQUESTS' in dict_responseHeaders and dict_responseHeaders['GET_CONSOLIDATED_REQUESTS']=='true':
            AgentLogger.log(AgentLogger.MAIN,'Received GET_CONSOLIDATED_REQUESTS from status updater '+'\n')
            #getConsolidatedWMSData()
            if com.manageengine.monagent.communication.AgentStatusHandler.WMS_THREAD.paused is True:
                com.manageengine.monagent.communication.AgentStatusHandler.WMS_THREAD.resume()
        if dict_responseHeaders and 'CONSOLIDATED_REQUESTS' in dict_responseHeaders and dict_responseHeaders['CONSOLIDATED_REQUESTS']=='true':
            AgentLogger.log(AgentLogger.MAIN,'Received CONSOLIDATED_REQUESTS from file collector '+'\n')
            handleResponseData(dict_responseHeaders, dict_responseData, 'CONSOLIDATED_REQUESTS')
        if dict_responseHeaders and 'poll' in dict_responseHeaders:
            pollInterval = dict_responseHeaders['poll']
            if pollInterval != AgentConstants.POLL_INTERVAL:
                AgentConstants.POLL_INTERVAL = pollInterval
                AgentLogger.log(AgentLogger.COLLECTOR,'Monitoring Poll Interval - {0} '.format(pollInterval)+'\n')
                com.manageengine.monagent.util.eBPFUtil.initialize(True)
                if AgentConstants.PS_UTIL_DC:
                    com.manageengine.monagent.collector.ps_util_metric_collector.reinit_monitoring()
                elif not AgentConstants.IS_DOCKER_AGENT == "1":
                    dict={}
                    dict['INTERVAL']=pollInterval
                    com.manageengine.monagent.collector.DataCollector.changeMonitoringInterval(dict)
            else:
                AgentLogger.log(AgentLogger.COLLECTOR,'No difference in poll values |  server value -- {0} agent value -- {1}'.format(pollInterval,AgentConstants.POLL_INTERVAL)+'\n')
        if dict_responseHeaders and 'SELF_MON_INTERVAL' in dict_responseHeaders:
            self_monitor_poll = dict_responseHeaders['SELF_MON_INTERVAL']
            AgentLogger.log(AgentLogger.COLLECTOR,'Request received to change Self Monitoring poll interval to {0} '.format(self_monitor_poll)+'\n')
            AgentUtil.ChangeTaskInterval('SelfMonitoring', self_monitor_poll)
        if dict_responseHeaders and 'ADDM_INTERVAL' in dict_responseHeaders:
            addm_monitor_poll = dict_responseHeaders['ADDM_INTERVAL']
            AgentLogger.log(AgentLogger.COLLECTOR,'Request received to change ADDM interval to {0} '.format(addm_monitor_poll)+'\n')
            AgentUtil.ChangeTaskInterval('ADDM', addm_monitor_poll)
        if dict_responseHeaders and 'CONT_DISCOVERY_INT' in dict_responseHeaders:
            AppConstants.CONTAINER_DISCOVERY_INTERVAL = dict_responseHeaders['CONT_DISCOVERY_INT']
            AgentLogger.log(AgentLogger.APPS,'Header received to change container discovery interval to {0} '.format(AppConstants.CONTAINER_DISCOVERY_INTERVAL)+'\n')
            container_monitoring.initialize(True)
        if dict_responseHeaders and 'UPTIME_MONITORING' in dict_responseHeaders:
            AgentLogger.log(AgentLogger.STDOUT,'Uptime Monitoring Request Received From Server'+'\n')
            AgentLogger.log(AgentLogger.STDOUT,'Uptime Monitoring Before Server Request : '+repr(AgentConstants.UPTIME_MONITORING)+'\n')
            AgentConstants.UPTIME_MONITORING=dict_responseHeaders['UPTIME_MONITORING']
            AgentLogger.log(AgentLogger.STDOUT,'Uptime Monitoring After Server Request : '+repr(AgentConstants.UPTIME_MONITORING)+'\n')
        if dict_responseHeaders and 's_v' in dict_responseHeaders:
            AgentLogger.log(AgentLogger.STDOUT,'Server Violated Threshold JSON : {0}'.format(dict_responseHeaders['s_v'])+'\n')
            AgentConstants.S_V_DICT = json.loads(dict_responseHeaders['s_v'])
        if dict_responseHeaders and 'APPLOG_ENABLED' in dict_responseHeaders:
            AgentLogger.log(AgentLogger.STDOUT, 'APPLOG_ENABLED  : {0}'.format(dict_responseHeaders['APPLOG_ENABLED']))
            if dict_responseHeaders['APPLOG_ENABLED'] == 'true':
                com.manageengine.monagent.communication.applog.enable()
            else:
                com.manageengine.monagent.communication.applog.disable()
        if dict_responseHeaders and 'SKEY' in dict_responseHeaders:
            AgentUtil.update_proxy_settings(dict_responseHeaders['SKEY'])
        if dict_responseHeaders and 'timeDiff' in dict_responseHeaders:
            time_diff = dict_responseHeaders['timeDiff']
            if not time_diff == '' and not time_diff == None:
                AgentUtil.AGENT_CONFIG.set('AGENT_INFO', 'time_diff', time_diff)                        
                AgentUtil.persistAgentInfo()
        if dict_responseHeaders and AgentConstants.KUBE_SEND_CONFIG in dict_responseHeaders:
            com.manageengine.monagent.kubernetes.SettingsHandler.KubeActions.set_send_config(dict_responseHeaders[AgentConstants.KUBE_SEND_CONFIG])
        if dict_responseHeaders and AgentConstants.KUBE_SEND_PERF in dict_responseHeaders:
            com.manageengine.monagent.kubernetes.SettingsHandler.KubeActions.set_send_perf(dict_responseHeaders[AgentConstants.KUBE_SEND_PERF])
        if dict_responseHeaders and AgentConstants.KUBE_CONFIG_DC_INTERVAL in dict_responseHeaders:
            AgentLogger.log(AgentLogger.KUBERNETES,'received kube config dc interval')
            com.manageengine.monagent.kubernetes.SettingsHandler.KubeActions.set_config_dc_interval(dict_responseHeaders[AgentConstants.KUBE_CONFIG_DC_INTERVAL])
        if dict_responseHeaders and AgentConstants.KUBE_CHILD_COUNT in dict_responseHeaders:
            AgentLogger.log(AgentLogger.KUBERNETES,'received kube child count')
            com.manageengine.monagent.kubernetes.SettingsHandler.KubeActions.set_child_write_count(dict_responseHeaders[AgentConstants.KUBE_CHILD_COUNT])
        if dict_responseHeaders and AgentConstants.KUBE_API_SERVER_ENDPOINT in dict_responseHeaders:
            AgentLogger.log(AgentLogger.KUBERNETES,'received KUBE_API_SERVER_ENDPOINT')
            com.manageengine.monagent.kubernetes.SettingsHandler.KubeActions.set_api_server_endpoint_url(dict_responseHeaders[AgentConstants.KUBE_API_SERVER_ENDPOINT])
        if dict_responseHeaders and AgentConstants.KUBE_STATE_METRICS_URL in dict_responseHeaders:
            AgentLogger.log(AgentLogger.KUBERNETES,'received KUBE_STATE_METRICS_URL')
            com.manageengine.monagent.kubernetes.SettingsHandler.KubeActions.set_kube_state_metrics_url(dict_responseHeaders[AgentConstants.KUBE_STATE_METRICS_URL])
        if dict_responseHeaders and AgentConstants.KUBE_CLUSTER_DN in dict_responseHeaders:
            AgentLogger.log(AgentLogger.KUBERNETES,'received KUBE_CLUSTER_DN')
            com.manageengine.monagent.kubernetes.SettingsHandler.KubeActions.set_cluster_display_name(dict_responseHeaders[AgentConstants.KUBE_CLUSTER_DN])
        if dict_responseHeaders and AgentConstants.REDISCOVER_KUBE_STATE_METRICS_URL in dict_responseHeaders:
            AgentLogger.log(AgentLogger.KUBERNETES,'received REDISCOVER_KUBE_STATE_METRICS_URL')
            com.manageengine.monagent.kubernetes.KubeGlobal.kubeStateMetricsUrl = None
        if dict_responseHeaders and AgentConstants.INITIATE_AGENT_UPGRADE in dict_responseHeaders:
            AgentLogger.log(AgentLogger.MAIN,' Initiate Agent Upgrade Request Received \n')
            upgrade_dict_props = {}
            if 'up_params' in dict_responseHeaders:
                upgrade_dict_props = json.loads(dict_responseHeaders['up_params'])
            if not AgentConstants.IS_VENV_ACTIVATED: 
                com.manageengine.monagent.upgrade.AgentUpgrader.handleUpgrade(upgrade_dict_props)
            else:
                com.manageengine.monagent.upgrade.AgentUpgrader.handle_venv_upgrade(False,upgrade_dict_props)
        if dict_responseHeaders and AgentConstants.INITIATE_PATCH_UPGRADE in dict_responseHeaders:
            AgentLogger.log(AgentLogger.MAIN,' Initiate Patch Upgrade Request Received \n')
            upgrade_dict_props = {}
            if 'up_params' in dict_responseHeaders:
                upgrade_dict_props = json.loads(dict_responseHeaders['up_params'])
            if not AgentConstants.IS_VENV_ACTIVATED:
                com.manageengine.monagent.upgrade.AgentUpgrader.handleUpgrade(upgrade_dict_props,True)
            else:
                com.manageengine.monagent.upgrade.AgentUpgrader.handle_venv_upgrade(True,upgrade_dict_props)
        if dict_responseHeaders and AgentConstants.GENERATE_RCA in dict_responseHeaders: 
            AgentLogger.log([ AgentLogger.STDOUT,AgentLogger.MAIN], repr(str_invoker)+' : GENERATE_RCA request received in response headers : ' + str(dict_responseHeaders[AgentConstants.GENERATE_RCA])+'\n')
            rcaInfo = com.manageengine.monagent.util.rca.RcaHandler.RcaInfo()
            rcaInfo.requestType = AgentConstants.GENERATE_RCA
            rcaInfo.action = AgentConstants.UPLOAD_RCA
            rcaInfo.downTimeInServer = dict_responseHeaders[AgentConstants.GENERATE_RCA]
            rcaInfo.searchTime = AgentUtil.getCurrentTimeInMillis(float(dict_responseHeaders[AgentConstants.GENERATE_RCA]))
            com.manageengine.monagent.util.rca.RcaHandler.RcaUtil.uploadRca(rcaInfo)
        if dict_responseHeaders and AgentConstants.GENERATE_NETWORK_RCA in dict_responseHeaders:
            AgentLogger.log([ AgentLogger.STDOUT,AgentLogger.MAIN], repr(str_invoker)+' : GENERATE_NETWORK_RCA request received in response headers : ' + str(dict_responseHeaders[AgentConstants.GENERATE_NETWORK_RCA])+'\n')
            rcaInfo = com.manageengine.monagent.util.rca.RcaHandler.RcaInfo()
            rcaInfo.requestType = AgentConstants.GENERATE_NETWORK_RCA
            rcaInfo.action = AgentConstants.UPLOAD_RCA
            rcaInfo.downTimeInServer = dict_responseHeaders[AgentConstants.GENERATE_NETWORK_RCA]
            rcaInfo.searchTime = AgentUtil.getCurrentTimeInMillis(float(dict_responseHeaders[AgentConstants.GENERATE_NETWORK_RCA]))
            com.manageengine.monagent.util.rca.RcaHandler.RcaUtil.uploadRca(rcaInfo)
        if dict_responseHeaders and AgentConstants.SUSPEND_UPLOAD_FLAG in dict_responseHeaders:
            AgentLogger.log(AgentLogger.STDOUT,'Suspend upload flag received from server for [{}]. Hence suspending upload for : [{}] seconds'.format(AgentConstants.AGENT_UPLOAD_PROPERTIES_MAPPER[upload_dir]['name'],str(dict_responseHeaders['SUSPEND_UPLOAD_TIME'])))
            AgentConstants.AGENT_UPLOAD_PROPERTIES_MAPPER[upload_dir]['upload_interval'] = int(dict_responseHeaders['SUSPEND_UPLOAD_TIME'])

        if dict_responseHeaders and AgentConstants.MAX_ZIPS_IN_CURRENT_BUFFER in dict_responseHeaders:
            if AgentConstants.AGENT_UPLOAD_PROPERTIES_MAPPER[upload_dir]['max_zips_current_buffer'] != int(dict_responseHeaders['MAX_ZIPS_IN_CURRENT_BUFFER_COUNT']):
                AgentLogger.log(AgentLogger.STDOUT,'Max zips in current buffer for [{}] changed : [{}] zips'.format(AgentConstants.AGENT_UPLOAD_PROPERTIES_MAPPER[upload_dir]['name'],str(dict_responseHeaders['MAX_ZIPS_IN_CURRENT_BUFFER_COUNT'])))
                AgentConstants.AGENT_UPLOAD_PROPERTIES_MAPPER[upload_dir]['max_zips_current_buffer'] = int(dict_responseHeaders['MAX_ZIPS_IN_CURRENT_BUFFER_COUNT'])

        if dict_responseHeaders and AgentConstants.MAX_ZIPS_IN_FAILED_BUFFER in dict_responseHeaders:
            if AgentConstants.AGENT_UPLOAD_PROPERTIES_MAPPER[upload_dir]['max_zips_failed_buffer'] != int(dict_responseHeaders['MAX_ZIPS_IN_FAILED_BUFFER_COUNT']):
                AgentLogger.log(AgentLogger.STDOUT,'Max zips in failed buffer for [{}] changed : [{}] zips'.format(AgentConstants.AGENT_UPLOAD_PROPERTIES_MAPPER[upload_dir]['name'],str(dict_responseHeaders['MAX_ZIPS_IN_FAILED_BUFFER_COUNT'])))
                AgentConstants.AGENT_UPLOAD_PROPERTIES_MAPPER[upload_dir]['max_zips_failed_buffer'] = int(dict_responseHeaders['MAX_ZIPS_IN_FAILED_BUFFER_COUNT'])

        if dict_responseHeaders and AgentConstants.GROUPED_ZIPS_SLEEP_INTERVAL in dict_responseHeaders:
            if AgentConstants.AGENT_UPLOAD_PROPERTIES_MAPPER[upload_dir]['grouped_zip_upload_interval'] != int(dict_responseHeaders['GROUPED_ZIPS_SLEEP_INTERVAL_TIME']):
                AgentLogger.log(AgentLogger.STDOUT,'Grouped zips upload delay interval for [{}] received : [{}] seconds'.format(AgentConstants.AGENT_UPLOAD_PROPERTIES_MAPPER[upload_dir]['name'],str(dict_responseHeaders['GROUPED_ZIPS_SLEEP_INTERVAL_TIME'])))
                AgentConstants.AGENT_UPLOAD_PROPERTIES_MAPPER[upload_dir]['grouped_zip_upload_interval'] = int(dict_responseHeaders['GROUPED_ZIPS_SLEEP_INTERVAL_TIME'])

        if dict_responseHeaders and AgentConstants.PEER_VALIDATE in dict_responseHeaders:
            AgentLogger.log(AgentLogger.PING,repr(str_invoker)+' : PEER VALIDATION ')
            com.manageengine.monagent.network.AgentPingHandler.PingUtil.handlePeerRequest(dict_responseData, AgentConstants.PEER_VALIDATE)
        if dict_responseHeaders and AgentConstants.PEER_SCHEDULE in dict_responseHeaders:
            AgentLogger.log(AgentLogger.PING,repr(str_invoker)+' : PEER SCHEDULE')
            com.manageengine.monagent.network.AgentPingHandler.PingUtil.handlePeerRequest(dict_responseData, AgentConstants.PEER_SCHEDULE)
        if dict_responseHeaders and AgentConstants.UPDATE_AGENT_KEY in dict_responseHeaders:
            AgentLogger.log(AgentLogger.STDOUT,' update agent key header received ')
            dict_data={}
            dict_data['AGENTKEY']=dict_responseHeaders[AgentConstants.UPDATE_AGENT_KEY]
            AgentUtil.updateKeys(dict_data)
        if dict_responseHeaders and AgentConstants.UPDATE_DEVICE_KEY in dict_responseHeaders:
            AgentLogger.log(AgentLogger.STDOUT,' update device key received ')
            dict_data={}
            dict_data['DEVICEKEY']=dict_responseHeaders[AgentConstants.UPDATE_DEVICE_KEY]
            AgentUtil.updateKeys(dict_data)
        if dict_responseHeaders and 'HADOOP_STOP_DC_FOR_NODES' in dict_responseHeaders:
            AgentLogger.log(AgentLogger.APPS,'skip dc nodes list :: {}'.format(dict_responseData))
            dict_responseData = json.loads(dict_responseData)
            stop_dc_nodes  = dict_responseData['HADOOP_STOP_DC_FOR_NODES']
            if AppConstants.skip_dc_for_nodes:
                AppConstants.skip_dc_for_nodes.extend(stop_dc_nodes)
            else:
                AppConstants.skip_dc_for_nodes = stop_dc_nodes
        if dict_responseHeaders and 'node_count' in dict_responseHeaders:
            AgentConstants.NODE_COUNT_IN_DC = int(dict_responseHeaders['node_count'])
        if dict_responseHeaders and 'skip_standby_nodes' in dict_responseHeaders:
            skip_nodes = dict_responseHeaders['skip_standby_nodes']
            if skip_nodes:
                AgentConstants.SKIP_STANDBY_NODES.add(skip_nodes)
        if dict_responseHeaders and 'allow_standby_nodes' in dict_responseHeaders:
            allowed_nodes = dict_responseHeaders['allow_standby_nodes']
            if allowed_nodes in AgentConstants.SKIP_STANDBY_NODES:
                AgentConstants.SKIP_STANDBY_NODES.pop(allowed_nodes)
        if dict_responseHeaders and AgentConstants.HADOOP_DATA_COLLECTOR_REPONSE in dict_responseHeaders :
            AgentLogger.log(AgentLogger.APPS,'response data dict :: {}'.format(dict_responseData))
            dict_parsed_data = json.loads(dict_responseData)
            app_id_dict = dict_parsed_data[AgentConstants.HADOOP_DATA_COLLECTOR_REPONSE]
            for key , value in app_id_dict.items():
                com.manageengine.monagent.util.AppUtil.update_app_id(key, value)
            com.manageengine.monagent.util.AppUtil.read_app_id()        
        if dict_responseHeaders and AgentConstants.AS in dict_responseHeaders:
            server_settings_json = dict_responseData
            if type(server_settings_json) == str:
                settings_from_server = json.loads(server_settings_json)
            else:
                settings_from_server = server_settings_json
            settings_handler.update_settings(settings_from_server)
        if dict_responseHeaders and AgentConstants.UPDATE_STATSD_CONFIG in dict_responseHeaders:
            statsd_config = dict_responseHeaders.get(AgentConstants.UPDATE_STATSD_CONFIG,None)
            statsd_config = json.loads(statsd_config)
            AgentLogger.log(AgentLogger.STDOUT,'statsd configuration :: {}'.format(statsd_config))
            MetricsUtil.statsd_util_obj.update_statsd_config(statsd_config)
        if dict_responseHeaders and "dms_primary_domain" in dict_responseHeaders:
            AgentConstants.DMS_PRIMARY_WS_HOST = dict_responseHeaders['dms_primary_domain']
        if dict_responseHeaders and "dms_secondary_domain" in dict_responseHeaders:
            AgentConstants.DMS_SECONDARY_WS_HOST = dict_responseHeaders['dms_secondary_domain']
        if dict_responseHeaders and "SUS_TIMEOUT" in dict_responseHeaders:
            AgentConstants.STATUS_UPDATE_TIMEOUT = int(dict_responseHeaders["SUS_TIMEOUT"])
            AgentLogger.log(AgentLogger.STDOUT,'status update timeout header received :: {}'.format(AgentConstants.STATUS_UPDATE_TIMEOUT))
        if dict_responseHeaders and "SUS_INTERVAL" in dict_responseHeaders:
            AgentConstants.STATUS_UPDATE_INTERVAL = int(dict_responseHeaders["SUS_INTERVAL"])
            AgentLogger.log(AgentLogger.STDOUT,'status update interval header received :: {}'.format(AgentConstants.STATUS_UPDATE_INTERVAL))
        if dict_responseHeaders and AgentConstants.SET_EVENTS_ENABLED in dict_responseHeaders:
            AgentLogger.log(AgentLogger.KUBERNETES,"Received EVENTS_ENABLED settings {}".format(dict_responseHeaders[AgentConstants.SET_EVENTS_ENABLED]))
            com.manageengine.monagent.kubernetes.SettingsHandler.KubeActions.set_event_settings(str(dict_responseHeaders[AgentConstants.SET_EVENTS_ENABLED]))
        if dict_responseHeaders and "ENABLE_MONITOR" in dict_responseHeaders:
            monitor = dict_responseHeaders["ENABLE_MONITOR"]
            AgentUtil.edit_monitorsgroup(monitor, 'enable')
            AgentLogger.log(AgentLogger.STDOUT,'ENABLE_MONITOR header received for the monitor:: {}'.format(monitor))
        if dict_responseHeaders and "DISABLE_MONITOR" in dict_responseHeaders:
            monitor = dict_responseHeaders["DISABLE_MONITOR"]
            AgentUtil.edit_monitorsgroup(monitor, 'disable')
            AgentLogger.log(AgentLogger.STDOUT,'DISABLE_MONITOR header received for the monitor:: {}'.format(monitor))
        if dict_responseHeaders and "INITIATE_CLUSTER_AGENT_UPGRADE" in dict_responseHeaders:
            com.manageengine.monagent.kubernetes.ClusterAgent.ClusterAgentUtil.upgrade_cluster_agent()
        if dict_responseHeaders and "RESOURCE_DISCOVERY_CONFIG" in dict_responseHeaders and dict_responseData:
            AgentLogger.log(AgentLogger.STDOUT,'RESOURCE_DISCOVERY_CONFIG sent from server : {}'.format(str(dict_responseData)))
            if type(dict_responseData) == str:
                dict_responseData = json.loads(dict_responseData)
            com.manageengine.monagent.kubernetes.KubeUtil.update_instant_discovery_config(dict_responseData)
    except Exception as e:
        AgentLogger.log([AgentLogger.CRITICAL,AgentLogger.STDOUT], ' *************************** Exception while handling response headers *************************** '+ repr(e))
        traceback.print_exc()
        bool_isSuccess = False
    return bool_isSuccess
        
def getConsolidatedWMSData(action=AgentConstants.TEST_PING):
    try:
        str_url = None
        dict_requestParameters={}
        dict_requestParameters['agentKey'] = AgentUtil.AGENT_CONFIG.get('AGENT_INFO', 'agent_key')
        dict_requestParameters['custID'] = AgentConstants.CUSTOMER_ID
        dict_requestParameters['action'] = action
        dict_requestParameters['bno'] = AgentConstants.AGENT_VERSION
        str_servlet = AgentConstants.WMS_SERVLET
        if not dict_requestParameters == None:
            str_requestParameters = urlencode(dict_requestParameters)
            str_url = str_servlet + str_requestParameters
        requestInfo = RequestInfo()
        requestInfo.set_loggerName(AgentLogger.STDOUT)
        requestInfo.set_method(AgentConstants.HTTP_POST)
        requestInfo.set_url(str_url)
        requestInfo.add_header("Content-Type", 'application/json')
        requestInfo.add_header("Accept", "text/plain")
        requestInfo.add_header("Connection", 'close')
        requestInfo.set_timeout(15)
        (bool_isSuccess, errorCode, dict_responseHeaders, dict_responseData) = sendRequest(requestInfo)
        if action == AgentConstants.GCR:
            com.manageengine.monagent.communication.AgentStatusHandler.WMS_THREAD.action=AgentConstants.TEST_PING
        if errorCode != 0:
            com.manageengine.monagent.communication.AgentStatusHandler.WMS_THREAD.pause()
        else:
            com.manageengine.monagent.communication.AgentStatusHandler.WMS_INTERVAL=15
            header_needed_value = "TIME_TO_WAIT" if AgentConstants.PYTHON_VERSION == 3 else "time_to_wait"
            if header_needed_value in dict_responseHeaders and str(dict_responseHeaders[header_needed_value]) != '-1':
                 com.manageengine.monagent.communication.AgentStatusHandler.WMS_INTERVAL=int(dict_responseHeaders[header_needed_value])
            else:
                 com.manageengine.monagent.communication.AgentStatusHandler.WMS_THREAD.pause()
            if dict_responseHeaders:
                handleResponseData(dict_responseHeaders,dict_responseData,'GET_CONSOLIDATED_REQUESTS')
    except Exception as e:
        AgentLogger.log(AgentLogger.MAIN,' Exception in get consolidated wms')
        traceback.print_exc()

#Parse WMS failed requests data here
def handleResponseData(dict_responseHeaders,dict_responseData,str_invoker):
    from com.manageengine.monagent import AgentConstants
    try:
        header_needed_value = "CONSOLIDATED_REQUESTS" if AgentConstants.PYTHON_VERSION == 3 else "consolidated_requests"
        if header_needed_value in dict_responseHeaders and dict_responseData:
            listFailedReq = dict_responseData if type(dict_responseData) is dict else json.loads(dict_responseData)
            com.manageengine.monagent.communication.DMSHandler.processTasks(listFailedReq)
    except Exception as e:
        AgentLogger.log([AgentLogger.STDERR], ' *************************** Exception while consolidating WMS Response Data *************************** '+str_invoker+ repr(e))
        traceback.print_exc()

@synchronized
def downloadFile(str_downloadUrl, str_destinationFilePath,**arguments):
    bool_isSuccess = True
    str_host = str(SERVER_INFO.get_host()) if 'host' not in arguments else arguments['host']
    str_loggerName = AgentLogger.STDOUT if 'logger' not in arguments else arguments['logger']
    checksum = None if 'checksum' not in arguments else arguments['checksum']
    ack_dict = None if 'ack' not in arguments else arguments['ack']
    return_all_params = False if 'return_all_params' not in arguments else arguments['return_all_params'] 
    str_port = str(SERVER_INFO.get_port()) if 'port' not in arguments else arguments['port']
    protocol = str(SERVER_INFO.get_protocol()) if 'protocol' not in arguments else arguments['protocol']
#     if checksum == None:
#         ack_dict['err']='Checksum not found'
#         data={'ack':ack_dict}
#         com.manageengine.monagent.actions.checksum_validator.upload_data_for_validation(data,"ack")
    try:
        requestInfo = RequestInfo()
        requestInfo.set_loggerName(str_loggerName)
        requestInfo.set_method(AgentConstants.HTTP_GET)
        requestInfo.add_header('Connection', 'close')
        requestInfo.set_host(str_host)
        requestInfo.set_port(str_port)
        requestInfo.set_url(str_downloadUrl)    
        requestInfo.set_responseAction(saveFile)
        requestInfo.add_custom_param('download_file_path',str_destinationFilePath)
        if str_host==AgentConstants.STATIC_SERVER_HOST:
            requestInfo.set_port(AgentConstants.URL_HTTPS_PORT)
        bool_isSuccess, int_errorCode, dict_responseHeaders, dict_responseData = sendRequest(requestInfo)
        if bool_isSuccess:
            if checksum:
                bool_isSuccess,actual_checksum = AgentUtil.file_hash_util.verify_hash(checksum,str_destinationFilePath)
                if not bool_isSuccess:
                    AgentLogger.log(str_loggerName,'Check Sum Failure')
                    AgentConstants.WATCHDOG_UPGRADE_MSG = AgentConstants.WATCHDOG_UPGRADE_MSG + "cksm-0|"
                    if ack_dict:
                        ack_dict['msg']=AgentConstants.CHECKSUM_MISMATCH
                        ack_dict['expected']=checksum
                        ack_dict['actual']=actual_checksum
                        data={'ack':ack_dict}
                        com.manageengine.monagent.actions.checksum_validator.upload_data_for_validation(data,"ack")
                    FileUtil.deleteFile(str_destinationFilePath)
        if return_all_params:
            return bool_isSuccess,int_errorCode,dict_responseHeaders,dict_responseData
    except Exception as e:
        AgentLogger.log(str_loggerName, 'FILE DOWNLOAD : *************************** Exception While Downloading File From The Location :'+repr(str_downloadUrl)+' *************************** '+ repr(e))
        traceback.print_exc()
        bool_isSuccess = False
    return bool_isSuccess

def downloadCustomFile(str_servlet, str_destinationFilePath,**arguments):
    bool_isSuccess = True
    dict_requestParameters = {}
    str_url = None
    str_loggerName = AgentLogger.STDOUT if 'logger' not in arguments else arguments['logger']
    checksum = None if 'checksum' not in arguments else arguments['checksum']
    ack_dict = None if 'ack' not in arguments else arguments['ack']
#     if checksum == None:
#         ack_dict['err']='Checksum not found'
#         data={'ack':ack_dict}
#         com.manageengine.monagent.actions.checksum_validator.upload_data_for_validation(data,"ack")
#         return
    try:
        if AgentConstants.IS_VENV_ACTIVATED is True:
            dict_requestParameters["t"] = "HybridAgent"
        elif AgentConstants.OS_NAME == AgentConstants.FREEBSD_OS:
            dict_requestParameters['t'] = 'FreeBSD'
        elif AgentConstants.OS_NAME == AgentConstants.LINUX_OS:
            dict_requestParameters['t'] = 'LINUX'
        else:
            dict_requestParameters['t'] = 'OSX'
        dict_requestParameters['custID'] = AgentConstants.CUSTOMER_ID
        if not dict_requestParameters == None:
            str_requestParameters = urlencode(dict_requestParameters)
            str_url = str_servlet + str_requestParameters
        AgentLogger.log(str_loggerName, 'CUSTOM FILE DOWNLOAD from : ' + str_url + ' initiated' )
        requestInfo = RequestInfo()
        requestInfo.set_loggerName(str_loggerName)
        requestInfo.set_method(AgentConstants.HTTP_GET)        
        requestInfo.add_header('Connection', 'close')
        requestInfo.set_url(str_url)    
        requestInfo.set_responseAction(saveFile)
        requestInfo.add_custom_param('download_file_path', str_destinationFilePath)
        bool_isSuccess, int_errorCode, dict_responseHeaders, dict_responseData = sendRequest(requestInfo)
        if bool_isSuccess:
            if checksum:
                bool_isSuccess,actual_checksum = AgentUtil.file_hash_util.verify_hash(checksum,str_destinationFilePath)
                if not bool_isSuccess:
                    AgentLogger.log(str_loggerName,'Check Sum Failure')
                    if ack_dict:
                        ack_dict['msg']=AgentConstants.CHECKSUM_MISMATCH
                        ack_dict['expected']=checksum
                        ack_dict['actual']=actual_checksum
                        data={'ack':ack_dict}
                        com.manageengine.monagent.actions.checksum_validator.upload_data_for_validation(data,"ack")
                        FileUtil.deleteFile(str_destinationFilePath)
    except Exception as e:
        AgentLogger.log(str_loggerName, 'FILE DOWNLOAD : *************************** Exception While Downloading File From The Location :'+repr(str_url)+' *************************** '+ repr(e))
        traceback.print_exc()
        bool_isSuccess = False
    return bool_isSuccess

def saveFile(requestInfo, str_responseData):
    bool_success = True
    file_obj = None
    AgentLogger.log(requestInfo.get_loggerName(), 'Saving file from the server to the path '+repr(requestInfo.get_custom_params()['download_file_path']))
    try:            
        file_obj = open(requestInfo.get_custom_params()['download_file_path'],'wb')
        file_obj.write(str_responseData)
    except Exception as e:
        AgentLogger.log(requestInfo.get_loggerName(), 'FILE DOWNLOAD : *************************** Exception While Saving The File To The Path:'+repr(requestInfo.get_custom_params()['download_file_path'])+' *************************** '+ repr(e))
        traceback.print_exc()
        bool_success = False
    finally:
        if not file_obj == None:
            file_obj.close()
    return bool_success

def download_from_url(url,file_path,str_loggerName):
    bool_isSuccess = False
    try:
        from six.moves.urllib.parse import urlparse
        parsed = urlparse(url)
        requestInfo = RequestInfo()
        requestInfo.set_loggerName(str_loggerName)
        requestInfo.set_method(AgentConstants.HTTP_GET)        
        requestInfo.add_header('Connection', 'close')
        requestInfo.set_protocol(parsed.scheme)
        requestInfo.set_host(parsed.hostname)
        if parsed.port:
            requestInfo.set_port(parsed.port)
        else:
            requestInfo.set_port(AgentConstants.URL_HTTPS_PORT)
        requestInfo.set_url(parsed.path)    
        requestInfo.set_responseAction(saveFile)
        requestInfo.add_custom_param('download_file_path', file_path)
        bool_isSuccess, int_errorCode, dict_responseHeaders, dict_responseData = sendRequest(requestInfo)
    except Exception as e:
        traceback.print_exc()
    return bool_isSuccess,int_errorCode

#Sends Request to an URL Without Port
def send_request_to_url(url,data=None,headers={},method="GET"):
    resp_data=None
    bool_success = False
    try:
        AgentLogger.log(AgentLogger.STDOUT,"url -- {}".format(url))
        request_obj = urlconnection.Request(url,data,headers,method=method)
        response = urlconnection.urlopen(request_obj,timeout=3,cafile=AgentConstants.CA_CERT_FILE,capath=AgentConstants.CA_CERT_PATH)
        resp_data = response.read()
        resp_data = resp_data.decode('UTF-8')
        resp_data = json.loads(resp_data)
        bool_success = True
    except Exception as e:
        traceback.print_exc()
        AgentLogger.log(AgentLogger.STDOUT,'unable to connect :: '+repr(e)+"\n")
    return bool_success,resp_data


