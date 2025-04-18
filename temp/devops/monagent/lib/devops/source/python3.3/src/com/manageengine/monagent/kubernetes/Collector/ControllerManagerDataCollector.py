import traceback

from com.manageengine.monagent.kubernetes import KubeGlobal, KubeUtil
from com.manageengine.monagent.kubernetes.Logging import KubeLogger as AgentLogger
from com.manageengine.monagent.kubernetes.Collector.DataCollectorInterface import DataCollector
from com.manageengine.monagent.kubernetes.Parser.PrometheusParser.ControllerManagerMetricsParser import ControllerManagerMetrics

def exception_handler(func):
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            AgentLogger.log(AgentLogger.KUBERNETES, "*** EXCEPTION *** => [ControllerManagerDataCollector] => {} => {} => {} ******".format(func.__name__, e, traceback.format_exc()))
    return wrapper


class ControllerManagerDataCollector(DataCollector):
    @exception_handler
    def __init__(self, dc_requisites_obj):
        super().__init__(dc_requisites_obj)
        self.controller_manager_config = {}
        self.controllermanager_config_id = KubeGlobal.kubeIds.get("KubeControllerManager", {}) if KubeGlobal.kubeIds else {}

    @exception_handler
    def set_controllermanager_termination(self):
        for reg_instance_key, instance_config in self.controllermanager_config_id.items():
            if reg_instance_key not in self.final_json["KubeControllerManager"]:
                self.final_json["KubeControllerManager"][reg_instance_key] = instance_config
                self.final_json["KubeControllerManager"][reg_instance_key]["deleted"] = "true"
                self.final_json["perf"] = "false"
                AgentLogger.log(AgentLogger.KUBERNETES, '*** INFO *** => ControllerManager Instance marked as deleted -> {} = {}'.format(reg_instance_key, instance_config))

    @exception_handler
    def init_controllermanager_dc(self):
        self.final_json["perf"] = "true"
        self.final_json["KubeControllerManager"] = {}
        for controller_manager_instance in self.controller_manager_config:
            self.final_json["KubeControllerManager"].update(getattr(ControllerManagerMetrics(self.controller_manager_config[controller_manager_instance]), "final_data"))
            if self.controllermanager_config_id and controller_manager_instance in self.controllermanager_config_id:
                self.final_json["KubeControllerManager"][controller_manager_instance]["id"] = self.controllermanager_config_id[controller_manager_instance]["id"]
            else:
                self.final_json["KubeControllerManager"][controller_manager_instance]["id"] = ""
                self.final_json["perf"] = "false"

    @exception_handler
    def init_controller_manager_config(self):
        api_url = KubeGlobal.host+KubeGlobal.API_ENDPOINT_RES_NAME_MAP["KubeControllerManager"]
        status, cp_node_data = KubeUtil.curl_api_with_token(api_url)

        if status == 200 and "items" in cp_node_data and cp_node_data["items"] and cp_node_data["items"][0]:
            cp_node = cp_node_data["items"][0]
            if "subsets" in cp_node and cp_node["subsets"][0]:
                endpoint_data = cp_node["subsets"][0]
                if "addresses" in endpoint_data and endpoint_data["addresses"] and "ports" in endpoint_data and endpoint_data["ports"][0]:
                    if endpoint_data["ports"][0]["name"] in ["https"] and "port" in endpoint_data["ports"][0]:
                        port = endpoint_data["ports"][0]["port"]
                        for each_ip in endpoint_data["addresses"]:
                            self.controller_manager_config[str(each_ip["ip"])+":"+str(port)] = { "ip": each_ip["ip"], "port": str(port) }
                        AgentLogger.log(AgentLogger.KUBERNETES, '*** DATA *** => [Conf] Controller Manager Instance Present in Cluster')
                    else:
                        AgentLogger.log(AgentLogger.KUBERNETES, '*** INFO *** => Controller Manager Port data not fount -> {} = {}'.format("controller manager",endpoint_data))
                else:
                    AgentLogger.log(AgentLogger.KUBERNETES, '*** INFO *** => Controller Manager data not fount -> {} = {}'.format("controller manager",endpoint_data))
            else:
                AgentLogger.log(AgentLogger.KUBERNETES, '*** INFO *** => Controller Manager subset data not fount -> {} = {}'.format("controller manager",cp_node))
        AgentLogger.log(AgentLogger.KUBERNETES, '*** DATA *** => Controller Manager Components Data -> {}'.format(self.controller_manager_config))

    @exception_handler
    def collect_data(self):
        self.init_controller_manager_config()
        self.init_controllermanager_dc()
        self.set_controllermanager_termination()
        AgentLogger.debug(AgentLogger.KUBERNETES, '*** DEBUG *** => ControllerManager Collected Data -> \n{}\n'.format(self.final_json))
