import time
import traceback
import copy

from com.manageengine.monagent.kubernetes.Collector.DataCollectorInterface import DataCollector
from com.manageengine.monagent.kubernetes.Parser import ParserFactory
from com.manageengine.monagent.kubernetes import KubeGlobal, KubeUtil

LAST_CONFIG_ID = {}
SUCCEEDED_RESOURCES = {}
ONDEMAND_RETRY = False


class YAMLFetcher(DataCollector):
    def get_cluster_agent_request_params(self):
        global ONDEMAND_RETRY
        params_dict = {
            'kube_ids': KubeGlobal.kubeIds,
            'succeeded_resources': SUCCEEDED_RESOURCES,
            'retry': ONDEMAND_RETRY
        }
        ONDEMAND_RETRY = False
        return params_dict

    def get_data_for_cluster_agent(self, req_params=None):
        global SUCCEEDED_RESOURCES, ONDEMAND_RETRY
        KubeGlobal.kubeIds = req_params['kube_ids']
        SUCCEEDED_RESOURCES = req_params['succeeded_resources']
        ONDEMAND_RETRY = req_params['retry']
        return super().get_data_for_cluster_agent()

    def get_from_cluster_agent(self):
        global SUCCEEDED_RESOURCES
        if super().get_from_cluster_agent():
            for res_type, resources in self.final_json.items():
                if isinstance(resources, dict):
                    for res_name, res_config in resources.items():
                        SUCCEEDED_RESOURCES.pop(res_config['id'], None)

    def collect_data(self):
        global LAST_CONFIG_ID, ONDEMAND_RETRY, SUCCEEDED_RESOURCES
        try:
            if SUCCEEDED_RESOURCES and (KubeUtil.is_eligible_to_execute('yamlfetcher_retry', time.time()) or ONDEMAND_RETRY):
                for res_type, resources in KubeGlobal.kubeIds.items():
                    if res_type in KubeGlobal.YAML_SUPPORTED_TYPES:
                        for res_name, res_config in resources.items():
                            if res_config['id'] not in SUCCEEDED_RESOURCES:
                                KubeGlobal.RESOURCE_VERSIONS[res_type].pop(res_name, None)

            for res_type in KubeGlobal.YAML_SUPPORTED_TYPES:
                self.final_json[res_type] = ParserFactory.get_json_parser(res_type)().get_data(yaml=True)
        except Exception:
            traceback.print_exc()
        LAST_CONFIG_ID = copy.deepcopy(KubeGlobal.kubeIds)
        ONDEMAND_RETRY = False
