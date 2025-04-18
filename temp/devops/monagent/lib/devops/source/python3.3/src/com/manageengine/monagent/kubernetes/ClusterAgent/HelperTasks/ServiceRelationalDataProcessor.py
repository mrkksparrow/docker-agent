from com.manageengine.monagent.kubernetes.ClusterAgent.HelperTasks.TaskExecutor import TaskExecutor
from com.manageengine.monagent.kubernetes import KubeUtil, KubeGlobal
from com.manageengine.monagent.kubernetes.Parser.JSONParser import Services

import traceback, json
from concurrent.futures import ThreadPoolExecutor


class ServiceRelationDataProcessor(TaskExecutor):
    def task_definition(self):
        final_dict = {
            KubeGlobal.DATA_TYPE_PARSED_FILE_MAP['service_rs']: {},
            KubeGlobal.DATA_TYPE_PARSED_FILE_MAP['service_pod_map']: {},
            KubeGlobal.DATA_TYPE_PARSED_FILE_MAP['service_endpoints']: {}
        }
        KubeUtil.get_api_data_by_limit(
            KubeGlobal.apiEndpoint + KubeGlobal.API_ENDPOINT_RES_NAME_MAP['Services'],
            self.hash_service_selectors,
            final_dict
        )
        return final_dict

    def hash_service_selectors(self, services, final_dict):
        with ThreadPoolExecutor(max_workers=4) as exe:
            for svc_data in services['items']:
                exe.submit(self.process_svc_data, svc_data, final_dict)

    def process_svc_data(self, svc, final_dict):
        try:
            name = svc['metadata']['name']
            ns = svc['metadata']['namespace']
            svc_name = name + '_' + ns
            if 'spec' in svc and 'selector' in svc['spec']:
                match_labels = []

                for key, value in svc['spec']['selector'].items():
                    match_labels.append("{}%3D{}".format(key, value))

                status, api_resp = KubeUtil.curl_api_with_token(KubeGlobal.apiEndpoint + "/api/v1/namespaces/{}/pods?labelSelector={}".format(ns, ",".join(match_labels)))
                if status == 200:
                    eps_data = {'ready_status': 'true', 'eps': {}}
                    ports = ','.join([str(port['port']) for port in svc['spec']['ports']])
                    for pod_value in api_resp.get("items", []):
                        pod_name = pod_value['metadata']['name'] + "_" + ns

                        for cnd in pod_value['status'].get('conditions', []):
                            if cnd['type'] == 'Ready' and cnd['status'] != 'True':
                                eps_data['ready_status'] = 'false'
                                break

                        if eps_data['ready_status'] != 'false':
                            # Relation metrics for Resource Dependency
                            if pod_name not in final_dict[KubeGlobal.DATA_TYPE_PARSED_FILE_MAP['service_rs']]:
                                final_dict[KubeGlobal.DATA_TYPE_PARSED_FILE_MAP['service_rs']][pod_name] = []
                            final_dict[KubeGlobal.DATA_TYPE_PARSED_FILE_MAP['service_rs']][pod_name].append(name)

                            # Relation Metrics for ClusterMetricsAggregator
                            final_dict[KubeGlobal.DATA_TYPE_PARSED_FILE_MAP['service_pod_map']][pod_name] = svc_name

                            # Associated Endpoints related metrics (Pods)
                            eps_data['eps'][pod_value['status']['podIP']] = ports

                    eps_data['eps'] = json.dumps(eps_data['eps'])
                    final_dict[KubeGlobal.DATA_TYPE_PARSED_FILE_MAP['service_endpoints']][svc_name] = eps_data
        except Exception:
            traceback.print_exc()
