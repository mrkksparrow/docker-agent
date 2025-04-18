from com.manageengine.monagent.kubernetes.Parser.JSONParserInterface import JSONParser
from com.manageengine.monagent.kubernetes import KubeGlobal
import json


class DaemonSets(JSONParser):
    def __init__(self):
        super().__init__('DaemonSets')

    def get_metadata(self):
        super().get_metadata()
        self.value_dict['Ge'] = self.get_2nd_path_value(['metadata', 'generation'])
        self.value_dict['MLb'] = json.dumps(self.get_3rd_path_value(['spec', 'selector', 'matchLabels'], ""))
        self.value_dict['Lb'] = json.dumps(self.get_2nd_path_value(['metadata', 'labels'], ""))
        self.value_dict['An'] = json.dumps(self.get_2nd_path_value(['metadata', 'annotations'], ""))
        self.value_dict['TN'] = self.get_4th_path_value(['spec', 'template', 'metadata', 'name'])
        self.value_dict['Str'] = self.get_3rd_path_value(['spec', 'updateStrategy', 'type'])
        self.value_dict['TLb'] = json.dumps(self.get_4th_path_value(['spec', 'template', 'metadata', 'labels'], ""))
        self.value_dict['TRP'] = self.get_4th_path_value(['spec', 'template', 'spec', 'restartPolicy'])
        self.value_dict['TTGPS'] = self.get_4th_path_value(['spec', 'template', 'spec', 'terminationGracePeriodSeconds'])
        self.value_dict['TDP'] = self.get_4th_path_value(['spec', 'template', 'spec', 'dnsPolicy'])
        self.value_dict['TSN'] = self.get_4th_path_value(['spec', 'template', 'spec', 'schedulerName'])

    def get_perf_metrics(self):
        # state metrics
        self.value_dict['KDSNS'] = self.get_2nd_path_value(['status', 'updatedNumberScheduled'], 0)
        self.value_dict['KDSCNS'] = self.get_2nd_path_value(['status', 'currentNumberScheduled'], 0)
        self.value_dict['KDSNM'] = self.get_2nd_path_value(['status', 'numberMisscheduled'], 0)
        self.value_dict['KDSDNS'] = self.get_2nd_path_value(['status', 'desiredNumberScheduled'], 0)
        self.value_dict['KDSCNR'] = self.get_2nd_path_value(['status', 'numberReady'], 0)
        self.value_dict['KDSNA'] = self.get_2nd_path_value(['status', 'numberAvailable'], 0)
        self.value_dict['KDSUA'] = self.get_2nd_path_value(['status', 'numberUnavailable'], 0)
        self.value_dict['KDSNR'] = self.value_dict['KDSDNS'] - self.value_dict['KDSCNR']    # Not ready replicas
        self.value_dict['KDSNUP'] = self.value_dict['KDSDNS'] - self.value_dict['KDSNS']    # Number of not updated replicas
        self.value_dict['KDSNOTS'] = self.value_dict['KDSDNS'] - self.value_dict['KDSCNS']  # Not scheduled case

    def get_aggregated_metrics(self):
        # aggregated metrics
        self.aggregate_cluster_metrics('KDSS', self.value_dict['KDSNS'])
        self.aggregate_cluster_metrics('KDSM', self.value_dict['KDSCNS'])
        self.aggregate_cluster_metrics('KDSD', self.value_dict['KDSNM'])
        self.aggregate_cluster_metrics('KDSR', self.value_dict['KDSDNS'])
        self.aggregate_cluster_metrics('KDSA', self.value_dict['KDSCNR'])
        self.aggregate_cluster_metrics('KDSNR', self.value_dict['KDSNA'])
