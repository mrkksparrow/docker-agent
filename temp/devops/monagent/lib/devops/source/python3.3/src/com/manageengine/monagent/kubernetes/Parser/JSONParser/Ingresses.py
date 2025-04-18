from com.manageengine.monagent.kubernetes.Parser.JSONParserInterface import JSONParser
import json


class Ingresses(JSONParser):
    def __init__(self):
        super().__init__('Ingresses')

    def get_metadata(self):
        super().get_metadata()
        self.value_dict['An'] = json.dumps(self.get_2nd_path_value(['metadata', 'annotations'], ""))
        self.value_dict['ICN'] = self.get_2nd_path_value(['spec', 'ingressClassName'], "")
        self.value_dict['Ru'] = json.dumps(self.get_2nd_path_value(['spec', 'rules'], []))

    def get_perf_metrics(self):
        self.value_dict['St'] = json.dumps(self.get_1st_path_value(['status'], {}))
