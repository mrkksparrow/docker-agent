import json
from com.manageengine.monagent.kubernetes.Parser.JSONParserInterface import JSONParser


class ReplicaSets(JSONParser):
    def __init__(self):
        super().__init__('ReplicaSets')

    def get_metadata(self):
        super().get_metadata()
        self.value_dict['An'] = json.dumps(self.get_2nd_path_value(['metadata', 'annotations']))
        self.value_dict['Lb'] = json.dumps(self.get_2nd_path_value(['metadata', 'labels']))
        self.value_dict['MLb'] = json.dumps(self.get_3rd_path_value(['spec', 'selector', 'matchLabels']))
        self.value_dict['KRSpSR'] = self.get_2nd_path_value(['spec', 'replicas'])

    def get_perf_metrics(self):
        self.value_dict['KRSSR'] = self.get_2nd_path_value(['status', 'replicas'])
        self.value_dict['KRSSFLR'] = self.get_2nd_path_value(['status', 'fullyLabeledReplicas'])
        self.value_dict['KRSSRR'] = self.get_2nd_path_value(['status', 'readyReplicas'])
