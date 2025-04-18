import xml.etree.ElementTree as ET
import os
import sys
import traceback
import json
import time, math, copy
import six.moves.urllib.request as urlconnection
from six.moves.urllib.parse import urlencode
try:
    import configparser
except Exception as e:
    import ConfigParser as configparser

from itertools import islice

from datetime import datetime

try:
    import yaml
except Exception:
    pass

from com.manageengine.monagent.kubernetes.Logging import KubeLogger as AgentLogger
from com.manageengine.monagent.kubernetes import KubeGlobal

if 'com.manageengine.monagent.kubernetes.SettingsHandler.Initializer' in sys.modules:
    Initializer = sys.modules['com.manageengine.monagent.kubernetes.SettingsHandler.Initializer']
else:
    from com.manageengine.monagent.kubernetes.SettingsHandler import Initializer

idDict = {}
calc_perc = lambda used, limit : (int(used) / int(limit)) * 100 if limit else 0
construct_node_ip_url = lambda url, address: url.format('[' + address + ']') if ':' in address else url.format(address)
COUNTER_PARAMS_DICT = {}

KUBE_CONFIG = configparser.RawConfigParser()

def exception_handler(func):
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            AgentLogger.log(AgentLogger.KUBERNETES, "****** Exception -> {} -> {} -> {} ******".format(func.__name__, e, traceback.format_exc()))
            traceback.print_exc()

    return wrapper

def load_xml_root_from_file(xmlFileName):
    root = None
    file_obj = None
    try:
        if os.path.isfile(xmlFileName):
            AgentLogger.debug(AgentLogger.KUBERNETES,'LoadXmlRootFromFile -> xmlFileName available')
            file_obj = open(xmlFileName,'rb')
            byte_data = file_obj.read()
            fileSysEncoding = sys.getfilesystemencoding()
            perfData = byte_data.decode(fileSysEncoding)
            root = ET.fromstring(perfData)
        else:
            AgentLogger.log(AgentLogger.KUBERNETES,'LoadXmlRootFromFile -> xmlFileName not available')
    except Exception as e:
        AgentLogger.log(AgentLogger.KUBERNETES,'LoadXmlRootFromFile -> Exception -> {0}'.format(e))
    finally:
        if file_obj:
            file_obj.close()
    return root

def curl_api_without_token(url, header=None, method='GET', request_body=None):
    try:
        proxies = {"http": None,"https": None}
        if method == 'GET':
            r = KubeGlobal.REQUEST_MODULE.get(url,proxies=proxies,verify=False,timeout=KubeGlobal.urlTimeout) if not header else KubeGlobal.REQUEST_MODULE.get(url, headers=header, proxies=proxies,verify=False,timeout=KubeGlobal.urlTimeout)
        elif method == 'POST':
            r = KubeGlobal.REQUEST_MODULE.post(url, proxies=proxies, verify=False,timeout=KubeGlobal.urlTimeout, json=request_body)

        AgentLogger.log(AgentLogger.DA,'curlapiWithoutToken -> url - {} - statusCode {}'.format(url, r.status_code))
        data = r.content
        if isinstance(data, bytes):
            data = data.decode()
        return r.status_code,data
    except Exception as e:
        AgentLogger.log(AgentLogger.KUBERNETES,'curlapiWithoutToken -> Exception -> {0}\n'.format(e))
    return -1,{}

def curl_api_with_token(url, ssl_verify = True):
        try:            
            headers = {'Authorization' : 'Bearer ' + KubeGlobal.bearerToken}
            proxies = {"http": None,"https": None}
            r = KubeGlobal.REQUEST_MODULE.get(
                url,
                headers=headers,
                proxies=proxies,
                verify=(KubeGlobal.serviceAccPath + '/ca.crt') if ssl_verify else False,
                timeout=KubeGlobal.urlTimeout
            )
            # AgentLogger.log(AgentLogger.KUBERNETES,'curl_api_with_token -> url - {} - statusCode {}\n'.format(url, r.status_code))
            data = r.content
            if isinstance(data, bytes):
                data = data.decode()
            if "/metrics/cadvisor" in url or '/healthz' in url or '/livez' in url or '/metrics' in url:
                return r.status_code,data
            return r.status_code,json.loads(data)
        except Exception as e:
            AgentLogger.log(AgentLogger.KUBERNETES,'curlapiWithToken -> Exception -> {0}\n'.format(e))
        return -1,{}

def get_control_plane_ip():
    try:
        if KubeGlobal.fargate:
            dns_name = get_fargate_clustername()
            if dns_name:
                return dns_name

        status_code, json=curl_api_with_token(KubeGlobal.host + '/api/v1/namespaces/default/endpoints?fieldSelector=metadata.name=kubernetes')
        port="443"
        kube_endpoint = json["items"][0]
        if "subsets" in kube_endpoint and "addresses" in kube_endpoint["subsets"][0]:
            controlplane_ip=kube_endpoint["subsets"][0]["addresses"][0]["ip"]

            if "ports" in kube_endpoint["subsets"][0] and "port" in kube_endpoint["subsets"][0]["ports"][0]:
                port=kube_endpoint["subsets"][0]["ports"][0]["port"]

            AgentLogger.log(AgentLogger.KUBERNETES, "control plane ip: "+controlplane_ip)
            return "https://"+controlplane_ip+":"+str(port)
        AgentLogger.log(AgentLogger.KUBERNETES, 'controlplane_ip not present in the endpoints\n')
    except Exception as e:
        AgentLogger.log(AgentLogger.KUBERNETES, 'Exception While Fetching the Fargate Cluster DNS Name -> {0}'.format(e))
    return None

def get_fargate_clustername():
    try:
        status_code, json=curl_api_with_token(KubeGlobal.host+KubeGlobal.clusterDNPATH)
        if "items" in json.keys():
            json=json.get("items")[0]
            if "data" in json.keys():
                json=json.get("data")
                if "kubeconfig" in json.keys():
                    json=json.get("kubeconfig").split("\n")
        for i in json:
            if "server:" in i:
                dns_name=i.strip().split(': ')[1]
                dns_split=dns_name.split('.')[0].split('//')[1]
                dns_name=dns_name.replace(dns_split, dns_split.upper())
                AgentLogger.log(AgentLogger.KUBERNETES, "Cluster DNS name: "+dns_name)
                return dns_name
        AgentLogger.log(AgentLogger.KUBERNETES, 'Fargate Cluster DNS not present in the configmap\n')
    except Exception as e:
        AgentLogger.log(AgentLogger.KUBERNETES, "")
    return None
    
def clear_and_init_dict(thisDic):
        try:
            if thisDic:
                thisDic.clear()
            thisDic = {}
        except Exception as e:
            AgentLogger.log(AgentLogger.KUBERNETES,'clearAndInitDict -> Exception -> {0}'.format(e))

def clear_and_init_list(thisList):
    try:
        if thisList:
            thisList.clear()
        thisList=[]
    except Exception as e:
        AgentLogger.log(AgentLogger.KUBERNETES,'clearAndInitList -> Exception -> {0}'.format(e))
            
def get_dict_node(dictNode,path):
    try:
        toReturnNode = dictNode
        pathExists = False
        #AgentLogger.log(AgentLogger.KUBERNETES,str(path))
        if path != "":
            for patharg in path.split('/'):
                if patharg=="#":
                    patharg="/"
                
                if patharg in toReturnNode:
                    tempNode = toReturnNode[patharg]
                    toReturnNode = tempNode
                    pathExists = True
                else:
                    AgentLogger.debug(AgentLogger.KUBERNETES,'path - ' + str(patharg) + 'does not exist')
                    pathExists = False
                    break
                
        if pathExists:
            return toReturnNode
    except Exception as e:
        AgentLogger.log(AgentLogger.KUBERNETES,'GetItemsGroupNode -> Exception -> {0}'.format(e))
    return None

def get_kube_ids():
    try:
        from com.manageengine.monagent.AgentConstants import APPS_CONFIG_DATA
        if APPS_CONFIG_DATA:
            if "KUBERNETES" in APPS_CONFIG_DATA:
                KubeGlobal.kubeIds = APPS_CONFIG_DATA["KUBERNETES"]
            else:
                AgentLogger.log(AgentLogger.KUBERNETES,'get_kube_ids -> "apps" not found ')
        else:
            AgentLogger.log(AgentLogger.KUBERNETES,'get_kube_ids -> "AgentConstants.APPS_CONFIG_DATA" is empty')
    except Exception as e:
        AgentLogger.log(AgentLogger.KUBERNETES,'get_id_group_dict -> Exception -> {0}'.format(e))

def get_id_group_dict(group):
    try:
        if KubeGlobal.kubeIds and group in KubeGlobal.kubeIds:
            return KubeGlobal.kubeIds[group]
    except Exception as e:
        AgentLogger.log(AgentLogger.KUBERNETES,'get_id_group_dict -> Exception -> {0}'.format(e))
    return None

def get_id(groupIdDict,itemName):
    id = ""
    try:
        if groupIdDict:
            if itemName in groupIdDict:
                itemHash = groupIdDict[itemName]
                id = itemHash["id"]
            else:
                AgentLogger.debug(AgentLogger.KUBERNETES,'id for itemName not found - {0}'.format(itemName))
        else:
            AgentLogger.debug(AgentLogger.KUBERNETES,'group ID dict is empty')            
    except Exception as e:
        AgentLogger.log(AgentLogger.KUBERNETES,'get_id -> Exception -> {0}'.format(e))
    return id

def get_resource_id(resource_name,resource_group):
    id = None
    try:
        resource_config = get_id_group_dict(resource_group)
        if resource_config and resource_name in resource_config:
            id = resource_config[resource_name]['id']
    except Exception:
        traceback.print_exc()
    return id

@exception_handler
def update_instant_discovery_config(discovered_resource_config):
    for resource in discovered_resource_config:
        if resource["nodeName"] == "Containers":
            continue
        if resource["nodeName"] not in KubeGlobal.DISCOVERED_RESOURCE_CONFIG_STORAGE:
            KubeGlobal.DISCOVERED_RESOURCE_CONFIG_STORAGE[resource["nodeName"]] = {}
        if resource["nodeName"] in ["Pods", "Endpoints", "Services", "Jobs", "DaemonSets", "Deployments", "PersistentVolumeClaim", "ReplicaSets", "StatefulSets"]:
            resourse_name_key = resource["Na"]+"_"+resource["NS"]
        elif resource["nodeName"] in ["Nodes", "Namespaces", "PV"]:
            resourse_name_key = resource["Na"]
        else:
            resourse_name_key = resource["Na"]
        KubeGlobal.DISCOVERED_RESOURCE_CONFIG_STORAGE[resource.pop("nodeName")][resourse_name_key] = resource
        AgentLogger.log(AgentLogger.DA, " DISCOVERED_RESOURCE_CONFIG_STORAGE updated : {}".format(KubeGlobal.DISCOVERED_RESOURCE_CONFIG_STORAGE))

@exception_handler
def update_kube_config_to_instant_discovery(kube_config):
    for resource in kube_config:
        for resource_item in kube_config[resource]:
            if resource not in KubeGlobal.DISCOVERED_RESOURCE_CONFIG_STORAGE:
                KubeGlobal.DISCOVERED_RESOURCE_CONFIG_STORAGE[resource] = {}
            if resource_item not in KubeGlobal.DISCOVERED_RESOURCE_CONFIG_STORAGE[resource]:
                KubeGlobal.DISCOVERED_RESOURCE_CONFIG_STORAGE[resource][resource_item] = kube_config[resource][resource_item]

def map_container_ids(dataDic):
    try:
        AgentLogger.log(AgentLogger.KUBERNETES,'mapping container ids')
        if dataDic and "Pods" in dataDic:
            #get podsData
            podsData = dataDic["Pods"]
            #get podsId
            podsId = get_id_group_dict("Pods")
            if podsId:

                for pod,podData in podsData.items():
                    if pod in podsId:
                        podId = podsId[pod]
                        #get cont data
                        if "Cont" in podData:
                            contData = podData["Cont"]                            
                            #get corresponding cont id
                            if "Cont" in podId:
                                contIDs = podId["Cont"]
                                #map cont IDs
                                for cont in contData:
                                    id = get_id(contIDs,cont)
                                    AgentLogger.debug(AgentLogger.KUBERNETES,'map_container_ids -> id found - {0}'.format(cont))
                                    contData[cont]["id"] = id
    except Exception as e:
        AgentLogger.log(AgentLogger.KUBERNETES,'map_conatiner_ids -> Exception -> {0}'.format(e))
    return dataDic

def replace_tokens(data, node="", throughProxy=False):
    try:
        if data:
            if (throughProxy or KubeGlobal.fargate) and KubeGlobal.nodeName and "$NODE_IP$" in data:
                if KubeGlobal.gkeAutoPilot:
                    return "https://"+node+"/stats/summary"

                if not throughProxy: node = KubeGlobal.nodeName    
                
                path=data.split("$/")[1]
                path_temp=path.split("/")

                if "stats" in path_temp or "metrics" in path_temp:
                    data = KubeGlobal.apiEndpoint + KubeGlobal.kubeletPath.format(node)+path
                    AgentLogger.debug(AgentLogger.KUBERNETES, 'Replacing Token for Fargate Proxy Kubelet Api')

            if "$NODE_IP$" in data and KubeGlobal.IP_ADDRESS:
                AgentLogger.debug(AgentLogger.KUBERNETES,'ReplaceTokens :: Replacing $NODE_IP$')
                data = data.replace("$NODE_IP$",KubeGlobal.IP_ADDRESS)
            if "$KUBELET_STATS_PORT$" in data and KubeGlobal.kubeletStatsPort:
                AgentLogger.debug(AgentLogger.KUBERNETES,'ReplaceTokens :: Replacing $KUBELET_STATS_PORT$ - {0}'.format(KubeGlobal.kubeletStatsPort))
                data = data.replace("$KUBELET_STATS_PORT$",KubeGlobal.kubeletStatsPort)
            if "$KUBE_STATE_METRICS_URL$" in data and KubeGlobal.kubeStateMetricsUrl:
                AgentLogger.debug(AgentLogger.KUBERNETES,'ReplaceTokens :: Replacing $KUBE_STATE_METRICS_URL$ - {0}'.format(KubeGlobal.kubeStateMetricsUrl))
                data = data.replace("$KUBE_STATE_METRICS_URL$",KubeGlobal.kubeStateMetricsUrl)
            if "$KUBE_STATE_IP$" in data and KubeGlobal.kubeStatePodIP:
                AgentLogger.debug(AgentLogger.KUBERNETES,'ReplaceTokens :: Replacing $KUBE_STATE_IP$ - {0}'.format(KubeGlobal.kubeStatePodIP))
                data = data.replace("$KUBE_STATE_IP$",KubeGlobal.kubeStatePodIP)
            if "$KUBE_STATE_PORT$" in data and KubeGlobal.kubeStatePort:
                AgentLogger.debug(AgentLogger.KUBERNETES,'ReplaceTokens :: Replacing $KUBE_STATE_PORT$ - {0}'.format(KubeGlobal.kubeStatePort))
                data = data.replace("$KUBE_STATE_PORT$",KubeGlobal.kubeStatePort)
    except Exception as e:
        AgentLogger.log(AgentLogger.KUBERNETES,'ReplaceTokens -> Exception -> {0}'.format(e))
    return data

def getKubeAPIServerEndPoint():
    AgentLogger.log(AgentLogger.KUBERNETES,'getKubeAPIServerEndPoint')
    try:
        url = "/api/v1/namespaces"
        #using KubeGlobal.kubeServer 
        server = KubeGlobal.kubeServer
        server = server.replace('"','')
        AgentLogger.log(AgentLogger.KUBERNETES,'## kubeServer name - {0}'.format(server))
        status,valDict = curl_api_with_token(server+url)
        if status == 200:
            AgentLogger.log(AgentLogger.KUBERNETES,'KubeGlobal.kubeServer - 200')
            KubeGlobal.apiEndpoint = server
            return
        
        #using KubeGlobal.host
        status,valDict = curl_api_with_token(KubeGlobal.host+url)
        if status == 200:
            AgentLogger.log(AgentLogger.KUBERNETES,'KubeGlobal.host - 200')
            KubeGlobal.apiEndpoint = KubeGlobal.host
            return
    except Exception as e:
        AgentLogger.log(AgentLogger.KUBERNETES,'getKubeAPIServerEndPoint -> Exception -> {0}'.format(e))
    AgentLogger.log(AgentLogger.KUBERNETES, "****** K8s Api Endpoint not pinging *******")

def shift_data_to_k8s_node(perfData):
    try:
        if "workloads" in perfData:
            perfData["kubernetes"] = perfData.pop("workloads")
        
        if "ComponentStatuses" in perfData:
            perfData["kubernetes"]["ComponentStatuses"] = perfData.pop("ComponentStatuses")

        perfData["kubernetes"]["provider"] = KubeGlobal.PROVIDER
    except Exception as e:
        traceback.print_exc()

def check_kube_presents():
    try:
        from com.manageengine.monagent.kubernetes_monitoring import KubernetesExecutor
        get_bearer_token()
        status, data = curl_api_with_token('https://kubernetes.default/api/v1/namespaces')
        if status == 200:
            KubernetesExecutor.discover_kubernetes(False)
            return True
    except Exception as e:
        traceback.print_exc()
    return False

def init_nested_dict(dict_for_init, keys_to_init):
    try:
        if len(keys_to_init) > 0:
            key = keys_to_init.pop(0)
            if key not in dict_for_init:
                dict_for_init[key] = {}
            init_nested_dict(dict_for_init[key], keys_to_init)
    except Exception as e:
        traceback.print_exc()

def get_bearer_token():
    AgentLogger.log(AgentLogger.KUBERNETES, 'inside GetbearerToken')
    file_obj = None
    try:
        tokenFile = KubeGlobal.serviceAccPath + "/token"
        if os.path.isfile(tokenFile):
            file_obj = open(tokenFile, "r")
            kubeToken = file_obj.read()
            kubeToken = kubeToken.rstrip()
            if kubeToken:
                KubeGlobal.bearerToken = kubeToken
    except Exception as e:
        AgentLogger.log(AgentLogger.KUBERNETES, 'Exception -> GetbearerToken -> {0}'.format(e))
    finally:
        if file_obj:
            file_obj.close()

def get_dctype():
    return "false" if KubeGlobal.isConfDc else "true"

def is_conf_agent():
    return True if KubeGlobal.sendConfig.lower() == "true" else False

def getKubeClusterVersion():
    AgentLogger.log(AgentLogger.KUBERNETES,'getKubeAPIServerEndPoint')
    version = None
    try:
        url = "/version"
        status, valDict = curl_api_with_token(KubeGlobal.apiEndpoint+url)
        if status == 200:
            AgentLogger.log(AgentLogger.KUBERNETES,'cluster version api output - {}'.format(json.dumps(valDict)))
            if valDict:
                version = valDict["gitVersion"]
    except Exception as e:
        AgentLogger.log(AgentLogger.KUBERNETES,'getKubeAPIServerEndPoint -> Exception -> {0}'.format(e))
    return version

def getKubeletHealthStatus():
    kubelet_health = 0
    try:
       url = ("https://[{}]:10250/healthz" if ":" in KubeGlobal.IP_ADDRESS else "https://{}:10250/healthz").format(KubeGlobal.IP_ADDRESS)
       status,valDict = curl_api_with_token(url)
       if status == 200:
           kubelet_health = 1
    except Exception as e:
       traceback.print_exc()
    return kubelet_health

def get_cluster_name_from_cloud_apis():
    try:
        if KubeGlobal.PROVIDER == "GCP":
            status, data = curl_api_without_token(KubeGlobal.gkeClusterNameEndpoint, {"Metadata-Flavor": "Google"})
            if status == 200:
                KubeGlobal.clusterDN = data
                AgentLogger.log(AgentLogger.KUBERNETES, "discovered cluster name for GKE cluster {}".format(data))
                return

        if KubeGlobal.PROVIDER == "AWS":
            bool_flag, auth_token = send_request_to_url("http://169.254.169.254/latest/api/token", None, {"X-aws-ec2-metadata-token-ttl-seconds": "21600"},"PUT")
            if auth_token:
                for tag_key in ['eks:cluster-name', 'aws:eks:cluster-name']:
                    bool_flag, resp_data = send_request_to_url("http://169.254.169.254/latest/meta-data/tags/instance/{}".format(tag_key), None, {"X-aws-ec2-metadata-token": auth_token})
                    if resp_data:
                        KubeGlobal.clusterDN = resp_data
                        AgentLogger.log(AgentLogger.KUBERNETES,"discovered cluster name for EKS cluster {}".format(resp_data))
                        return
    except Exception as e:
        traceback.print_exc()

def check_cluster_distribution():
    try:
        if KubeGlobal.PROVIDER == "AWS":
            bool_flag, resp_data = send_request_to_url("http://169.254.169.254/latest/meta-data/iam/info")
            if resp_data and "InstanceProfileArn" in resp_data and "eks" in str(resp_data["InstanceProfileArn"]):
                KubeGlobal.clusterDistribution = "EKS"
    except Exception as e:
        traceback.print_exc()

# This method fetches the updated (poll interval & last DC time) and checks whether the resource type valid for this DC
def is_eligible_to_execute(res_type, dc_start_time = KubeGlobal.DC_START_TIME, update_needed = True, skip_period_check = False):
    eligibility = False
    try:
        poll_interval = int(KubeGlobal.KUBE_GLOBAL_SETTINGS[res_type])
        if poll_interval == -1:
            return eligibility

        if poll_interval == 1:
            AgentLogger.log(AgentLogger.KUBERNETES, "********* {} eligible for DC *********".format(res_type))
            return not eligibility

        if skip_period_check:
            return True

        if res_type in KubeGlobal.RES_BASED_LAST_DC_TIME:
            diff = math.ceil(time.time()) - KubeGlobal.RES_BASED_LAST_DC_TIME[res_type]
            if diff >= poll_interval:
                AgentLogger.log(AgentLogger.KUBERNETES, "********* {} eligible for DC - diff {} *********".format(res_type, diff))
                eligibility = True
            else:
                return eligibility
        else:
            eligibility = True

        if update_needed:
            KubeGlobal.RES_BASED_LAST_DC_TIME[res_type] = dc_start_time
    except Exception as e:
        AgentLogger.console_logger.warning("********* Exception -> is_eligible_to_execute -> {}".format(e))
        traceback.print_exc()
    return eligibility

def discover_ksm_url():
    try:
        url = "/api/v1/pods?labelSelector={}%3D{}"

        for labels in KubeGlobal.KSM_MATCH_LABELS:
            try:
                status, valDict = curl_api_with_token(KubeGlobal.apiEndpoint + url.format(labels[0], labels[1]))

                if status == 200 and "items" in valDict and len(valDict["items"]) > 0:
                    pod_ip = valDict['items'][0]['status']['podIP']
                    KubeGlobal.kubeStateMetricsUrl = ("http://[{}]:{}" if ":" in pod_ip else "http://{}:{}").format(pod_ip, KubeGlobal.kubeStatePort)
                    AgentLogger.log(AgentLogger.KUBERNETES,"Discovered Kube-State-Metrics Pod - {}".format(KubeGlobal.kubeStatePodIP))
                    break
            except Exception as e:
                AgentLogger.log(AgentLogger.KUBERNETES, "Exc -> discover_ksm_url -> {}".format(e))
                traceback.print_exc()
    except Exception as e:
        AgentLogger.log(AgentLogger.KUBERNETES, 'discover_ksm_url -> Exception -> {0}'.format(e))

def pre_dc_init(func):
    def wrapper():
        KubeGlobal.DC_START_TIME = time.time()
        handle_init_actions()
        return func()
    return wrapper

def handle_init_actions():
    from com.manageengine.monagent.kubernetes.ClusterAgent.ClusterAgentUtil import check_and_discover_cluster_agent_svc
    if is_eligible_to_execute("dcinit", KubeGlobal.DC_START_TIME):
        get_bearer_token()
        getKubeAPIServerEndPoint()
        discover_ksm_url()
        Initializer.fetch_global_settings_from_configmap()
        Initializer.fetch_1min_settings_from_configmap()
        check_and_discover_cluster_agent_svc()
    KubeGlobal.CONFIGMAP_INTEG_DATA = load_integration_config_details()
    KubeGlobal.NODE_BASE_PODS_CONFIGS = get_kubelet_api_data('/pods')
    get_kube_ids()

def MergeDataDictionaries(dict1, dict2):
    try:
        if dict1 and not dict2:
            return dict1

        if dict2 and not dict1:
            return dict2

        dictNew = dict(mergedicts(dict1, dict2))
        return dictNew
    except Exception as e:
        AgentLogger.log(AgentLogger.KUBERNETES, 'Exception while MergeDictionaries {}'.format(e))
    return None

def mergedicts(dict1,dict2):
    try:
        for k in set(dict1.keys()).union(dict2.keys()):
                if k in dict1 and k in dict2:
                    if isinstance(dict1[k], dict) and isinstance(dict2[k], dict):
                        yield (k, dict(mergedicts(dict1[k], dict2[k])))
                    else:
                        # If one of the values is not a dict, you can't continue merging it.
                        # Value from second dict overrides one in first and we move on.
                        yield (k, dict2[k])
                        # Alternatively, replace this with exception raiser to alert you of value conflicts
                elif k in dict1:
                    yield (k, dict1[k])
                else:
                    yield (k, dict2[k])
    except Exception as e:
        AgentLogger.log(AgentLogger.KUBERNETES, 'Exception while mergedicts {}'.format(e))

def getAge(ct, cmpt=datetime.now(), return_as_sec=False):
    age = None
    try:
        from dateutil import relativedelta
        if ct:
            ct=ct.split('T')
            ct=ct[0]+" "+ct[1].split('Z')[0]+".000000"
            c=datetime.strptime(ct, '%Y-%m-%d %H:%M:%S.%f')
            b=datetime.strptime(str(cmpt), '%Y-%m-%d %H:%M:%S.%f')

            if return_as_sec:
                return time.mktime(b.timetuple()) - time.mktime(c.timetuple())

            d=relativedelta.relativedelta(b,c)
            day, month, year, minute, hour, sec=d.days, d.months, d.years, d.minutes, d.hours, d.seconds
            if year!=0:
                unit = ' year' if year <= 1 else ' years'
                age=str(year)+unit
            elif month!=0:
                unit = ' month' if month <= 1 else ' months'
                age=str(month)+unit
            elif day!=0:
                unit = ' day' if day <= 1 else ' days'
                age=str(day)+unit
            elif hour!=0:
                unit = ' hour' if hour <= 1 else ' hours'
                age=str(hour)+unit
            elif minute!=0:
                unit = ' min' if minute <= 1 else ' mins'
                age=str(minute)+unit
            else:
                age=str(sec)+' secs'
    except Exception as e:
        traceback.print_exc()
    return age

def getAgeInSec(ct):
    age = None
    try:
        from dateutil import relativedelta
        if ct:
            timestamp = datetime.strptime(ct, "%Y-%m-%dT%H:%M:%SZ")
            current_timestamp = datetime.now()
            time_difference = current_timestamp - timestamp
            age = time_difference.total_seconds()

    except Exception as e:
        traceback.print_exc()
    return age

def list_chunks(my_list,SIZE=4):
    final_list = [my_list[i * SIZE:(i + 1) * SIZE] for i in range((len(my_list) + SIZE - 1) // SIZE )]
    return final_list

def dict_chunks(kv_pairs, SIZE=10):
    it = iter(kv_pairs)
    for i in range(0, len(kv_pairs), SIZE):
        yield {k:kv_pairs[k] for k in islice(it, SIZE)}

def get_api_data_by_limit(url, callback, *args, **kwargs):
    continue_token = None
    while True:
        repl_url = url + '&continue={}'.format(continue_token) if continue_token else url
        status, api_resp = curl_api_with_token(repl_url)
        if status == 200:
            if 'continue' in api_resp['metadata'] and api_resp['metadata']['remainingItemCount'] > 0:
                continue_token = api_resp['metadata']['continue']
                callback(api_resp, *args, **kwargs)
                continue
            callback(api_resp, *args, **kwargs)
        break

def get_counter_value(param,current_value,isNotDiv=False):
    global COUNTER_PARAMS_DICT
    return_value = 0
    try:
        if param in COUNTER_PARAMS_DICT and not isNotDiv:
           return_value = ( float(current_value) - float(COUNTER_PARAMS_DICT[param]) ) / 5
           COUNTER_PARAMS_DICT[param] = current_value
        elif param in COUNTER_PARAMS_DICT and isNotDiv:
            return_value = float(current_value) - float(COUNTER_PARAMS_DICT[param])
            COUNTER_PARAMS_DICT[param] = current_value
        else:
            return_value = 0
            COUNTER_PARAMS_DICT[param] = current_value
    except Exception as e:
        AgentLogger.log(AgentLogger.KUBERNETES,'exception occurred in counter values block for param -- {0}'.format(param))
        traceback.print_exc()
    return round(return_value,2)

def get_value_from_expression(expression,data_dict,round_off=False):
    locals = {}
    locals.update(data_dict)
    exec("contents="+expression,locals)
    value = round(locals['contents']) if round_off else locals['contents']
    return value

def send_request_to_url(url,data=None,headers={},method="GET"):
    resp_data=None
    bool_success = False
    try:
        AgentLogger.log(AgentLogger.KUBERNETES,"url -- {}".format(url))
        request_obj = urlconnection.Request(url,data,headers,method=method)
        response = urlconnection.urlopen(request_obj,timeout=3)
        resp_data = response.read()
        resp_data = resp_data.decode('UTF-8')
        resp_data = json.loads(resp_data)
        bool_success = True
    except Exception as e:
        traceback.print_exc()
        AgentLogger.log(AgentLogger.KUBERNETES,'unable to connect :: '+repr(e)+"\n")
    return bool_success,resp_data

def get_count_metric(url):
    status, api_resp = curl_api_with_token(url)
    if status == 200 and 'continue' in api_resp['metadata'] and api_resp['metadata']['remainingItemCount'] > 0:
        return api_resp['metadata']['remainingItemCount'] + 1
    return len(api_resp.get("items", []))

def find_replicaset_owner(rs_name):
    try:
        name, ns = rs_name.split("_")
        status, api_resp = curl_api_with_token(KubeGlobal.apiEndpoint + '/apis/apps/v1/namespaces/{}/replicasets?fieldSelector=metadata.name={}'.format(ns, name))

        if status == 200:
            replicaset_data = api_resp["items"][0]["metadata"]
            if replicaset_data["ownerReferences"][0]["kind"] == "Deployment":
                return replicaset_data["ownerReferences"][0]["name"] + "_" + ns
    except Exception:
        traceback.print_exc()
    return None

def convert_cpu_values_to_standard_units(value):
    suffix = str(value[-1])
    if suffix == 'm':   # milli core
        return float(value[:-1])
    if suffix == 'n':   # nano core
        return float(value[:-1]) / 1000000
    if suffix == 'u':   # micro core
        return float(value[:-1]) / 1000

    return float(value) * 1000

def convert_values_to_standard_units(value):
    str_value = str(value)
    if len(str_value) > 2:
        suffix = str_value[-2:]
        if suffix == "Mi":  # Mebibyte
            return float(value[:-2]) * 1048576
        if suffix == "Ki":  # Kebibyte
            return float(value[:-2]) * 1024
        if suffix == "Gi":  # Gebibyte
            return float(value[:-2]) * 1073741824
        if suffix == 'Ti':  # Tebibyte
            return float(value[:-2]) * 1099511627776
        if suffix == 'Pi':  # Pebibyte
            return float(value[:-2]) * 1125899906842624

    suffix = str_value[-1:]
    if suffix == "M":   # Megabyte
        return float(value[:-1]) * 1000000
    if suffix == "K" or suffix == "k":  # Kilobyte
        return float(value[:-1]) * 1000
    if suffix == "G":   # Gigabyte
        return float(value[:-1]) * 1000000000
    if suffix == 'm':
        return float(value[:-1]) / 1000
    if suffix == 'T':   # Terabyte
        return float(value[:-1]) * 1000000000000
    if suffix == 'P':   # Petabyte
        return float(value[:-1]) * 1000000000000000

    return float(value)

def fetch_cluster_metadata():
    url = KubeGlobal.apiEndpoint + '{}?limit=1'
    return {
        "version": getKubeClusterVersion(),
        "PC": get_count_metric(url.format(KubeGlobal.API_ENDPOINT_RES_NAME_MAP["Pods"].split('?')[0])),
        "NoC": get_count_metric(url.format(KubeGlobal.API_ENDPOINT_RES_NAME_MAP["Nodes"].split('?')[0])),
        "JC": get_count_metric(url.format(KubeGlobal.API_ENDPOINT_RES_NAME_MAP["Jobs"].split('?')[0])),
        "DPC": get_count_metric(url.format(KubeGlobal.API_ENDPOINT_RES_NAME_MAP["Deployments"].split('?')[0])),
        "DSC": get_count_metric(url.format(KubeGlobal.API_ENDPOINT_RES_NAME_MAP["DaemonSets"].split('?')[0])),
        "SSC": get_count_metric(url.format(KubeGlobal.API_ENDPOINT_RES_NAME_MAP["StatefulSets"].split('?')[0])),
        "RSC": get_count_metric(url.format(KubeGlobal.API_ENDPOINT_RES_NAME_MAP["ReplicaSets"].split('?')[0])),
        "SC": get_count_metric(url.format(KubeGlobal.API_ENDPOINT_RES_NAME_MAP["Services"].split('?')[0])),
        "NSCNT": get_count_metric(url.format(KubeGlobal.API_ENDPOINT_RES_NAME_MAP["Namespaces"].split('?')[0]))
    }

def func_exec_time(func):
    def wrapper(*args, **kwargs):
        try:
            start_time = time.time()
            return_data = func(*args, **kwargs)
            AgentLogger.console_logger.info('Time taken for completing {} - {}'.format(func.__name__, time.time()-start_time))
            return return_data
        except Exception as e:
            AgentLogger.log(AgentLogger.KUBERNETES, "****** Exception -> {} ******".format(e))
            traceback.print_exc()

    return wrapper

def get_kubelet_api_data(path, node_name=None, ip_address=None):
    api_path_urls = []
    if not node_name and not ip_address:
        api_path_urls.extend([
            'https://{}:10250'.format(KubeGlobal.IP_ADDRESS),
            'https://{}:10250'.format(KubeGlobal.KUBELET_NODE_NAME),
            'https://{}/api/v1/nodes/{}/proxy'.format(KubeGlobal.apiEndpoint, KubeGlobal.KUBELET_NODE_NAME)
        ])
    if node_name:
        api_path_urls.extend([
            'https://{}:10250'.format(KubeGlobal.KUBELET_NODE_NAME),
            'https://{}/api/v1/nodes/{}/proxy'.format(KubeGlobal.apiEndpoint, KubeGlobal.KUBELET_NODE_NAME)
        ])
    if ip_address:
        api_path_urls.extend([
            'https://{}:10250'.format(KubeGlobal.IP_ADDRESS)
        ])
    for url in api_path_urls:
        status, api_resp = curl_api_with_token(url + path, False)
        if status == 200:
            return api_resp

    return None

def load_integration_config_details():
    status, response = curl_api_with_token(KubeGlobal.apiEndpoint + '/api/v1/configmaps?fieldSelector=metadata.name=site24x7-agent-integrations')
    if status == 200 and 'items' in response and len(response['items']):
        return {
            'config': yaml.safe_load(response['items'][0]['data']['integrations']),
            'rv': response['items'][0]['metadata']['resourceVersion']
        }
    return {}

def check_metadata_needed():
    for res_type in ["DaemonSets", "Deployments", "StatefulSets"]:
        if res_type not in KubeGlobal.kubeIds:
            return False

def write_kubernetes_dc_config_to_file(keyValueDict, section=KubeGlobal.configParserSection):
    try:
        if keyValueDict:
            for key in keyValueDict:
                value = keyValueDict[key]
                AgentLogger.log(AgentLogger.KUBERNETES, 'WriteKubernetesDCConfigToFile -> key -> {} -> value -> {}'.format(key, value))
                KubeGlobal.KUBERNETES_CONFIG.set(section, key, value)
            with open(KubeGlobal.CONF_FILE, 'w+') as set:
                KubeGlobal.KUBERNETES_CONFIG.write(set)
        else:
            AgentLogger.log(AgentLogger.KUBERNETES, 'WriteKubernetesDCConfigToFile -> keyValueDict is empty')
    except Exception as e:
        AgentLogger.log(AgentLogger.KUBERNETES, 'WriteKubernetesDCConfigToFile -> Exception -> {0}'.format(e))


def update_s247_configmap(data):
    headers = {
        'Authorization': 'Bearer ' + KubeGlobal.bearerToken,
        'Content-Type': 'application/strategic-merge-patch+json',
        'Accept': 'application/json'
    }
    response = KubeGlobal.REQUEST_MODULE.patch(
        KubeGlobal.apiEndpoint + KubeGlobal.s247ConfigMapPath,
        headers=headers,
        verify=KubeGlobal.serviceAccPath + '/ca.crt',
        data=json.dumps(data)
    )

    return response.status_code, response.content


def get_cluster_id():
    for ns in ['default', 'kube-system']:
        status, response = curl_api_with_token(KubeGlobal.apiEndpoint + '/api/v1/namespaces?metadata.name=' + ns)
        if status == 200 and response.get('items'):
            return response['items'][0]['metadata']['uid']
    return None

def execute_dctask_ondemand(dc_name):
    if dc_name in KubeGlobal.ONDEMAND_DCTASK_EXEC_LIST:
        AgentLogger.log(AgentLogger.KUBERNETES, 'Ondemand task execution called, task name - {}'.format(dc_name))
        final_json = KubeGlobal.ONDEMAND_DCTASK_EXEC_LIST[dc_name].dc_class(KubeGlobal.ONDEMAND_DCTASK_EXEC_LIST[dc_name]).execute_dc_tasks()
        # zipping the respective task data
        getattr(sys.modules['com.manageengine.monagent.kubernetes_monitoring.KubernetesExecutor'], 'write_data_to_file')(
            [final_json] if isinstance(final_json, dict) else final_json
        )
