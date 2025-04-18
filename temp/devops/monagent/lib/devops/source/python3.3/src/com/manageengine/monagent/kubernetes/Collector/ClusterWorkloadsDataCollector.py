from com.manageengine.monagent.kubernetes import KubeUtil, KubeGlobal
from com.manageengine.monagent.kubernetes.Collector.DataCollectorInterface import DataCollector
from com.manageengine.monagent.kubernetes.Parser.ParserFactory import get_json_parser
from com.manageengine.monagent.kubernetes.ClusterAgent.ClusterAgentUtil import ReadOrWriteWithFileLock

import json


class WorkloadsDataCollector(DataCollector):
    
    def get_from_cluster_agent(self):
        super().get_from_cluster_agent()
        if 'kubernetes' in self.final_json:
            self.final_json['kubernetes']['ca_stats'] = json.dumps(KubeGlobal.CLUSTER_AGENT_STATS)

    def get_data_for_cluster_agent(self, req_params=None):
        self.collect_data()
        with ReadOrWriteWithFileLock(KubeGlobal.HELPER_TASK_STATS_FILE, 'r') as read_obj:
            self.final_json['kubernetes']['helper_stats'] = json.dumps(read_obj.read_json())
        return self.final_json

    def collect_data(self):
        self.final_json = {
            "kubernetes": KubeUtil.fetch_cluster_metadata(),
            "DaemonSets": get_json_parser("DaemonSets")().get_data(),
            "Namespaces": KubeUtil.MergeDataDictionaries(get_json_parser("Namespaces")().get_data(), get_json_parser("ResourceQuota")().get_data()),
            "Deployments": get_json_parser("Deployments")().get_data(),
            "Jobs": get_json_parser("Jobs")().get_data(),
            "Services": get_json_parser("Services")().get_data(),
            "StatefulSets": get_json_parser("StatefulSets")().get_data(),
            "Ingresses": get_json_parser("Ingresses")().get_data(),
            "PV": get_json_parser("PV")().get_data(),
            "PersistentVolumeClaim": get_json_parser("PersistentVolumeClaim")().get_data(),
            "ReplicaSets": get_json_parser("ReplicaSets")().get_data(),
            "HorizontalPodAutoscalers": get_json_parser("HorizontalPodAutoscalers")().get_data()
        }
        self.update_aggregated_metrics()

    def update_aggregated_metrics(self):
        for res_type, res_value in self.final_json.items():
            self.final_json['kubernetes'].update(res_value.pop('aggregated_metrics', {}))
