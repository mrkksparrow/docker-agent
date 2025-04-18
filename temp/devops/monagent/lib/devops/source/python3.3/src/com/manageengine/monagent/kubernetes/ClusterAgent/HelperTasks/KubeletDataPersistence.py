from com.manageengine.monagent.kubernetes.ClusterAgent.HelperTasks.TaskExecutor import TaskExecutor
from com.manageengine.monagent.kubernetes import KubeGlobal, KubeUtil
from concurrent.futures import ThreadPoolExecutor


class KubeletDataPersistence(TaskExecutor):
    def task_definition(self):
        status, nodes = KubeUtil.curl_api_with_token(KubeGlobal.apiEndpoint + '/api/v1/nodes')
        final_dict = {
            KubeGlobal.DATA_TYPE_PARSED_FILE_MAP['all_kubelet']: {}
        }
        if status == 200:
            with ThreadPoolExecutor(max_workers=4) as exe:
                for node in nodes['items']:
                    exe.submit(get_and_filter_kubelet_data, node, final_dict)
        return final_dict


def get_and_filter_kubelet_data(node_data, final_dict):
    status, data = KubeUtil.curl_api_with_token(KubeGlobal.apiEndpoint + "/api/v1/nodes/{}/proxy/stats/summary".format(node_data['metadata']['name']))
    if status != 200:
        data = KubeUtil.get_kubelet_api_data('/stats/summary', node_name=node_data['metadata']['name'])

    data['node'].pop("runtime", None)
    data['node'].pop("rlimit", None)
    data['node'].pop("swap", None)

    for pod in data['pods']:
        pod.pop('containers', None)
        pod.pop('swap', None)

    final_dict[KubeGlobal.DATA_TYPE_PARSED_FILE_MAP['all_kubelet']][node_data['metadata']['name']] = data
