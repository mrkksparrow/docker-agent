import os
import time
import configparser
import traceback

from com.manageengine.monagent.kubernetes.Logging import KubeLogger as AgentLogger

try:
    import requests
    REQUEST_MODULE = requests
except Exception as e:
    REQUEST_MODULE = None

KUBERNETES_CONFIG = configparser.RawConfigParser()

#constants
configParserSection = "kubernetes"
configMidParam = "mid"
configStatusParam = "enabled"
sendConfigParam = "sendConfig"
sendPerfParam = "sendPerf"
childWriteCountParam = "childWriteCount"
configDCIntervalParam = "configDCInterval"
apiEndpointParam = "apiServerEndpointUrl"
kubeStateMetricsParam = "kubestateMetricsUrl"
clusterDNParam = "clusterDisplayName"
eventsEnabledParam = "eventsEnabled"
eventsWriteCountParam="eventswritecount"
confData = ["[kubernetes] \n","enabled=1 \n","mid=0 \n","sendConfig=true \n","sendPerf=true \n","configDCInterval=15 \n","childWriteCount=500 \n","apiServerEndpointUrl= \n","kubestateMetricsUrl= \n","clusterDisplayName= \n","eventsEnabled=true \n", "eventswritecount=500 \n"] #configDCInterval in mins
KSM_MATCH_LABELS = [
    ("app.kubernetes.io/name", "site24x7-kube-state-metrics"),
    ("app", "site24x7-kube-state-metrics"),
    ("app.kubernetes.io/name", "kube-state-metrics"),
    ("k8s-app", "kube-state-metrics")
]
RES_BASED_LAST_DC_TIME = {}
PROMETHEUS_COUNTER_DATA_STORAGE = {}
PROMETHEUS_ONCHANGE_DATA_STORAGE = {}
DISCOVERED_RESOURCE_CONFIG_STORAGE = {}
PROVIDER = "Self-Managed"
CLUSTER_AGENT_SVC = None
DC_START_TIME = None
API_ENDPOINT_RES_NAME_MAP = {
    "Nodes": "/api/v1/nodes?limit=500",
    "Pods": "/api/v1/pods?limit=500",
    "Deployments": "/apis/apps/v1/deployments?limit=500",
    "DaemonSets": "/apis/apps/v1/daemonsets?limit=500",
    "Namespaces": "/api/v1/namespaces?limit=500",
    "Endpoints": "/api/v1/endpoints?limit=500",
    "HorizontalPodAutoscalers": "/apis/autoscaling/v1/horizontalpodautoscalers?limit=500",
    "Services": "/api/v1/services?limit=500",
    "ReplicaSets": "/apis/apps/v1/replicasets?limit=500",
    "StatefulSets": "/apis/apps/v1/statefulsets?limit=500",
    "PV": "/api/v1/persistentvolumes?limit=500",
    "PersistentVolumeClaim": "/api/v1/persistentvolumeclaims?limit=500",
    "Jobs": "/apis/batch/v1/jobs?limit=500",
    "Ingresses": "/apis/networking.k8s.io/v1/ingresses?limit=500",
    "ResourceQuota": "/api/v1/resourcequotas?limit=500",
    "kubeletStatsProxy": "/api/v1/nodes/{}/proxy/stats/summary",
    "kubeletCAdvisorProxy": "/api/v1/nodes/{}/proxy/metrics/cadvisor",
    "KubeAPIServer": "/api/v1/endpoints?fieldSelector=metadata.name=kubernetes",
    "KubeControllerManager": "/api/v1/endpoints?fieldSelector=metadata.name=kube-controller-manager",
}


"""
Settings for all resource types, dc types
key-value (type_name, value) pair, value should in below form
-1: not eligible
1: eligible
any other value in secs will be considered as as interval
"""
KUBE_GLOBAL_SETTINGS = {
    "kubernetes": "300",
    "daemonsets": "300",
    "deployments": "300",
    "statefulsets": "300",
    "pods": "300",
    "nodes": "300",
    "services": "300",
    "replicasets": "900",
    "ingresses": "300",
    "jobs": "300",
    "pv": "300",
    "persistentvolumeclaim": "300",
    "componentstatuses": "300",
    "horizontalpodautoscalers": "300",
    "endpoints": "3600",
    "namespaces": "300",
    "eventcollector": "60",
    "npcdatacollector": "300",
    "instantdiscoverydatacollector": "60",
    "apiserverdatacollector": "300",
    "controllermanagerdatacollector": "300",
    "npcdatacollector_discovery": "900",
    "resourcedependency": "300",
    "workloadsdatacollector": "300",
    "workloadsdatacollector_discovery": "900",
    "clustermetricsaggregator": "300",
    "sidecarnpccollector": "300",
    "sidecarnpccollector_discovery": "900",
    "dcinit": "900",
    "clusteragent": "1",
    "ksm": "1",
    "guidancemetrics": "20600",
    "termination": "900",
    "kubelet": "300",
    "metadata": "20600",
    "prometheus_integration": "1",
    "plugin_integration": "1",
    "database_integration": "1",
    "ksmprocessor": "1",
    "kubeletdatapersistence": "1",
    "servicerelationdataprocessor": "1",
    "skip_podip_check": "-1",
    "metricsserveraggregator": "-1",
    "serverterminationtask": "900",
    "yamlfetcher": "60",
    "resourcedependency_ondemand": "20",
    "resourcedependency_complete": "3600",
    "kubeproxymetriccollector": "300",
    "yamlfetcher_retry": "1200"
}

KUBE_INSTANT_DISCOVERY_SETTINGS = {
    "Pods": "90",
    "Nodes": "90",
    "Namespaces": "90",
    "HorizontalPodAutoscalers": "-1",
    "DaemonSets": "90",
    "Deployments": "60",
    "Endpoints": "-1",
    "ReplicaSets": "-1",
    "StatefulSets": "90",
    "Services": "-1",
    "PV": "-1",
    "PersistentVolumeClaims": "-1",
    "Jobs": "-1",
    "Ingresses": "-1",
}



# files
CONF_FILE = '/opt/site24x7/monagent/conf/apps/kubernetes/kubernetes.cfg'
SETTINGS_JSON_FILE = '/etc/site24x7/clusterconfig/SETTINGS'
ONEMIN_JSON_FILE = '/etc/site24x7/clusterconfig/1MIN'

# Servlet
KDR_SERVLET = '/dp/kb/KubernetesDataReceiver?'
RD_SERVLET = '/dp/kb/ResourceDependencyServlet?'
KUBE_ACTION_SERVLET = '/dp/kb/KubeActionServlet?'

#kubernetes cluster details
kubernetesPresent = False
kubeServer = ""
kubeCluster = ""
kubeUniqueID = None
kubePlatform = None
kubeNamespace = ""
nodeType = ""
isContainerAgent = False
apiEndpoint = "https://kubernetes.default"
kubeStateMetricsUrl = ""
clusterDN = ""
clusterDistribution = ""
nodeName = ""
fargate = False
mid = None
monStatus = 0
gkeAutoPilot = False
nonMountedAgent = False
isConfDc = False
isTerminationDc = False

#other configs       
childWriteCount = "500"
urlTimeout = 30
sendConfig = "true"
sendPerf = "true"
eventsWriteCount = "500"
PERF_POLL_INTERVAL = "300"
IP_ADDRESS = None
NODE_AGENT_UPGRADE_LOCK_FILE = '/opt/site24x7/monagent/temp/upgrade-lock.txt'
KUBELET_ERROR = False

# api data
CONFIGMAP_INTEG_DATA = {}
NODE_BASE_PODS_CONFIGS = {}

#secrets
serviceAccPath = "/var/run/secrets/kubernetes.io/serviceaccount"
bearerToken = ""
host = "https://kubernetes.default"
clusterDNPATH = "/api/v1/configmaps?fieldSelector=metadata.name=kube-proxy"
kubeletPath = "/api/v1/nodes/{}/proxy/"
kubeStatePodIP = None #10.244.1.120
kubeStatePort = "8080"
kubeletStatsPort = "10250"
gkeClusterNameEndpoint = "http://metadata.google.internal/computeMetadata/v1/instance/attributes/cluster-name"
s247ConfigMapPath = "/api/v1/namespaces/{}/configmaps/site24x7"

#Events Constants
EVENTS_ENABLED = "true"
eventsListenerPath = "/apis/events.k8s.io/v1/events?limit=500"

#on change data configs
prevConfigDataTime = -1
sendConfigDataInterval = 5 * 60 * 60 #in secs

#id configs
kubeIds = {}
KUBELET_NODE_NAME = ''
NO_NS_UNIQUNESS_TYPES=["Namespaces","Nodes","PV", "KubeAPIServer"]
TERMINATION_NOT_SUPPORTED_GRPS = ["ResourceQuota", "ComponentStatuses", "KubeAPIServer", "KubeControllerManager", "KubeProxy"]
YAML_SUPPORTED_TYPES = ['DaemonSets', 'Deployments', 'StatefulSets', 'PV', 'PersistentVolumeClaim', 'Ingresses', 'Nodes', 'Services']
CLUSTER_POD_LIST = []

# CLUSTER AGENT
CLUSTER_AGENT_VERSION = '100'
LOWEST_SUPPORTED_CLUSTER_AGENT_VERSION = 100
IS_CLUSTER_AGENT = False
CLUSTER_AGENT_SRC = ''
CONF_FOLDER_PATH = ''
CLUSTER_AGENT_WORKING_DIR = ''
LOGS_FOLDER_PATH = ''
PARSED_DATA_FOLDER_PATH = ''
DETAILS_LOGS_FOLDER_PATH = ''
KUBE_CONF_FOLDER_PATH = ''
DATA_TYPE_PARSED_FILE_MAP = ''
KSM_OUTPUT_FILE = ''
CLUSTER_AGENT_UPGRADE_LOCK_FILE = ''
HELPER_TASK_STATS_FILE = ''
CLUSTER_AGENT_STATS = {}
NODE_AGENT_STATS = {}
CLUSTER_AGENT_URL_DATA_TYPE_MAP = {}
CLUSTER_AGENT_DC_OBJS_LIST = {}
NODE_BASE_KSM = {
    'lut': time.time()
}
INTEG_CONFIGMAP_RESOURCE_VERSION = 0
S247_CONFIGMAP_RESOURCE_VERSION = 0
S247_CONFIGMAP_SYSTEM_KEYS = ['SETTINGS', 'NODE_AGENT_VERSION', 'CLUSTER_AGENT_VERSION', '1MIN']
RESOURCE_VERSIONS = {
    "Nodes": {},
    "Pods": {},
    "Deployments": {},
    "DaemonSets": {},
    "Namespaces": {},
    "Endpoints": {},
    "HorizontalPodAutoscalers": {},
    "Services": {},
    "ReplicaSets": {},
    "StatefulSets": {},
    "PV": {},
    "PersistentVolumeClaim": {},
    "Jobs": {},
    "Ingresses": {},
    "ResourceQuota": {}
}
ONDEMAND_DCTASK_EXEC_LIST = {}

def set_cluster_agent_constants(src_path):
    global IS_CLUSTER_AGENT, CLUSTER_AGENT_SRC, CONF_FOLDER_PATH, CLUSTER_AGENT_WORKING_DIR, LOGS_FOLDER_PATH, PARSED_DATA_FOLDER_PATH, DETAILS_LOGS_FOLDER_PATH, KUBE_CONF_FOLDER_PATH, DATA_TYPE_PARSED_FILE_MAP, KSM_OUTPUT_FILE, CLUSTER_AGENT_UPGRADE_LOCK_FILE, HELPER_TASK_STATS_FILE, CLUSTER_AGENT_STATS

    CLUSTER_AGENT_SRC = src_path
    CONF_FOLDER_PATH = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(src_path))))) + '/conf'
    CLUSTER_AGENT_WORKING_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(src_path)))))
    LOGS_FOLDER_PATH = CLUSTER_AGENT_WORKING_DIR + '/logs'
    PARSED_DATA_FOLDER_PATH = CLUSTER_AGENT_WORKING_DIR + '/parsed_data'
    DETAILS_LOGS_FOLDER_PATH = LOGS_FOLDER_PATH + '/details'
    KUBE_CONF_FOLDER_PATH = src_path + '/com/manageengine/monagent/kubernetes/Conf'
    CLUSTER_AGENT_UPGRADE_LOCK_FILE = CONF_FOLDER_PATH + '/upgrade_lock_file.txt'
    DATA_TYPE_PARSED_FILE_MAP = {
        'npc_ksm': 'npc_ksm_parsed_data.json',
        'service_rs': 'service_rs.json',
        'service_pod_map': 'service_pod_map.json',
        'service_endpoints': 'service_endpoints.json',
        'rs_deploy_map': 'rs_deploy_map.json',
        'resource_dependency_ksm': 'resource_dependency_ksm.json',
        'all_kubelet': 'all_kubelet.json'
    }
    CLUSTER_AGENT_STATS = {
        'helpertasks': {}
    }
    HELPER_TASK_STATS_FILE = PARSED_DATA_FOLDER_PATH + '/stats.json'
    IS_CLUSTER_AGENT = True
    KSM_OUTPUT_FILE = PARSED_DATA_FOLDER_PATH + '/{}'.format('ksm_output.txt')
    create_cluster_agent_dc_objs()

def create_cluster_agent_dc_objs():
    global CLUSTER_AGENT_DC_OBJS_LIST
    from com.manageengine.monagent.kubernetes.Collector.ClusterMetricsAggregator import ClusterMetricsAggregator
    from com.manageengine.monagent.kubernetes.Collector.ClusterWorkloadsDataCollector import WorkloadsDataCollector
    from com.manageengine.monagent.kubernetes.Collector.GuidanceMetrics import GuidanceMetrics
    from com.manageengine.monagent.kubernetes.Collector.DataCollectorInterface import DCRequisites
    from com.manageengine.monagent.kubernetes.Collector.ResourceDependencyCollector import ResourceDependency
    from com.manageengine.monagent.kubernetes.Collector.EventCollector import EventCollector
    from com.manageengine.monagent.kubernetes.Collector.MetricsServerAggregator import MetricsServerAggregator
    from com.manageengine.monagent.kubernetes.Collector.YAMLFetcher import YAMLFetcher
    from com.manageengine.monagent.kubernetes.Collector.InstantDiscoveryDataCollector import InstantDiscoveryDataCollector
    from com.manageengine.monagent.kubernetes.Collector.ServerTerminationTask import ServerTerminationTask

    dc_requisites_obj = DCRequisites()
    dc_requisites_obj.set_dc_name(ClusterMetricsAggregator.__name__.lower())
    dc_requisites_obj.set_dc_class(ClusterMetricsAggregator)
    CLUSTER_AGENT_DC_OBJS_LIST[dc_requisites_obj.dc_name] = dc_requisites_obj

    dc_requisites_obj = DCRequisites()
    dc_requisites_obj.set_dc_name(GuidanceMetrics.__name__.lower())
    dc_requisites_obj.set_dc_class(GuidanceMetrics)
    CLUSTER_AGENT_DC_OBJS_LIST[dc_requisites_obj.dc_name] = dc_requisites_obj

    dc_requisites_obj = DCRequisites()
    dc_requisites_obj.set_dc_name(WorkloadsDataCollector.__name__.lower())
    dc_requisites_obj.set_dc_class(WorkloadsDataCollector)
    CLUSTER_AGENT_DC_OBJS_LIST[dc_requisites_obj.dc_name] = dc_requisites_obj

    dc_requisites_obj = DCRequisites()
    dc_requisites_obj.set_dc_name(ResourceDependency.__name__.lower())
    dc_requisites_obj.set_dc_class(ResourceDependency)
    CLUSTER_AGENT_DC_OBJS_LIST[dc_requisites_obj.dc_name] = dc_requisites_obj

    dc_requisites_obj = DCRequisites()
    dc_requisites_obj.set_dc_name(EventCollector.__name__.lower())
    dc_requisites_obj.set_dc_class(EventCollector)
    CLUSTER_AGENT_DC_OBJS_LIST[dc_requisites_obj.dc_name] = dc_requisites_obj

    dc_requisites_obj = DCRequisites()
    dc_requisites_obj.set_dc_name(MetricsServerAggregator.__name__.lower())
    dc_requisites_obj.set_dc_class(MetricsServerAggregator)
    CLUSTER_AGENT_DC_OBJS_LIST[dc_requisites_obj.dc_name] = dc_requisites_obj

    dc_requisites_obj = DCRequisites()
    dc_requisites_obj.set_dc_name(InstantDiscoveryDataCollector.__name__.lower())
    dc_requisites_obj.set_dc_class(InstantDiscoveryDataCollector)
    CLUSTER_AGENT_DC_OBJS_LIST[dc_requisites_obj.dc_name] = dc_requisites_obj

    dc_requisites_obj = DCRequisites()
    dc_requisites_obj.set_dc_name(YAMLFetcher.__name__.lower())
    dc_requisites_obj.set_dc_class(YAMLFetcher)
    CLUSTER_AGENT_DC_OBJS_LIST[dc_requisites_obj.dc_name] = dc_requisites_obj

    dc_requisites_obj = DCRequisites()
    dc_requisites_obj.set_dc_name(ServerTerminationTask.__name__.lower())
    dc_requisites_obj.set_dc_class(ServerTerminationTask)
    CLUSTER_AGENT_DC_OBJS_LIST[dc_requisites_obj.dc_name] = dc_requisites_obj

def set_mid(newMid):
    try:
        global mid
        if newMid and newMid!=mid:
            AgentLogger.log(AgentLogger.KUBERNETES,'KubeGlobal :: setting mid - '.format(newMid))
            mid = newMid
    except Exception as e:
        AgentLogger.log(AgentLogger.KUBERNETES,'KubeGlobal :: setmid -> Exception -> {0}'.format(e))

def set_mon_status(newMonStatus):
    try:
        global monStatus
        if newMonStatus and newMonStatus!=monStatus:
            AgentLogger.log(AgentLogger.KUBERNETES,'KubeGlobal :: setting monStatus - '.format(newMonStatus))
            monStatus = newMonStatus
    except Exception as e:
        AgentLogger.log(AgentLogger.KUBERNETES,'KubeGlobal :: setmid -> Exception -> {0}'.format(e))