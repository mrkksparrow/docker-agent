import os
import traceback
import json
import sys
import time
from com.manageengine.monagent.kubernetes import KubeGlobal
from com.manageengine.monagent.kubernetes.Logging import KubeLogger as AgentLogger

if 'com.manageengine.monagent.kubernetes.KubeUtil' in sys.modules:
    KubeUtil = sys.modules['com.manageengine.monagent.kubernetes.KubeUtil']
else:
    from com.manageengine.monagent.kubernetes import KubeUtil


def init():
    try:
        KubeUtil.get_bearer_token()
        find_s247_configmap_namespace()
        add_to_registered_servers_configmap()
        read_config_file()
        load_kube_global_settings()
        load_1min_discovery_settings()
        getEnvVariables()
        get_kubernetes_conf_data()
        add_ondemand_exec_dctask_list()
        validate_kubelet_response()
    except Exception as e:
        AgentLogger.log(AgentLogger.KUBERNETES, 'Init -> Exception -> {0}'.format(e))

def find_s247_configmap_namespace():
    status, response = KubeUtil.curl_api_with_token('https://kubernetes.default/api/v1/configmaps?fieldSelector=metadata.name=site24x7')
    if status == 200 and 'items' in response and len(response['items']):
        KubeGlobal.s247ConfigMapPath = KubeGlobal.s247ConfigMapPath.format(response['items'][0]['metadata']['namespace'])

def read_config_file():
    try:
        if not os.path.isfile(KubeGlobal.CONF_FILE):
            AgentLogger.log(AgentLogger.KUBERNETES, 'kubernetes.conf not present.... hence writing it')
            os.mkdir(os.path.dirname(KubeGlobal.CONF_FILE))
            file1 = open(KubeGlobal.CONF_FILE, "w")
            file1.writelines(KubeGlobal.confData)
            file1.close()
        KubeGlobal.KUBERNETES_CONFIG.read(KubeGlobal.CONF_FILE)
        AgentLogger.log(AgentLogger.KUBERNETES, 'KubeGlobal.KUBERNETES_CONFIG -> reading -> success ')
    except Exception as e:
        AgentLogger.log(AgentLogger.KUBERNETES, 'KubeGlobal.KUBERNETES_CONFIG -> Exception -> {0}'.format(e))


def get_kubernetes_conf_data():
    AgentLogger.debug(AgentLogger.KUBERNETES, 'GetKubernetesConfData')
    try:
        if KubeGlobal.KUBERNETES_CONFIG.has_section(KubeGlobal.configParserSection):
            AgentLogger.debug(AgentLogger.KUBERNETES, 'GetKubernetesConfData -> has section ')
            if KubeGlobal.KUBERNETES_CONFIG.has_option(KubeGlobal.configParserSection, KubeGlobal.configMidParam):
                KubeGlobal.mid = KubeGlobal.KUBERNETES_CONFIG.get(KubeGlobal.configParserSection, KubeGlobal.configMidParam)
            if KubeGlobal.KUBERNETES_CONFIG.has_option(KubeGlobal.configParserSection, KubeGlobal.configStatusParam):
                KubeGlobal.monStatus = KubeGlobal.KUBERNETES_CONFIG.get(KubeGlobal.configParserSection,KubeGlobal.configStatusParam)
            if KubeGlobal.KUBERNETES_CONFIG.has_option(KubeGlobal.configParserSection, KubeGlobal.sendConfigParam):
                KubeGlobal.sendConfig = KubeGlobal.KUBERNETES_CONFIG.get(KubeGlobal.configParserSection, KubeGlobal.sendConfigParam)
            if KubeGlobal.KUBERNETES_CONFIG.has_option(KubeGlobal.configParserSection, KubeGlobal.sendPerfParam):
                KubeGlobal.sendPerf = KubeGlobal.KUBERNETES_CONFIG.get(KubeGlobal.configParserSection, KubeGlobal.sendPerfParam)
            if KubeGlobal.KUBERNETES_CONFIG.has_option(KubeGlobal.configParserSection, KubeGlobal.configDCIntervalParam):
                KubeGlobal.sendConfigDataInterval = KubeGlobal.KUBERNETES_CONFIG.get(KubeGlobal.configParserSection,KubeGlobal.configDCIntervalParam)
            if KubeGlobal.KUBERNETES_CONFIG.has_option(KubeGlobal.configParserSection, KubeGlobal.childWriteCountParam):
                KubeGlobal.childWriteCount = KubeGlobal.KUBERNETES_CONFIG.get(KubeGlobal.configParserSection,KubeGlobal.childWriteCountParam)
                AgentLogger.log(AgentLogger.KUBERNETES,'KubeGlobal.childWriteCount - {0}'.format(KubeGlobal.childWriteCount))
            if KubeGlobal.KUBERNETES_CONFIG.has_option(KubeGlobal.configParserSection, KubeGlobal.kubeStateMetricsParam):
                KubeGlobal.kubeStateMetricsUrl = KubeGlobal.KUBERNETES_CONFIG.get(KubeGlobal.configParserSection, KubeGlobal.kubeStateMetricsParam)
            if KubeGlobal.KUBERNETES_CONFIG.has_option(KubeGlobal.configParserSection, KubeGlobal.clusterDNParam):
                KubeGlobal.clusterDN = KubeGlobal.KUBERNETES_CONFIG.get(KubeGlobal.configParserSection, KubeGlobal.clusterDNParam)
            if KubeGlobal.KUBERNETES_CONFIG.has_option(KubeGlobal.configParserSection, KubeGlobal.eventsEnabledParam):
                KubeGlobal.EVENTS_ENABLED = KubeGlobal.KUBERNETES_CONFIG.get(KubeGlobal.configParserSection, KubeGlobal.eventsEnabledParam)
    except Exception as e:
        AgentLogger.log(AgentLogger.KUBERNETES, 'GetKubernetesConfData -> Exception -> {0}'.format(e))


def getEnvVariables():
    AgentLogger.log(AgentLogger.KUBERNETES, 'getEnvVariables')
    write_config_param_dict = {}
    try:
        if "CLUSTER_NAME" in os.environ:
            KubeGlobal.clusterDN = os.environ["CLUSTER_NAME"]
            AgentLogger.log(AgentLogger.KUBERNETES, 'getEnvVariables - CLUSTER_NAME - {0}'.format(KubeGlobal.clusterDN))
            write_config_param_dict[KubeGlobal.clusterDNParam] = KubeGlobal.clusterDN
        if "API_SERVER_ENDPOINT_URL" in os.environ:
            KubeGlobal.apiEndpoint = os.environ["API_SERVER_ENDPOINT_URL"]
            AgentLogger.log(AgentLogger.KUBERNETES,'getEnvVariables - API_SERVER_ENDPOINT_URL - {0}'.format(KubeGlobal.apiEndpoint))
            write_config_param_dict[KubeGlobal.apiEndpointParam] = KubeGlobal.apiEndpoint
        if "KUBE_STATE_METRICS_URL" in os.environ:
            KubeGlobal.kubeStateMetricsUrl = os.environ["KUBE_STATE_METRICS_URL"]
            AgentLogger.log(AgentLogger.KUBERNETES, 'getEnvVariables - KUBE_STATE_METRICS_URL - {0}'.format(KubeGlobal.kubeStateMetricsUrl))
            write_config_param_dict[KubeGlobal.kubeStateMetricsParam] = KubeGlobal.kubeStateMetricsUrl
        if "NODE_NAME" in os.environ:
            KubeGlobal.nodeName = os.environ["NODE_NAME"]
            AgentLogger.log(AgentLogger.KUBERNETES, 'getEnvVariables - NODE_NAME - {0}'.format(KubeGlobal.nodeName))
        KubeUtil.write_kubernetes_dc_config_to_file(write_config_param_dict)
    except Exception as e:
        AgentLogger.log(AgentLogger.KUBERNETES, 'getEnvVariables -> Exception -> {0}'.format(e))


def fetch_global_settings_from_configmap():
    try:
        if os.path.exists(KubeGlobal.SETTINGS_JSON_FILE):
            with open(KubeGlobal.SETTINGS_JSON_FILE, 'r') as read_obj:
                settings_json = json.load(read_obj)
                for key, value in KubeGlobal.KUBE_GLOBAL_SETTINGS.items():
                    if key in settings_json:
                        KubeGlobal.KUBE_GLOBAL_SETTINGS[key] = settings_json[key]
                AgentLogger.log(AgentLogger.KUBERNETES, "Fetched global settings from configmap --> {}".format(KubeGlobal.KUBE_GLOBAL_SETTINGS))
                return True
    except Exception:
        traceback.print_exc()
    return False

def fetch_1min_settings_from_configmap():
    try:
        if os.path.exists(KubeGlobal.ONEMIN_JSON_FILE):
            with open(KubeGlobal.ONEMIN_JSON_FILE, 'r') as read_obj:
                settings_json = json.load(read_obj)
                for key, value in KubeGlobal.KUBE_INSTANT_DISCOVERY_SETTINGS.items():
                    if key in settings_json:
                        KubeGlobal.KUBE_INSTANT_DISCOVERY_SETTINGS[key] = settings_json[key]
                AgentLogger.log(AgentLogger.KUBERNETES, "Fetched 1min settings from configmap --> {}".format(KubeGlobal.KUBE_INSTANT_DISCOVERY_SETTINGS))
                return True
    except Exception:
        traceback.print_exc()
    return False

def load_kube_global_settings():
    if not fetch_global_settings_from_configmap():
        section = 'poll_interval'
        try:
            if KubeGlobal.KUBERNETES_CONFIG.has_section(section):
                existing_setting = dict(KubeGlobal.KUBERNETES_CONFIG.items(section))
                for option, value in KubeGlobal.KUBE_GLOBAL_SETTINGS.items():
                    if option in existing_setting:
                        KubeGlobal.KUBE_GLOBAL_SETTINGS[option] = existing_setting[option]
            else:
                KubeGlobal.KUBERNETES_CONFIG.add_section(section)
                KubeUtil.write_kubernetes_dc_config_to_file(KubeGlobal.KUBE_GLOBAL_SETTINGS, section)
            AgentLogger.log(AgentLogger.KUBERNETES, "Fetched global settings from config file --> {}".format(KubeGlobal.KUBE_GLOBAL_SETTINGS))
        except Exception as e:
            AgentLogger.log(AgentLogger.KUBERNETES, 'Exception -> load_res_based_poll_intrv_to_config {0}'.format(e))
            traceback.print_exc()

def load_1min_discovery_settings():
    if not fetch_1min_settings_from_configmap():
        section = 'resource_discovery'
        update_needed = False
        try:
            if KubeGlobal.KUBERNETES_CONFIG.has_section(section):
                existing_setting = KubeGlobal.KUBERNETES_CONFIG.items(section)
                for option, value in KubeGlobal.KUBE_INSTANT_DISCOVERY_SETTINGS.items():
                    if option in existing_setting:
                        KubeGlobal.KUBE_INSTANT_DISCOVERY_SETTINGS[option] = existing_setting[option]
                    else:
                        update_needed = True
            else:
                KubeGlobal.KUBERNETES_CONFIG.add_section(section)
                update_needed = True

            if update_needed:
                KubeUtil.write_kubernetes_dc_config_to_file(KubeGlobal.KUBE_INSTANT_DISCOVERY_SETTINGS, section)
            AgentLogger.log(AgentLogger.KUBERNETES, "Fetched 1min settings from config file --> {}".format(KubeGlobal.KUBE_INSTANT_DISCOVERY_SETTINGS))
        except Exception as e:
            AgentLogger.log(AgentLogger.KUBERNETES, 'Exception -> load_res_based_discovery_config {0}'.format(e))
            traceback.print_exc()

def add_to_registered_servers_configmap():
    try:
        status, response = KubeUtil.update_s247_configmap({
            'data': {
                os.getenv('NODE_NAME'): json.dumps({
                    'id': getattr(sys.modules['com.manageengine.monagent.util.AgentUtil'], 'AGENT_CONFIG').get('AGENT_INFO', 'agent_key'),
                    'UID': getattr(sys.modules['com.manageengine.monagent.AgentConstants'], 'SYSTEM_UUID'),
                    'time': time.time()
                })
            }
        })
        if status == 200:
            AgentLogger.log(AgentLogger.KUBERNETES, "Successfully added node_name into configmap for server termination")
            return
    except Exception:
        traceback.print_exc()
    KubeGlobal.NODE_AGENT_STATS['STT_NENA'] = os.getenv('NODE_NAME')

def add_ondemand_exec_dctask_list():
    from com.manageengine.monagent.kubernetes.Collector.YAMLFetcher import YAMLFetcher
    from com.manageengine.monagent.kubernetes.Collector.DataCollectorInterface import DCRequisites
    from com.manageengine.monagent.kubernetes.Collector.ResourceDependencyCollector import ResourceDependency

    dc_requisites_obj = DCRequisites()
    dc_requisites_obj.set_dc_name(YAMLFetcher.__name__.lower())
    dc_requisites_obj.set_child_write_count(70)
    dc_requisites_obj.set_dc_class(YAMLFetcher)
    dc_requisites_obj.set_split_data_required(True)
    dc_requisites_obj.get_from_cluster_agent(True)
    dc_requisites_obj.set_on_demand_exec_needed(True)
    dc_requisites_obj.set_cluster_req_type("POST")
    dc_requisites_obj.set_servlet_name('020')
    KubeGlobal.ONDEMAND_DCTASK_EXEC_LIST[YAMLFetcher.__name__.lower()] = dc_requisites_obj

    dc_requisites_obj = DCRequisites()
    dc_requisites_obj.set_dc_name(ResourceDependency.__name__.lower())
    dc_requisites_obj.set_dc_class(ResourceDependency)
    dc_requisites_obj.get_from_cluster_agent(True)
    dc_requisites_obj.set_on_demand_exec_needed(True)
    dc_requisites_obj.set_split_data_required(True)
    dc_requisites_obj.set_servlet_name('017')
    dc_requisites_obj.set_cluster_req_type("POST")
    KubeGlobal.ONDEMAND_DCTASK_EXEC_LIST[ResourceDependency.__name__.lower()] = dc_requisites_obj

def validate_kubelet_response():
    flag = 0
    try:
        for i in range(3):
            status, response = KubeUtil.curl_api_with_token('https://{}:10250/stats/summary'.format(KubeGlobal.IP_ADDRESS), False)
            if status == 200 and 'pods' in response:
                for pod in response['pods']:
                    if pod['memory'].get('workingSetBytes', 1) > 0 or pod['memory'].get('rssBytes', 1) > 0 or pod['memory'].get('usageBytes', 1) > 0:
                        flag = 0
                        AgentLogger.log(AgentLogger.KUBERNETES, "Kubelet error not detected !!!")
                        break
                    flag = 1
                if not flag:
                    break
    except Exception:
        traceback.print_exc()
    KubeGlobal.KUBELET_ERROR = flag or os.getenv('RKE', '').lower() == 'true'
