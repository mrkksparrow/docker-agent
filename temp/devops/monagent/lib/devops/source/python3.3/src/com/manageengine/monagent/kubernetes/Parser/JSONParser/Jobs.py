from com.manageengine.monagent.kubernetes.Parser.JSONParserInterface import JSONParser
from com.manageengine.monagent.kubernetes import KubeGlobal, KubeUtil
import json
from datetime import datetime


class Jobs(JSONParser):
    def __init__(self):
        super().__init__('Jobs')

    def get_metadata(self):
        super().get_metadata()
        self.value_dict['Lb'] = json.dumps(self.get_2nd_path_value(['metadata', 'labels'], ""))
        self.value_dict['An'] = json.dumps(self.get_2nd_path_value(['metadata', 'annotations'], ""))
        self.value_dict['ML'] = json.dumps(self.get_3rd_path_value(['spec', 'selector', 'matchLabels'], ""))
        self.value_dict['Pa'] = self.get_2nd_path_value(['spec', 'parallelism'])
        self.value_dict['Co'] = self.get_2nd_path_value(['spec', 'completions'])
        self.value_dict['Bol'] = self.get_2nd_path_value(['spec', 'backoffLimit'])
        self.value_dict['ttl'] = self.get_2nd_path_value(['spec', 'ttlSecondsAfterFinished'])

    def get_perf_metrics(self):
        self.value_dict['STM'] = self.get_2nd_path_value(['status', 'startTime'])
        self.value_dict['CMPT'] = self.get_2nd_path_value(['status', 'completionTime'])
        self.value_dict['succeeded_pods'] = self.get_2nd_path_value(['status', 'succeeded'], 0)
        self.value_dict['failed_pods'] = self.get_2nd_path_value(['status', 'failed'], 0)
        self.value_dict['active_pods'] = self.get_2nd_path_value(['status', 'active'], 0)
        self.value_dict['ready_pods'] = self.get_2nd_path_value(['status', 'ready'], 0)
        self.value_dict['job_status'] = 'Active'

        # finding job running duration
        ct = datetime.now()
        if self.value_dict["CMPT"]:
            ct = self.value_dict["CMPT"].split("T")
            ct = ct[0] + " " + ct[1].split('Z')[0] + ".000000"
        self.value_dict["duration"] = KubeUtil.getAge(self.value_dict['STM'], ct)
        self.value_dict['duration_sec'] = KubeUtil.getAge(self.value_dict['STM'], ct, True)

        # job status
        for condition in self.get_2nd_path_value(['status', 'conditions'], []):
            if condition['status'] == "True":
                self.value_dict['job_status'] = condition['type']
                self.value_dict['job_status_reason'] = condition.get('message', '')

    def get_aggregated_metrics(self):
        self.aggregate_cluster_metrics(self.value_dict['job_status'] + '_jobs', 1)
