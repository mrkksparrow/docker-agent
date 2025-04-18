import copy
import traceback

from com.manageengine.monagent.kubernetes import KubeGlobal, KubeUtil
from com.manageengine.monagent.kubernetes.Logging import KubeLogger as AgentLogger
from com.manageengine.monagent.kubernetes.Collector.DataCollectorInterface import DataCollector
from com.manageengine.monagent.kubernetes.Parser.ParserFactory import get_json_parser


def exception_handler(func):
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            AgentLogger.log(AgentLogger.KUBERNETES, "*** EXCEPTION *** => [InstantDiscoveryDataCollector] => {} => {} => {} ******".format(func.__name__, e, traceback.format_exc()))
    return wrapper


class InstantDiscoveryDataCollector(DataCollector):
    @exception_handler
    def __init__(self, dc_requisites_obj):
        super().__init__(dc_requisites_obj)
        self.instant_discovery_resource = [
            "Nodes",
            "Pods",
            "Namespaces",
            "DaemonSets",
            "HorizontalPodAutoscalers",
            "Deployments",
            "ReplicaSets",
            "StatefulSets",
            "Services",
            "PV",
            "PersistentVolumeClaim",
            "Jobs",
            "Ingresses",
        ] if KubeUtil.is_conf_agent() else [
            "Pods"
        ]

    def get_cluster_agent_request_params(self):
        return {
            'RCS': KubeGlobal.DISCOVERED_RESOURCE_CONFIG_STORAGE,
            'NODE_NAME': KubeGlobal.KUBELET_NODE_NAME
        }

    def get_data_for_cluster_agent(self, req_params=None):
        KubeGlobal.DISCOVERED_RESOURCE_CONFIG_STORAGE = req_params['RCS']
        KubeGlobal.KUBELET_NODE_NAME = req_params['NODE_NAME']
        return super().get_data_for_cluster_agent()

    def get_from_cluster_agent(self):
        if super().get_from_cluster_agent():
            for res_type, resources in self.final_json.items():
                if isinstance(resources, dict):
                    for res_name, res_config in resources.items():
                        if 'deleted' in res_config and res_type in KubeGlobal.DISCOVERED_RESOURCE_CONFIG_STORAGE:
                            KubeGlobal.DISCOVERED_RESOURCE_CONFIG_STORAGE[res_type].pop(res_name, None)

    @exception_handler
    def collect_data(self):
        for resource in self.instant_discovery_resource:
            if resource in KubeGlobal.KUBE_INSTANT_DISCOVERY_SETTINGS and int(KubeGlobal.KUBE_INSTANT_DISCOVERY_SETTINGS[resource]) != -1:
                resource_obj = get_json_parser(resource)()
                self.final_json[resource] = resource_obj.get_data(discovery=True)

        if [resource for resource in self.final_json if self.final_json[resource]]:
            self.final_json["perf"] = "false"

        AgentLogger.debug(AgentLogger.KUBERNETES, "*** @@InstantDiscoveryDataCollector@@ *** => \n{}\n ******".format(self.final_json))
