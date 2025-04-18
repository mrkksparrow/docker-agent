import json
from com.manageengine.monagent.kubernetes.Parser.JSONParserInterface import JSONParser


class PersistentVolume(JSONParser):
    def __init__(self):
        super().__init__('PV')
        self.is_namespaces = False

    def get_metadata(self):
        super().get_metadata()
        self.value_dict['An'] = json.dumps(self.get_2nd_path_value(['metadata', 'annotations'], {}))
        self.value_dict['Fn'] = json.dumps(self.get_2nd_path_value(['metadata', 'finalizers'], []))
        self.value_dict['PVRP'] = self.get_2nd_path_value(['spec', 'persistentVolumeReclaimPolicy'])
        self.value_dict['SC'] = self.get_2nd_path_value(['spec', 'storageClassName'])
        self.value_dict['VM'] = self.get_2nd_path_value(['spec', 'volumeMode'])
        self.value_dict['SCa'] = self.get_3rd_path_value(['spec', 'capacity', 'storage'])
        self.value_dict['AM'] = json.dumps(self.get_2nd_path_value(['spec', 'accessModes']))
        self.value_dict['CRKi'] = self.get_3rd_path_value(['spec', 'claimRef', 'kind'])
        self.value_dict['CRNa'] = self.get_3rd_path_value(['spec', 'claimRef', 'namespace'])
        self.value_dict['CRN'] = self.get_3rd_path_value(['spec', 'claimRef', 'name'])
        self.value_dict['CRUID'] = self.get_3rd_path_value(['spec', 'claimRef', 'uid'])
        self.value_dict['requested'] = self.get_3rd_path_value(['spec', 'claimRef', 'storage'])
        self.value_dict['CRAM'] = self.get_3rd_path_value(['spec', 'claimRef', 'accessModes'])

    def get_perf_metrics(self):
        self.value_dict['Ph'] = self.get_2nd_path_value(['status', 'phase'])
