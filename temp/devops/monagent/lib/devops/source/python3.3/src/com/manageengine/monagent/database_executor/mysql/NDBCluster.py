'''
Created on 21-Mar-2023

@author: arjun
'''


import sys,json,subprocess,socket,re,traceback,time,os
import xml.etree.ElementTree as ET

if "com.manageengine.monagent.util.DatabaseUtil" in sys.modules:
    DatabaseUtil = sys.modules["com.manageengine.monagent.util.DatabaseUtil"]
else:
    from com.manageengine.monagent.util import DatabaseUtil

try:
    from com.manageengine.monagent.database_executor.mysql                      import mysql_monitoring
except:
    mysql_monitoring    =   sys.modules["com.manageengine.monagent.database_executor.mysql.mysql_monitoring"]

from com.manageengine.monagent                                              import AgentConstants
from com.manageengine.monagent.logger                                       import AgentLogger
from com.manageengine.monagent.security                                     import AgentCrypt
from com.manageengine.monagent.discovery                                    import discovery_util
from com.manageengine.monagent.scheduler                                    import AgentScheduler
from com.manageengine.monagent.database.XMLExecutor                         import Executor
from com.manageengine.monagent.database                                     import DatabaseLogger, DBConstants, DatabaseExecutor
# from com.manageengine.monagent.database_executor.mysql                      import mysql_monitoring
from com.manageengine.monagent.util                                         import AgentUtil

try:
    import pymysql
    AgentConstants.PYMYSQL_MODULE='1'
except Exception as e:
    AgentLogger.log([AgentLogger.DATABASE, AgentLogger.STDERR], "can't import pymysql")
    traceback.print_exc()

# 1. Registration
#       -> Register NDB Cluster with APPLICATION_DISCOVERY_SERVLET and store monitor_id in mysql.cfg file.
#       -> Register each node with CHILD_DISCOVERY_SERVLET and store monitor_id in-memory.
# 2. Data Collection
#       -> Start Data Collection after getting PERF_NODE_UPDATE or perfNode from HeaderResponse.
# 3. Write to file
#       ->


def child_rediscover(dict_task):
    try:
        if 'MONITOR_ID' in dict_task:
            if dict_task.get('mid'):
                ndb_config_dict = getNDBConfig()
                for section_name,section in ndb_config_dict.items():
                    # if section.get("mysqlNDBmonkey")==dict_task["mid"] and section.get("NDB_status") == "0":
                    if section.get("mysqlNDBmonkey")==dict_task["mid"]:
                        SendChildNodesRegistrationRequest(section)
        AgentLogger.log(AgentLogger.DATABASE,'received child_rediscover request for NDB Cluster :: mid - {}'.format(dict_task.get('mid')))
    except Exception as e:
        AgentLogger.log(AgentLogger.DATABASE,'child_rediscover :: Error - {}'.format(e))
        traceback.print_exc()
    finally:
        return None

# sends GET request to get monitor id for ndb cluster
def AppRegistrationRequest(dict_params, config, instance_name, request_params,rediscover=False):
    try:
        version,__params    =   FetchDiscoveryData(dict_params)
        sql_node            =   getCurrentApiNode(dict_params)
        if version and __params and sql_node:
            __params["sql_node"]    =   sql_node
            if rediscover:
                ndb_system_name =   config.get(instance_name,"ndb_system_name")
                if ndb_system_name and ndb_system_name!=__params.get("ndb_system_name"):
                    # __params["old_ndb_system_name"] =   ndb_system_name
                    config.set(instance_name,"ndb_system_name_old",ndb_system_name)
            
            config.set(instance_name, "ndb_system_name", __params["ndb_system_name"])
            config.set(instance_name, "NDB_version", str(version))
            config.set(instance_name, "NDB_current_node", str(sql_node))

            request_params.update(__params)

            DBConstants.NDB_REGISTRATION_TAKES_PLACE=[config.get(instance_name,"ndb_system_name")]

        AgentLogger.log(AgentLogger.DATABASE, "NDB APP Discovery request sent - {}".format(__params))
    except Exception as e:
        DatabaseLogger.log( DatabaseLogger.MAIN, "Exception while registering NDB Cluster monitor Param - {}\n Error - {}".format( dict_params, e ) )
        traceback.print_exc()

# receives MID for ndb cluster from APPLICATION DISCOVERY response
def AppRegistrationResponse(responseHeader, responseData, config, instance_name):
    try:
        config.set(instance_name, "mysqlNDBmonkey", responseHeader["mysqlNDBmonkey"])

        perf_pollinterval       =   responseHeader.get("NDB_perf_pollinterval")     or  "300"
        conf_pollinterval       =   responseHeader.get("NDB_conf_pollinterval")     or  "180"
        one_day_pollinterval    =   responseHeader.get("NDB_one_day_pollinterval")  or  "86400"
        collection_config       =   responseHeader.get("NDB_disabled_queries")     or  "{}"

        NDB_enabled             =   "true"  if str(responseHeader.get("perfNode")).lower()=="true" else "false"
        status                  =   "5"     if responseHeader.get("SUSPEND_MONITORING") == "TRUE" else "0"

        config.set(instance_name, "NDB_disabled_queries",    str(collection_config))
        config.set(instance_name, "NDB_perf_pollinterval",    str(perf_pollinterval))
        config.set(instance_name, "NDB_conf_pollinterval",    str(conf_pollinterval))
        config.set(instance_name, "NDB_one_day_pollinterval", str(one_day_pollinterval))
        config.set(instance_name, "NDB_status",               status)
        config.set(instance_name, "NDB_enabled",              NDB_enabled)

        AgentLogger.log(AgentLogger.DATABASE,"NDB APP Discovery response received successfully. \n responseHeader - {}\n instance_name - {}".format(responseHeader, instance_name))

        if DBConstants.NDB_REGISTRATION_TAKES_PLACE:
            DBConstants.NDB_REGISTRATION_TAKES_PLACE   =   None
    except Exception as e:
        DatabaseLogger.log( DatabaseLogger.MAIN, "NDB - AppRegistrationResponse {}".format(e))

# register Child Monitor ID for each node
def SendChildNodesRegistrationRequest(dict_params):
    try:
        __requests = FetchChildNodeDiscoveryData(dict_params)
        for i,requestBody in enumerate(__requests):
            # requestBody["pagenumber"]=i+1
            discovery_util.post_discovery_result(requestBody,AgentConstants.AGENT_UPLOAD_PROPERTIES_MAPPER['013'],"CHILD_DISCOVERY")

        AgentLogger.log(AgentLogger.DATABASE,"NDB Cluster - child Discovery requests - {}".format(__requests))
    except Exception as e:
        AgentLogger.log(AgentLogger.DATABASE," SendChildNodesRegistrationRequest - {}".format(e))

# converts header response dict to loopable version dict for checking new config with mysql.cfg file contents
def childNodesConfigFormatter(child_nodes_config):
    try:
        new_config={}

        for key,value in child_nodes_config.items():
            uniqueID=value["mid"]
            new_config[uniqueID] = {"mysqlNDBmonkey":uniqueID}

            if "child_keys" in value and "MYSQLNDB_NODE" in value["child_keys"] and value.get("status") not in ["3","5"]:
                new_config[uniqueID]['child_keys'] = value["child_keys"]["MYSQLNDB_NODE"]

            for property_name in ["NDB_perf_pollinterval","NDB_conf_pollinterval","NDB_one_day_pollinterval","status","NDB_disabled_queries"]:
                if property_name in value:
                    new_config[uniqueID][property_name]=str(value[property_name])

            if DBConstants.NDB_REGISTRATION_TAKES_PLACE and DBConstants.NDB_REGISTRATION_TAKES_PLACE[0]==key:
                if DBConstants.NDB_CID_MAPPER.get(uniqueID)==None and uniqueID in new_config and 'child_keys' in new_config[uniqueID]:
                    DBConstants.NDB_CID_MAPPER[uniqueID]=new_config[uniqueID]['child_keys']

        AgentLogger.log(AgentLogger.DATABASE,"childNodesConfigFormatter - NDB_REGISTRATION_TAKES_PLACE - {}".format(DBConstants.NDB_REGISTRATION_TAKES_PLACE))
        
        return new_config
    except Exception as e:
        AgentLogger.log(AgentLogger.DATABASE,"Error :: childNodesConfigFormatter - {}".format(e))
        return {}

# Starts DC after obtaining cid's for Nodes(API,MGM,NDB) from update config response
# Also Updates Configuration for NDB Cluster module 
def UpdateConfigForNDB(child_nodes_config):
    try:
        persist         = False
        new_config      = childNodesConfigFormatter(child_nodes_config) 

        conf_file       = AgentConstants.DB_CONSTANTS[AgentConstants.MYSQL_DB]['CONF_FILE']
        MYSQL_CONFIG    = DatabaseUtil.get_config_parser(conf_file)
        #MYSQL_CONFIG   = DatabaseUtil.MYSQL_CONFIG

        AgentLogger.log(AgentLogger.DATABASE,"Received UpdateConfig for NDB ")
        for section_name, section in MYSQL_CONFIG.items():
            uniqueID = section.get("mysqlNDBmonkey")

            if section_name in ["DEFAULT","MYSQL"] and uniqueID == None or uniqueID not in new_config:
                continue

            AgentLogger.log(AgentLogger.DATABASE,"section_name - {}\tmysqlNDBmonkey - {}".format(section_name,uniqueID))

            if "child_keys" in new_config[uniqueID]:
                DBConstants.NDB_CID_MAPPER[uniqueID]=new_config[uniqueID]["child_keys"]

            if "status" in new_config[uniqueID] and section.get("NDB_status") != new_config[uniqueID]["status"]:
                persist = True
                section.update({"NDB_status": new_config[uniqueID]["status"]})

            for property_name in ["NDB_perf_pollinterval","NDB_conf_pollinterval","NDB_one_day_pollinterval","NDB_disabled_queries"]:
                if property_name in new_config[uniqueID] and new_config[uniqueID][property_name]!=section.get(property_name):
                    persist=True
                    section.update({property_name:new_config[uniqueID][property_name]})

        if persist:
            DatabaseUtil.persist_config_parser(conf_file, MYSQL_CONFIG)
            mysql_monitoring.start_mysql_data_collection()
        AgentLogger.log(AgentLogger.DATABASE,"child Discovery response - from response header - {}".format(child_nodes_config))
        AgentLogger.log(AgentLogger.DATABASE,"new config - {}".format(new_config))
      
    except Exception as e:
        AgentLogger.log(AgentLogger.DATABASE,"UpdateConfigForNDB: config param - {} :: Exception - {} :: traceback - {}".format(child_nodes_config, e, traceback.print_exc()))

# Toggles DC of a API node in NDBCluster according to the signal received from the server.
def enableInstance(dict_task):
    try:
        AgentLogger.log(AgentLogger.DATABASE,"NDBCluster :: DC enabled/disable update for this instance - perfNode - {}".format(dict_task.get('perfNode')))
        perfNode    =   str(dict_task.get('perfNode')).lower()
        if perfNode in ['true','false']:
            # mysql_config = DatabaseUtil.get_config_parser(AgentConstants.MYSQL_CONF_FILE)
            mysql_config = DatabaseUtil.MYSQL_CONFIG
            enabled_NDB_Clusters={}
            for section_name, section in mysql_config.items():
                if section.get('NDB_enabled') == "true":
                    section.update({"NDB_enabled":"false"})
                if perfNode=="true" and section.get('NDB_enabled') == "false" and enabled_NDB_Clusters.get(section.get('mysqlNDBmonkkey'))==None:
                    section.update({"NDB_enabled":"true"})
                    enabled_NDB_Clusters.update({section.get("mysqlNDBmonkey"):""})
            DatabaseUtil.persist_config_parser(AgentConstants.DB_CONSTANTS[AgentConstants.MYSQL_DB]['CONF_FILE'], mysql_config)
            # initialize()
            mysql_monitoring.start_mysql_data_collection()
    except Exception as e:
        AgentLogger.log(AgentLogger.DATABASE,"enableInstance - {} \nException - {}".format(dict_task, traceback.print_exc()))

# Used to activate NDBCluster Monitoring.
def activateNDBClusterMonitoring(newConfig):
    try:
        toggleNDBStatus(newConfig.get("mid"),"0")
        AgentLogger.log(AgentLogger.DATABASE,"received activate monitor request for ndb - new config - {}".format(newConfig))
    except Exception as e:
        AgentLogger.log(AgentLogger.DATABASE," activateNDBClusterMonitoring   -   newConfig - {} \nException - {}".format(newConfig, e))

def toggleNDBStatus(mid,status_code):
    try:
        if mid:
            # mysql_config = DatabaseUtil.get_config_parser(AgentConstants.MYSQL_CONF_FILE)
            mysql_config = DatabaseUtil.MYSQL_CONFIG
            persist=False
            for section_name,section in mysql_config.items():
                if mid==section.get("mysqlNDBmonkey"):
                    persist=True
                    if status_code=="0":
                        SendChildNodesRegistrationRequest(getNDBSingleSectionConfig(section))
                    else:
                        deleteScheduleWithMID(section.get("mysqlNDBmonkey"))
                    section.update({"NDB_status":status_code})
                    break

            if persist:
                DatabaseUtil.persist_config_parser(AgentConstants.DB_CONSTANTS[AgentConstants.MYSQL_DB]['CONF_FILE'],mysql_config)
                mysql_monitoring.start_mysql_data_collection()
    except Exception as e:
        AgentLogger.log(AgentLogger.DATABASE,"toggleNDBStatus - mid - {} \nException - {}".format(mid, e))

def suspendNDBClusterMonitoring(newConfig):
    try:
        toggleNDBStatus(newConfig.get("mid"),"5")
        AgentLogger.log(AgentLogger.DATABASE,"received suspend monitor request for ndb - newConfig - {}".format(newConfig))
    except Exception as e:
        AgentLogger.log(AgentLogger.DATABASE,"suspendNDBClusterMonitoring - newConfig - {} \nException - {}".format(newConfig, e))

# save perf data to file
def savePerf(output):
    try:
        if output:
            for part in output:
                dir_prop = AgentConstants.AGENT_UPLOAD_PROPERTIES_MAPPER['012']
                status,file_path=DatabaseUtil.save_database_data(part,dir_prop,"MYSQLNDB")
                AgentLogger.log(AgentLogger.DATABASE, "save perf - persist part - status - {} file path - {}".format(status,file_path))
    except Exception as e:
        AgentLogger.log(AgentLogger.DATABASE," savePerf - {}".format(e))

# Directly post configuration data to server
def saveConf(args):
    try:
        output,__type=args
        if output:
            discovery_util.post_discovery_result(output,AgentConstants.AGENT_UPLOAD_PROPERTIES_MAPPER['014'],__type)
            AgentLogger.log(AgentLogger.DATABASE, "posted to ClusterConfigSevlet for type - {}".format(__type))
    except Exception as e:
        AgentLogger.log(AgentLogger.DATABASE,"saveConf :: output - {} \nException - {}".format(args, e))

def getNDBSingleSectionConfig(section):
    try:
        __section_dict = {}
        for k, v in section.items():
            __section_dict[k] = v
        
        if __section_dict.get("encrypted.password"):
            __section_dict["password"] = str(AgentCrypt.decrypt_with_ss_key(__section_dict["encrypted.password"]))
        
        return __section_dict
    except Exception as e:
        AgentLogger.log(AgentLogger.DATABASE," getNDBSingleSectionConfig -> {}".format(e))
    

# Loads NDB Cluster Config as dict from MYSQL_CONFIG
def getNDBConfig():
    try:
        # mysql_config = DatabaseUtil.get_config_parser(AgentConstants.MYSQL_CONF_FILE)
        mysql_config = DatabaseUtil.MYSQL_CONFIG
        NDBCONFIG = {}
        for section_name, section in mysql_config.items():
            if section_name in ["DEFAULT","MYSQL"]:
                continue
            if section.get("NDB_status")!=None:
                tmp = getNDBSingleSectionConfig(section)
                if tmp:
                    NDBCONFIG[section_name]=tmp
        return NDBCONFIG
    except Exception as e:
        AgentLogger.log(AgentLogger.DATABASE," getNDBConfig -> {} ".format(e))

def deleteScheduleWithMID(mid):
    try:
        types = ["_ndb_perf", "_ndb_conf", "_ndb_child_discovery"]
        for suffix in types:
            deleteSingleScheduleWithMID(mid+suffix)
    except Exception as e:
        AgentLogger.log(AgentLogger.DATABASE," Exception :: deleteScheduleWithMID :: task_name -> {} Exception -> {}".format(mid, e))


def deleteSingleScheduleWithMID(task_name):
    try:
        tmp = AgentConstants.DATABASE_OBJECT_MAPPER['mysql'].get(task_name)
        if tmp:
            AgentScheduler.deleteSchedule(tmp)
            AgentConstants.DATABASE_OBJECT_MAPPER['mysql'].pop(task_name)
            AgentLogger.log(AgentLogger.DATABASE,"removed schedule with task_name for ndb - {}".format(task_name))
    except Exception as e:
        AgentLogger.log(AgentLogger.DATABASE," Exception :: deleteSingleScheduleWithMID :: task_name -> {} Exception -> {}".format(task_name, e))

# returns the node_name of API node. 
def getCurrentApiNode(dict_params):
    try:
        connectionStatus,connection         =   DatabaseUtil.getDBConnection(dict_params, AgentConstants.MYSQL_DB)
        # hostname                            =   socket.gethostbyname_ex(dict_params['host'])[2]
        hostname                            =   getAllIPAddressesOfHost("-4") or []
        if connectionStatus:
            output                          =   getOutputFromQuery(connection,DBConstants.NDBDiscoveryCurrentAPINodeQuery)
            for row in output:
                if socket.gethostbyname(row[1]) in hostname:
                    return row[0]
    except Exception as e:
        AgentLogger.log(AgentLogger.DATABASE,"Exception :: getCurrentApiNode -> {} hostname -> {} ".format(e,hostname))

# All IPv4,IPv6 addresses of this server and pid of the NDB,MGM,API nodes are needed in order to map NDBCluster Nodes to server monitors in server side.
# returns data which is used for mapping NDB,MGM,API nodes to server monitors
def getNodeDiscovery(params=None):
    try:
        result,nodes    =   None,[]
        # ips=socket.gethostbyname_ex(socket.gethostname())[2]
        ips             =   getAllIPAddressesOfHost()
        send_API        =   False

        for section_name,section in DatabaseUtil.MYSQL_CONFIG.items():
            if section.get("NDB_enabled") != None:
                send_API    =   True
                break

        _mapper         =   {"NDB":"ndbd","MGM":"ndb_mgmd"}
        if send_API:
            _mapper.update({"API":"mysqld"})

        for key,val in _mapper.items():
            pid =   getPID(val)
            if pid:
                nodes.append({"node_type":key,"pid":pid,"ips":ips})
        if nodes:
            result  =   {"NDB_DISCOVERY":nodes}
        AgentLogger.log(AgentLogger.DATABASE," getNodeDiscovery :: NDB_DISCOVERY - {}".format(result))
    except Exception as e:
        AgentLogger.log(AgentLogger.DATABASE," Exception :: getNodeDiscovery -> {}".format(e))
    return result,"NDB_DISCOVERY"

# returns all IPv4 and IPv6 addresses from all network interfaces of the system.
def getAllIPAddressesOfHost(ip_version=""):
    ips=[]
    try:
        s=subprocess.Popen("ip "+ ip_version +" addr |awk '/inet6? / {print $2}' | sed -r 's/\/[0-9]+$//'",shell=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE) # used to obtain all ips of the host. - ipv4 and ipv6
        output,err=s.communicate()
        if err:
            AgentLogger.log(AgentLogger.DATABASE,"'ip' utility is not found using /proc/net/fib_trie for getting all ip addresses of this server error :: {}".format(err))
            s=subprocess.Popen("awk '/32 host/ {print f} {f=$2}' /proc/net/fib_trie | awk '!seen[$0]++'",shell=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE) # only ipv4 can be obtained
            output,err=s.communicate()
            if err!=None:
                ips=output.decode("utf-8").split("\n")
        else:
            ips=output.decode("utf-8").split("\n")
        if ips[-1]=='':
            ips.pop()
    except Exception as e:
        AgentLogger.log(AgentLogger.DATABASE,"Exception :: couldn't able to find all IP Addresses of host :: getAllIPAddressesOfHost - {} ".format(e))
    return ips

# To get Process ID of a process.
# Only return pid of the process which doesn't have a child process.
def getPID(process_name):
    try:
        result      =   []
        __str="{"+subprocess.getoutput("ps -ef|grep "+process_name+"|grep -v grep|awk '{printf $3\":\"$2\",\"}'")
        __str=eval(re.sub(",*\s*$","",__str)+"}")
        for parentPID,childPID in __str.items():
            if __str.get(childPID)==None:
                result.append(childPID)
    except Exception as e:
        AgentLogger.log(AgentLogger.DATABASE," Exception :: getPID -> {}".format(e))
    return result


# Used to get NDBCluster Version based on "select @@Version" query output.
def isNDBClusterInstance(connection):
    try:
        if connection:
            output = getOutputFromQuery(connection, DBConstants.NDBClusterVersionCheckQuery)
            return isNDBCluster(output[0][0])            
    except Exception as e:
        AgentLogger.log(AgentLogger.DATABASE," Exception :: isNDBClusterInstance -> {}".format(e))


def isNDBCluster(output):
    try:
        output = re.findall("\d+\.\d+\.?\d*-cluster", output) or re.findall("ndb-\d+\.\d+\.?\d*", output)
        if len(output) == 1:
            str.replace(output[0],'ndb-','')
            str.replace(output[0],'-cluster','')
            return re.findall("\d+\.\d+", output[0])[0]
    except Exception as e:
        AgentLogger.log(AgentLogger.DATABASE," Exception :: isNDBCluster -> {}".format(e))

# Used for application and child discovery
def getOutputFromQuery(connection, query):
    try:
        with connection.cursor() as cursor:
            cursor.execute(query)
            return cursor.fetchall()
    except Exception as e:
        AgentLogger.log(AgentLogger.DATABASE," Exception :: getOutputFromQuery :: Query -> {} Exception -> {}".format(query, e))

# Returns the url params for application discovery servlet's GET request.

def FetchDiscoveryData(dict_params):
    try:
        # hostname,current_sql_node=socket.gethostbyname(dict_params["host"]),""
        paramObj = {"ndb_cluster": "TRUE"}
        connectionStatus,connection = DatabaseUtil.getDBConnection(dict_params, AgentConstants.MYSQL_DB)
        if connectionStatus:
            version = isNDBClusterInstance(connection)
            if version:
                output      =   getOutputFromQuery( connection, DBConstants.NDBDiscoveryConectionStringQuery  )
                output2     =   getOutputFromQuery( connection, DBConstants.NDBDiscoverySystemNameQuery  )
                
                paramObj[output[0][0]]      =   output[0][1]
                paramObj[output[1][0]]      =   output[1][1]
                paramObj[output2[0][0]]     =   output2[0][1]
                connection.close()
                return version,paramObj
            connection.close()
        return None,None
    except Exception as e:
        AgentLogger.log(AgentLogger.DATABASE,"Exception :: FetchDiscoveryData -> {}".format(e))
        return None,None

def FetchChildNodeDiscoveryData(section_dict):
    try:

        mysqlNDBmonkey, mid = section_dict.get("mysqlNDBmonkey"), section_dict.get("mid")
        connectionStatus, connection  = DatabaseUtil.getDBConnection(section_dict, AgentConstants.MYSQL_DB)
        queryOutput =   getOutputFromQuery(connection,DBConstants.NDBChildDiscoveryQuery)
        data_mapper =   {"MYSQLNDB_NODE":[],"MYSQLMGM_NODE":[]}
        result=[]
        for val in queryOutput:
            if val[2]=="NDB":
                # data_mapper["MYSQLNDB_NODE"].append({"node_name":val[0],"node_id":val[1],"node_type":val[2],"node_hostname":val[3],"ip":socket.gethostbyname(val[3]),"node_version":val[4]})
                data_mapper["MYSQLNDB_NODE"].append({"node_name":val[0],"node_type":val[2],"node_hostname":val[3],"ip":socket.gethostbyname(val[3]),"node_version":val[4]})
            else:
                # data_mapper["MYSQLMGM_NODE"].append({"node_name":val[0],"node_id":val[1],"node_type":val[2],"node_hostname":val[3],"ip":socket.gethostbyname(val[3]),"node_version":val[4]})
                data_mapper["MYSQLMGM_NODE"].append({"node_name":val[0],"node_type":val[2],"node_hostname":val[3],"ip":socket.gethostbyname(val[3]),"node_version":val[4]})

        if mid and mysqlNDBmonkey:
            for _key,_data in data_mapper.items():
                requestObj = {
                    "request": {
                        "AGENT_REQUEST_ID": "-1",
                        "CHILD_TYPE": _key,
                        "MONITOR_TYPE": "MYSQLNDB",
                        "MONITOR_ID": mysqlNDBmonkey
                    },
                    "totalpages": 1,
                    "Data": _data,
                    "pagenumber": 1,
                }
                result.append(requestObj)
            return result
    except Exception as e:
        AgentLogger.log(AgentLogger.DATABASE,"Exception :: FetchNodeDiscoveryData -> {}".format(e))



class Initializer:
    def __init__(self,instance_name,xmlString):
        try:
            self.conf_folder        =   AgentConstants.DB_CONSTANTS[AgentConstants.MYSQL_DB]['CONF_FOLDER']
            self.section_dict       =   self.load_section_info(instance_name)
            self.load(instance_name,xmlString)
            
            self.change_in_child_keys = False
            self.child_keys         = {}

            self.nextDay            =   0
            perf_file_path          =   os.path.join(self.conf_folder,self.section_dict.get("ndb_system_name")+ '_perf.json')
            DatabaseUtil.write_data("",self.conf_folder,self.section_dict.get("ndb_system_name")+ '_conf.json')
            if os.path.exists(perf_file_path) and os.path.getmtime(perf_file_path)+int(self.section_dict.get("NDB_perf_pollinterval") or 300)<int(time.time()):
                DatabaseUtil.write_data("",self.conf_folder,self.section_dict.get("ndb_system_name")+ '_perf.json')
        except Exception as e:
            AgentLogger.log(AgentLogger.DATABASE,'Exception while initializing NDBCluster.Initializer object :: Instance - {} :: Error - {}'.format(instance_name,e))


    def load(self,instance_name,xmlString):
        try:
            self.instance_name  =   instance_name
  
            self.instance_info = {
                'os'                        : 'linux',
                'application'               : 'mysql_ndb',
                'instance_name'             : instance_name,
                'section_dict'              : self.section_dict,
                'time_diff'                 : AgentUtil.AGENT_CONFIG.get('AGENT_INFO', 'time_diff'),
                'xmlString'                 : xmlString
            }
        except Exception as e:
            AgentLogger.log(AgentLogger.DATABASE," Exception :: NDBCluster.Initializer.load() -> {}".format(e))
   
    @staticmethod
    def load_section_info(instance_name):
        try:
            section_dict   =   {}
            for key in ['host','port','user','mysqlNDBmonkey','encrypted.password','ndb_system_name','NDB_version','NDB_disabled_queries','mid','NDB_one_day_pollinterval','NDB_perf_pollinterval','NDB_conf_pollinterval']: 
                section_dict[key]  =   DatabaseUtil.MYSQL_CONFIG.get(instance_name,key)
            decrypted_pwd               = str(AgentCrypt.decrypt_with_ss_key(section_dict.get('encrypted.password')))
            section_dict['password']    = '' if str(decrypted_pwd) in ['None', 'none', '0', ''] else decrypted_pwd
            section_dict['NDB_disabled_queries'] = json.loads(section_dict.get("NDB_disabled_queries") or "{}")
        except Exception as e:
            AgentLogger.log(AgentLogger.DATABASE," Exception :: NDBCluster.Initializer.load_section_info() -> {}".format(e,instance_name))
        return section_dict

    def collectTopologyData(self):
        try:
            final_data  =   (None,None)
            file_name   =   self.section_dict.get("ndb_system_name")+ '_conf.json'
            instance_dict = {
                'cached'            :   DatabaseUtil.read_data( AgentConstants.DB_CONSTANTS[AgentConstants.MYSQL_DB]['CONF_FOLDER']) or "",
                'collection_type'   :   "9",               
                'child_keys'        :   self.child_keys
            }
            instance_dict.update(self.instance_info)
            changed,result,cached = DatabaseExecutor.initialize(instance_dict)
            if changed:
                DatabaseUtil.write_data(cached, AgentConstants.DB_CONSTANTS[AgentConstants.MYSQL_DB]['CONF_FOLDER'],file_name)
                final_data  = (result,"MYSQLNDB")
        except Exception as e:
            AgentLogger.log(AgentLogger.DATABASE," Exception :: NDBCluster.Initializer.collectTopologyData() -> {}".format(e))
        return final_data

    def collectPerformanceData(self):
        try:
            result,onceADayBool =   {}, False
            now                 =   int(time.time())
            conf_folder         =    AgentConstants.DB_CONSTANTS[AgentConstants.MYSQL_DB]['CONF_FOLDER']
            if now >= self.nextDay or self.change_in_child_keys:
                onceADayBool    =   True
                self.nextDay    =   now + int(self.section_dict.get("NDB_one_day_pollinterval") or 86400)

            file_name   =   self.section_dict.get("ndb_system_name")+ '_perf.json'
            instance_dict = {
                'cached'            :   json.loads(DatabaseUtil.read_data(conf_folder,file_name) or "{}"),
                'onceADayBool'      :   onceADayBool,
                'collection_type'   :   "8",
                'child_keys'        :   self.child_keys
            }
            instance_dict.update(self.instance_info)
            cache,result = DatabaseExecutor.initialize(instance_dict)

            if cache:
                DatabaseUtil.write_data(cache,conf_folder,file_name)
        except Exception as e:
            AgentLogger.log(AgentLogger.DATABASE," Exception :: NDBCluster.Initializer.collectPerformanceData() -> {}".format(e))
        return result

    def data_collection_initialize(self,task_args_list):
        result = None
        try:
            if DBConstants.NDB_CID_MAPPER.get(self.section_dict.get('mysqlNDBmonkey')) != self.child_keys:
                self.change_in_child_keys = True
            else:
                self.change_in_child_keys = False
            
            self.child_keys     =   DBConstants.NDB_CID_MAPPER.get(self.section_dict.get('mysqlNDBmonkey')) or {}

            instance,data_collection_type   = task_args_list
            if data_collection_type == "7":
                SendChildNodesRegistrationRequest(self.section_dict)
            elif data_collection_type == "8":
                result  =   self.collectPerformanceData()
            elif data_collection_type == "9":
                result  =   self.collectTopologyData()

        except Exception as e:
            AgentLogger.log(AgentLogger.DATABASE," Exception :: NDBCluster.data_collection_initialize() - {},task_args_list - {}".format(e,task_args_list))
        return result
