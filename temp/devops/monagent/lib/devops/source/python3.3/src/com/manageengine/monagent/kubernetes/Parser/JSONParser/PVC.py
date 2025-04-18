import json
from com.manageengine.monagent.kubernetes.Parser.JSONParserInterface import JSONParser


class PersistentVolumeClaim(JSONParser):
    def __init__(self):
        super().__init__('PersistentVolumeClaim')

    def get_metadata(self):
        super().get_metadata()
        self.value_dict['An'] = json.dumps(self.get_2nd_path_value(['metadata', 'annotations']))
        self.value_dict['Fn'] = json.dumps(self.get_2nd_path_value(['spec', 'finalizers']))
        self.value_dict['AM'] = json.dumps(self.get_2nd_path_value(['spec', 'accessModes']))
        self.value_dict['SR'] = self.get_4th_path_value(['spec', 'resources', 'requests', 'storage'])
        self.value_dict['VN'] = self.get_2nd_path_value(['spec', 'volumeName'])
        self.value_dict['SC'] = self.get_2nd_path_value(['spec', 'storageClassName'])
        self.value_dict['VM'] = self.get_2nd_path_value(['spec', 'volumeMode'])

    def get_perf_metrics(self):
        self.value_dict['Ph'] = self.get_2nd_path_value(['status', 'phase'])
