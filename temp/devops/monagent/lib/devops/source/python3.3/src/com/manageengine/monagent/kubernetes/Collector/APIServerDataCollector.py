import traceback

from com.manageengine.monagent.kubernetes import KubeGlobal, KubeUtil
from com.manageengine.monagent.kubernetes.Logging import KubeLogger as AgentLogger
from com.manageengine.monagent.kubernetes.Collector.DataCollectorInterface import DataCollector
from com.manageengine.monagent.kubernetes.Parser.PrometheusParser.APIServerMetricsParser import APIServerMetrics

def exception_handler(func):
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            AgentLogger.log(AgentLogger.KUBERNETES, "*** EXCEPTION *** => [APIServerDataCollector] => {} => {} => {} ******".format(func.__name__, e, traceback.format_exc()))
    return wrapper


class APIServerDataCollector(DataCollector):
    @exception_handler
    def __init__(self, dc_requisites_obj):
        super().__init__(dc_requisites_obj)
        self.api_server_config = {}
        self.apiserver_config_id = KubeGlobal.kubeIds.get("KubeAPIServer", {}) if KubeGlobal.kubeIds else {}

    @exception_handler
    def set_apiserver_termination(self):
        for reg_instance_key, instance_config in self.apiserver_config_id.items():
            if reg_instance_key not in self.final_json["KubeAPIServer"]:
                self.final_json["KubeAPIServer"][reg_instance_key] = instance_config
                self.final_json["KubeAPIServer"][reg_instance_key]["deleted"] = "true"
                self.final_json["perf"] = "false"
                AgentLogger.log(AgentLogger.KUBERNETES, '*** INFO *** => APIServer Instance marked as deleted -> {} = {}'.format(reg_instance_key, instance_config))

    @exception_handler
    def init_apiserver_dc(self):
        self.final_json["perf"] = "true"
        self.final_json["KubeAPIServer"] = {}
        for api_server_instance in self.api_server_config:
            self.final_json["KubeAPIServer"].update(getattr(APIServerMetrics(self.api_server_config[api_server_instance]), "final_data"))
            if self.apiserver_config_id and api_server_instance in self.apiserver_config_id:
                self.final_json["KubeAPIServer"][api_server_instance]["id"] = self.apiserver_config_id[api_server_instance]["id"]
            else:
                self.final_json["KubeAPIServer"][api_server_instance]["id"] = ""
                self.final_json["perf"] = "false"


    @exception_handler
    def init_apiserver_config(self):
        api_url = KubeGlobal.apiEndpoint+KubeGlobal.API_ENDPOINT_RES_NAME_MAP["KubeAPIServer"]
        status, cp_node_data = KubeUtil.curl_api_with_token(api_url)

        if status == 200 and "items" in cp_node_data and cp_node_data["items"] and cp_node_data["items"][0]:
            cp_node = cp_node_data["items"][0]
            if "subsets" in cp_node and cp_node["subsets"][0]:
                endpoint_data = cp_node["subsets"][0]
                if "addresses" in endpoint_data and endpoint_data["addresses"] and "ports" in endpoint_data and endpoint_data["ports"][0]:
                    if endpoint_data["ports"][0]["name"] in ["https"] and "port" in endpoint_data["ports"][0]:
                        port = endpoint_data["ports"][0]["port"]
                        if KubeGlobal.clusterDistribution == "EKS" and KubeUtil.is_conf_agent():
                            for each_ip in endpoint_data["addresses"]:
                                self.api_server_config[str(each_ip["ip"])+":"+str(port)] = { "ip": each_ip["ip"], "port": str(port), "eks": True}
                            AgentLogger.log(AgentLogger.KUBERNETES, '*** DATA *** => [Conf] APIServer Instance Present in EKS Cluster')
                        elif KubeGlobal.clusterDistribution == "EKS" and not KubeUtil.is_conf_agent():
                            AgentLogger.log(AgentLogger.KUBERNETES, '*** DATA *** => [Perf] APIServer DC skipped for Perf Node in EKS Cluster')
                        else:
                            for each_ip in endpoint_data["addresses"]:
                                if each_ip["ip"] == KubeGlobal.IP_ADDRESS or each_ip["ip"] in KubeGlobal.IP_ADDRESS or KubeGlobal.IP_ADDRESS in each_ip["ip"]:
                                    self.api_server_config[str(each_ip["ip"])+":"+str(port)] = { "ip": each_ip["ip"], "port": str(port) }
                                    AgentLogger.log(AgentLogger.KUBERNETES, '*** DATA *** => Current Node Identified as APIServer')
                    else:
                        AgentLogger.log(AgentLogger.KUBERNETES, '*** INFO *** => APIServer Port data not found -> {} = {}'.format("apiserver",endpoint_data))
                else:
                    AgentLogger.log(AgentLogger.KUBERNETES, '*** INFO *** => APIServer data not found -> {} = {}'.format("apiserver",endpoint_data))
            else:
                AgentLogger.log(AgentLogger.KUBERNETES, '*** INFO *** => APIServer subset data not found -> {} = {}'.format("apiserver",cp_node))
        AgentLogger.log(AgentLogger.KUBERNETES, '*** DATA *** => APIServer Components Data -> {}'.format(self.api_server_config))

    @exception_handler
    def collect_data(self):
        self.init_apiserver_config()
        self.init_apiserver_dc()
        self.set_apiserver_termination()
        AgentLogger.debug(AgentLogger.KUBERNETES, '*** DEBUG *** => APIServer Collected Data -> \n{}\n'.format(self.final_json))
