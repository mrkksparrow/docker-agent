from com.manageengine.monagent.kubernetes.Parser.JSONParserInterface import JSONParser
import json


class StatefulSets(JSONParser):
    def __init__(self):
        super().__init__("StatefulSets")

    def get_metadata(self):
        super().get_metadata()
        self.value_dict['Ge'] = self.get_2nd_path_value(['metadata', 'generation'])
        self.value_dict['An'] = json.dumps(self.get_2nd_path_value(['metadata', 'annotations']))
        self.value_dict['SN'] = self.get_2nd_path_value(['spec', 'serviceName'])
        self.value_dict['PMP'] = self.get_2nd_path_value(['spec', 'podManagementPolicy'])
        self.value_dict['RHL'] = self.get_2nd_path_value(['spec', 'revisionHistoryLimit'])
        self.value_dict['US'] = self.get_3rd_path_value(['spec', 'updateStrategy', 'type'])
        self.value_dict['MLb'] = self.get_3rd_path_value(['spec', 'selector', 'matchLabels'])
        self.value_dict['TLb'] = self.get_4th_path_value(['spec', 'template', 'metadata', 'labels'])

    def get_perf_metrics(self):
        self.value_dict['KSSR'] = self.get_2nd_path_value(['spec', 'replicas'], 0)  # desired replicas
        self.value_dict['OG'] = self.get_2nd_path_value(['status', 'observedGeneration'], 0)
        self.value_dict['KSSSR'] = self.get_2nd_path_value(['status', 'replicas'], 0)   # number of pods created by this statefulset
        self.value_dict['Re'] = self.get_2nd_path_value(['status', 'replicas'], 0)   # number of pods created by this statefulset
        self.value_dict['KSSSRR'] = self.get_2nd_path_value(['status', 'readyReplicas'], 0)
        self.value_dict['KSSSRC'] = self.get_2nd_path_value(['status', 'currentReplicas'], 0)
        self.value_dict['KSSSRU'] = self.get_2nd_path_value(['status', 'updatedReplicas'], 0)
        self.value_dict['KSSSA'] = self.get_2nd_path_value(['status', 'availableReplicas'], 0)
        self.value_dict['CC'] = self.get_2nd_path_value(['status', 'collisionCount'], 0)
        self.value_dict['NR'] = self.value_dict['KSSR'] - self.value_dict['KSSSRR']  # not ready replica count based on desired count
        self.value_dict['UR'] = self.value_dict['KSSR'] - self.value_dict['KSSSA']  # UnavailableReplicas count based on desired count
        self.value_dict['KSSGMM'] = self.value_dict['OG'] != self.raw_data['metadata']['generation']

    def get_aggregated_metrics(self):
        # aggregated metrics
        self.aggregate_cluster_metrics('KSSD', self.value_dict['Re'])
        self.aggregate_cluster_metrics('KSSRR', self.value_dict['KSSSRR'])
        self.aggregate_cluster_metrics('KSSNR', self.value_dict['NR'])
        self.aggregate_cluster_metrics('KSSC', self.value_dict['KSSSRC'])
        self.aggregate_cluster_metrics('KSSCC', self.value_dict['CC'])
        self.aggregate_cluster_metrics('KSSU', self.value_dict['KSSSRU'])
