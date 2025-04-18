import traceback

from com.manageengine.monagent.kubernetes.ClusterAgent.HelperTasks.TaskExecutor import TaskExecutor
from com.manageengine.monagent.kubernetes.Parser.PrometheusParser.NPCStateMetricsParser import NPCStateMetrics
from com.manageengine.monagent.kubernetes.Parser.PrometheusParser.ResourceDependencyMetricsParser import ResourceDependency
from com.manageengine.monagent.kubernetes import KubeGlobal, KubeUtil
from prometheus_client.parser import text_string_to_metric_families


class KSMProcessor(TaskExecutor):
    def task_definition(self):
        status, ksm_response = KubeUtil.curl_api_without_token(KubeGlobal.kubeStateMetricsUrl + '/metrics')
        if status == 200:
            return KubeUtil.MergeDataDictionaries(
                parse_npc(text_string_to_metric_families(ksm_response)),
                parse_resource_dependency_data(text_string_to_metric_families(ksm_response))
            )
        return {}


def parse_npc(families):
    npc_obj = NPCStateMetrics()
    npc_obj.parse_families(families)
    npc_ksm = npc_obj.final_dict

    return {
        KubeGlobal.DATA_TYPE_PARSED_FILE_MAP['npc_ksm']: npc_ksm,
    }


def parse_resource_dependency_data(families):
    try:
        rd_obj = ResourceDependency()
        rd_obj.parse_families(families)
        rd_data = rd_obj.final_dict
        return {
            KubeGlobal.DATA_TYPE_PARSED_FILE_MAP['rs_deploy_map']: rd_data['ReplicaSet'],
            KubeGlobal.DATA_TYPE_PARSED_FILE_MAP['resource_dependency_ksm']: rd_data
        }
    except Exception:
        traceback.print_exc()
    return {}
