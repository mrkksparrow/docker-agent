import traceback
import time

from com.manageengine.monagent.kubernetes.Collector.ClusterMetricsAggregator import ClusterMetricsAggregator
from com.manageengine.monagent.kubernetes.Parser.PrometheusParser.NPCStateMetricsParser import NPCStateMetrics
from com.manageengine.monagent.kubernetes import KubeUtil, KubeGlobal
from com.manageengine.monagent.kubernetes.ClusterAgent import ClusterAgentUtil


class MetricsServerAggregator(ClusterMetricsAggregator):
    def collect_data(self):
        try:
            self.ksm_data = NPCStateMetrics().get_data()

            KubeUtil.get_api_data_by_limit(
                KubeGlobal.apiEndpoint + KubeGlobal.API_ENDPOINT_RES_NAME_MAP['Services'], self.hash_service_selectors, self.service_selectors
            )

            node_perf_metrics = KubeUtil.curl_api_with_token(KubeGlobal.apiEndpoint + '/apis/metrics.k8s.io/v1beta1/nodes')[1]
            pod_perf_metrics = KubeUtil.curl_api_with_token(KubeGlobal.apiEndpoint + '/apis/metrics.k8s.io/v1beta1/pods')[1]

            for node_data in node_perf_metrics['items']:
                self.aggregate_cluster_metrics(
                    {
                        'cpu': {'usageNanoCores': KubeUtil.convert_cpu_values_to_standard_units(node_data['usage']['cpu']) * 1000000000},
                        'memory': {'workingSetBytes': KubeUtil.convert_values_to_standard_units(node_data['usage']['memory'])}
                    },
                    self.ksm_data['Nodes'][node_data['metadata']['name']]
                )

            self.aggregate_workload_metrics(pod_perf_metrics['items'], self.ksm_data['Pods'])
            self.aggregate_deployment_perf_values()
            self.calculate_cluster_capacity()
        except Exception:
            traceback.print_exc()

    def get_data_for_cluster_agent(self, req_params=None):
        self.ksm_data = ClusterAgentUtil.get_parsed_data_for_ca("npc_ksm")
        self.service_selectors = ClusterAgentUtil.get_parsed_data_for_ca("service_pod_map")
        self.rs_deploy_map = ClusterAgentUtil.get_parsed_data_for_ca("rs_deploy_map")

        node_perf_metrics = KubeUtil.curl_api_with_token(KubeGlobal.apiEndpoint + '/apis/metrics.k8s.io/v1beta1/nodes')[1]
        pod_perf_metrics = KubeUtil.curl_api_with_token(KubeGlobal.apiEndpoint + '/apis/metrics.k8s.io/v1beta1/pods')[1]

        for node_data in node_perf_metrics['items']:
            self.aggregate_cluster_metrics(
                {
                    'cpu': {'usageNanoCores': KubeUtil.convert_cpu_values_to_standard_units(node_data['usage']['cpu']) * 1000000000},
                    'memory': {'workingSetBytes': KubeUtil.convert_values_to_standard_units(node_data['usage']['memory'])}
                },
                self.ksm_data['Nodes'][node_data['metadata']['name']]
            )

        self.aggregate_workload_metrics(pod_perf_metrics['items'], self.ksm_data['Pods'])
        self.aggregate_deployment_perf_values()
        self.calculate_cluster_capacity()
        return self.final_json

    def construct_pod_perf_value(self, pod, pod_state_data, pod_name):
        perf_value_dict = {
            'cpu_used': 0,
            'mem_used': 0,
            'mem_req': 0,
            'cpu_req': 0,
            'cpu_limit': 0,
            'mem_limit': 0,
            'rx': 0,
            'tx': 0,
            'rss_mem_used': 0,
            'rc': 0
        }
        for containers in pod['containers']:
            perf_value_dict['cpu_used'] += KubeUtil.convert_cpu_values_to_standard_units(containers['usage']['cpu'])
            perf_value_dict['mem_used'] += int(KubeUtil.convert_values_to_standard_units(containers['usage']['memory'])) / 1048576

        perf_value_dict['mem_req'] = float(pod_state_data["PRMB"]) if "PRMB" in pod_state_data else 0
        perf_value_dict['cpu_req'] = float(pod_state_data["PRRCC"]) if "PRRCC" in pod_state_data else 0
        perf_value_dict['mem_limit'] = float(pod_state_data["PRLMB"]) if "PRLMB" in pod_state_data else 0
        perf_value_dict['cpu_limit'] = float(pod_state_data["PRLCC"]) if "PRLCC" in pod_state_data else 0
        perf_value_dict['rc'] = float(pod_state_data["RC"]) if "RC" in pod_state_data else 0
        return perf_value_dict
