from com.manageengine.monagent.kubernetes.Parser.JSONParserInterface import JSONParser
import json


class Deployments(JSONParser):
    def __init__(self):
        super().__init__('Deployments')

    def get_metadata(self):
        super().get_metadata()
        self.value_dict['Lb'] = json.dumps(self.get_2nd_path_value(['metadata', 'labels']))
        self.value_dict['An'] = json.dumps(self.get_2nd_path_value(['metadata', 'annotations']))
        self.value_dict['Str'] = self.get_3rd_path_value(['spec', 'strategy', 'type'])
        self.value_dict['MLb'] = json.dumps(self.get_3rd_path_value(['spec', 'selector', 'matchLabels']))
        self.value_dict['TSRP'] = self.get_4th_path_value(['spec', 'template', 'spec', 'restartPolicy'])
        self.value_dict['TTGPS'] = self.get_4th_path_value(['spec', 'template', 'spec', 'terminationGracePeriodSeconds'])
        self.value_dict['TDP'] = self.get_4th_path_value(['spec', 'template', 'spec', 'dnsPolicy'])
        self.value_dict['TSN'] = self.get_4th_path_value(['spec', 'template', 'spec', 'schedulerName'])
        self.value_dict['KDSpPa'] = self.get_2nd_path_value(['spec', 'paused'], 0)
        self.value_dict['PDLS'] = self.get_2nd_path_value(['spec', 'progressDeadlineSeconds'])
        self.value_dict['KDSpSRMUA'] = self.get_4th_path_value(['spec', 'strategy', 'rollingUpdate', 'maxUnavailable'], 0)

    def get_perf_metrics(self):
        # state metrics
        self.value_dict['KDSpR'] = self.get_2nd_path_value(['spec', 'replicas'], 0)  # total replicas specified in YAML
        self.value_dict['KDSR'] = self.get_2nd_path_value(['status', 'replicas'], 0)  # no. of replicas scheduled
        self.value_dict['KDSRUP'] = self.get_2nd_path_value(['status', 'updatedReplicas'], 0)
        self.value_dict['RRep'] = self.get_2nd_path_value(['status', 'readyReplicas'], 0)  # no. of pods in ready state
        self.value_dict['KDSRA'] = self.get_2nd_path_value(['status', 'availableReplicas'], 0)
        self.value_dict['ARep'] = self.get_2nd_path_value(['status', 'availableReplicas'], 0)
        self.value_dict['KDSRUA'] = self.get_2nd_path_value(['status', 'unavailableReplicas'], 0)
        self.value_dict['KDSNRR'] = self.value_dict['KDSpR'] - self.value_dict['RRep']  # Not ready replicas based on desired count
        self.value_dict['KDSRUAD'] = self.value_dict['KDSpR'] - self.value_dict['KDSRA']  # Unavailable replicas based on desired count
        self.value_dict['OGV'] = self.get_2nd_path_value(['status', 'observedGeneration'])
        self.value_dict['RHL'] = self.get_2nd_path_value(['status', 'revisionHistoryLimit'])
        self.value_dict['KDSGMM'] = self.raw_data['metadata']['generation'] != self.value_dict['OGV']

    def get_aggregated_metrics(self):
        # aggregated metrics
        self.aggregate_cluster_metrics('KDDR', self.get_2nd_path_value(['spec', 'replicas'], 0))  # total replicas
        self.aggregate_cluster_metrics('KDRA', self.value_dict['KDSRA'])  # available replicas
        self.aggregate_cluster_metrics('KDRUA', self.value_dict['KDSRUA'])  # unavailable replicas
        self.aggregate_cluster_metrics('KDRUP', self.value_dict['KDSRUP'])  # updated replicas
        self.aggregate_cluster_metrics('KDPR', self.get_2nd_path_value(['spec', 'paused'], 0))  # paused replicas
        self.aggregate_cluster_metrics('KDR', self.value_dict['RRep'])
        self.aggregate_cluster_metrics('KDO', self.value_dict['KDSpR'] - self.value_dict['KDSRUP'])  # outdated replicas
        self.aggregate_cluster_metrics('KDDNA', self.value_dict['KDSRUA'])
        # self.aggregate_cluster_metrics('KDMUR', self.get_4th_path_value(['spec', 'strategy', 'rollingUpdate', 'maxUnavailable'], 0))
