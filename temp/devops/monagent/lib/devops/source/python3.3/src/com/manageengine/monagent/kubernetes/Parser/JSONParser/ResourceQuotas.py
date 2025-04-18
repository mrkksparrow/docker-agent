from com.manageengine.monagent.kubernetes.Parser.JSONParserInterface import JSONParser
from com.manageengine.monagent.kubernetes import KubeUtil, KubeGlobal
import json


class ResourceQuota(JSONParser):
    def __init__(self):
        super().__init__('ResourceQuota')

    def get_root_name(self):
        return self.raw_data['metadata']['namespace']

    def save_value_dict(self, root_name):
        self.final_dict[root_name] = self.final_dict[root_name] if root_name in self.final_dict else {"ResourceQuota": {}}
        self.final_dict[root_name]['ResourceQuota'][self.raw_data['metadata']['name']] = self.value_dict

    def get_metadata(self):
        super().get_metadata()
        self.value_dict['id'] = (KubeGlobal.kubeIds.get("Namespaces", {})
                                 .get(self.raw_data['metadata']['namespace'], {})
                                 .get("ResourceQuota", {})
                                 .get("id"))
        self.value_dict['Lb'] = json.dumps(self.get_2nd_path_value(['metadata', 'labels'], ""))
        self.value_dict['An'] = json.dumps(self.get_2nd_path_value(['metadata', 'annotations'], ""))
        self.value_dict['scope_selector'] = json.dumps(self.get_2nd_path_value(['spec', 'scopeSelector'], ""))

    def get_perf_metrics(self):
        for key, value in self.raw_data['spec']['hard'].items():
            self.value_dict[key.replace('.', '_') + '_max'] = KubeUtil.convert_values_to_standard_units(value)

        for key, value in self.raw_data['status']['used'].items():
            replaced_key = key.replace('.', '_')
            converted_value = KubeUtil.convert_values_to_standard_units(value)
            self.value_dict[replaced_key + '_used'] = converted_value
            self.value_dict[replaced_key + '_percentage'] = float(converted_value) / float(self.value_dict[replaced_key + '_max'])




