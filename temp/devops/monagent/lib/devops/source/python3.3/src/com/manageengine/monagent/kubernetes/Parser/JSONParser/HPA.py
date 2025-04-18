import json
from com.manageengine.monagent.kubernetes.Parser.JSONParserInterface import JSONParser
from com.manageengine.monagent.kubernetes import KubeUtil


class HPA(JSONParser):
    def __init__(self):
        super().__init__('HorizontalPodAutoscalers')

    def get_metadata(self):
        super().get_metadata()
        self.value_dict['An'] = json.dumps(self.get_2nd_path_value(['metadata', 'annotations'], {}))
        self.value_dict['Lb'] = json.dumps(self.get_2nd_path_value(['metadata', 'labels'], {}))
        self.value_dict['MLb'] = json.dumps(self.get_3rd_path_value(['spec', 'selector', 'matchLabels'], {}))
        self.value_dict['KHSMiR'] = self.get_2nd_path_value(['spec', 'minReplicas'])
        self.value_dict['KHSMaR'] = self.get_2nd_path_value(['spec', 'maxReplicas'])
        self.value_dict['Ki'] = self.get_3rd_path_value(['spec', 'scaleTargetRef', 'kind'])
        self.value_dict['SSCTNa'] = self.get_3rd_path_value(['spec', 'scaleTargetRef', 'name'])

    def get_perf_metrics(self):
        self.value_dict['LST'] = self.get_2nd_path_value(['status', 'lastScaleTime'])
        self.value_dict['KHSCR'] = self.get_2nd_path_value(['status', 'currentReplicas'])
        self.value_dict['DR'] = self.get_2nd_path_value(['status', 'desiredReplicas'])
        self.value_dict['CCPUUP'] = self.get_2nd_path_value(['status', 'currentCPUUtilizationPercentage'])
        self.value_dict['KHSMaOut'] = self.get_2nd_path_value(['spec', 'maxReplicas']) - self.get_2nd_path_value(['status', 'currentReplicas'], 0)  # Replicas maxed out
        self.value_dict["Cnds"] = self.get_hpa_current_condition()

        for resource_type in self.get_2nd_path_value(['spec', 'metrics'], {}):
            if resource_type["type"] == "Resource" and resource_type["resource"]["name"] == "memory":
                self.value_dict["TMEMUP"] = resource_type["resource"]["target"]["averageUtilization"]
            if resource_type["type"] == "Resource" and resource_type["resource"]["name"] == "cpu":
                self.value_dict["TCPUUP"] = resource_type["resource"]["target"]["averageUtilization"]

        for resource_type in self.get_2nd_path_value(['status', 'currentMetrics'], {}):
            if resource_type["type"] == "Resource" and resource_type["resource"]["name"] == "memory":
                self.value_dict["CMEMUP"] = resource_type["resource"]["current"]["averageUtilization"]
                self.value_dict["CMEMUV"] = int(KubeUtil.convert_values_to_standard_units(resource_type["resource"]["current"]["averageValue"]))
            if resource_type["type"] == "Resource" and resource_type["resource"]["name"] == "cpu":
                self.value_dict["CCPUUP"] = resource_type["resource"]["current"]["averageUtilization"]
                self.value_dict["CCPUUV"] = int(KubeUtil.convert_cpu_values_to_standard_units(resource_type["resource"]["current"]["averageValue"]))

    def get_hpa_current_condition(self):
        cnds = {}
        for condition_type in self.get_2nd_path_value(['status', 'conditions'], {}):
            type_name = condition_type["type"]
            cnds[type_name] = {
                "Ty": type_name,
                "Sts": condition_type["status"],
                "Rsn": condition_type["reason"],
                "Msg": condition_type["message"]
            }
        return cnds
