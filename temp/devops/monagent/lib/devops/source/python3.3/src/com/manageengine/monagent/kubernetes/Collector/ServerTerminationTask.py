from com.manageengine.monagent.kubernetes.Collector.DataCollectorInterface import DataCollector
from com.manageengine.monagent.kubernetes import KubeUtil, KubeGlobal
from com.manageengine.monagent.kubernetes.Logging import KubeLogger
import json
import time


class ServerTerminationTask(DataCollector):
    def collect_data(self):
        status, response = KubeUtil.curl_api_with_token(KubeGlobal.apiEndpoint + KubeGlobal.s247ConfigMapPath)
        if status == 200:
            self.final_json = {
                'Server': {}
            }
            self.handle_server_termination(response['data'])
            if self.final_json:
                self.final_json['perf'] = 'false'
                KubeLogger.console_logger.info('server termination data {}'.format(self.final_json))

    def handle_server_termination(self, registered_server_list):
        status, response = KubeUtil.curl_api_with_token(KubeGlobal.apiEndpoint + KubeGlobal.API_ENDPOINT_RES_NAME_MAP['Nodes'])
        if status == 200:
            nodes_hash_list = {node['metadata']['name']: 1 for node in response['items']}
            for server_name, server_info in registered_server_list.items():
                if server_name not in nodes_hash_list and server_name not in KubeGlobal.S247_CONFIGMAP_SYSTEM_KEYS:
                    server_data = json.loads(server_info)
                    self.final_json['Server'][server_name] = {
                        'id': server_data['id'],
                        'Na': server_name,
                        'UID': server_data['UID'],
                        'deleted': 'true'
                    }
                    if time.time() - int(server_data.get('time', 0)) > 7200:
                        KubeUtil.update_s247_configmap({
                            'data': {
                                server_name: None
                            }
                        })
                        KubeLogger.log(KubeLogger.KUBERNETES, '******** Removing server - {} from configmap *********'.format(server_name))
