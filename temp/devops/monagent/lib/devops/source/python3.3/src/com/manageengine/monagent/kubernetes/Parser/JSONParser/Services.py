from com.manageengine.monagent.kubernetes.Parser.JSONParserInterface import JSONParser
from com.manageengine.monagent.kubernetes import KubeGlobal, KubeUtil
from com.manageengine.monagent.kubernetes.ClusterAgent import ClusterAgentUtil
import json


class Services(JSONParser):
    def __init__(self):
        super().__init__('Services')
        self.saved_endpoints_data = ClusterAgentUtil.get_parsed_data_for_ca('service_endpoints')

    def get_metadata(self):
        super().get_metadata()
        self.value_dict['Lb'] = json.dumps(self.get_2nd_path_value(['metadata', 'labels'], ""))
        self.value_dict['An'] = json.dumps(self.get_2nd_path_value(['metadata', 'annotations'], ""))
        self.value_dict['ML'] = json.dumps(self.get_3rd_path_value(['spec', 'selector', 'matchLabels'], ""))
        self.value_dict['CIP'] = self.get_2nd_path_value(['spec', 'clusterIP'])
        self.value_dict['Ty'] = self.get_2nd_path_value(['spec', 'type'])
        self.value_dict['SA'] = self.get_2nd_path_value(['spec', 'sessionAffinity'])
        self.value_dict['ETP'] = self.get_2nd_path_value(['spec', 'externalTrafficPolicy'])
        self.value_dict['Sel'] = json.dumps(self.get_2nd_path_value(['spec', 'selector'], ""))

    def get_perf_metrics(self):
        # load balancer IPs
        self.value_dict['LIP'] = ','.join([
            l_ip['ip'] for l_ip in self.get_3rd_path_value(['status', 'loadBalancer', 'ingress'], [])
        ])
        # ports
        self.value_dict['Po'] = json.dumps({
            port['targetPort']: port['protocol'] for port in self.get_2nd_path_value(['spec', 'ports'], [])
        })
        self.parse_endpoints(self.raw_data['metadata']['name'] + '_' + self.raw_data['metadata']['namespace'])

    def get_aggregated_metrics(self):
        # aggregated metrics
        self.aggregate_cluster_metrics(self.get_2nd_path_value(['spec', 'type']), 1)

    def parse_endpoints(self, svc_name):
        if self.saved_endpoints_data and svc_name in self.saved_endpoints_data:
            self.value_dict.update(self.saved_endpoints_data[svc_name])
            return

        match_labels = ["{}%3D{}".format(key, value) for key, value in self.get_2nd_path_value(['spec', 'selector'], {}).items()]
        status, api_resp = KubeUtil.curl_api_with_token(KubeGlobal.apiEndpoint + "/api/v1/namespaces/{}/pods?labelSelector={}".format(
            self.value_dict['NS'], ",".join(match_labels)
        ))

        if status == 200:
            eps_data = {'ready_status': 'true', 'eps': {}}
            ports = ','.join([str(port) for port in self.get_2nd_path_value(['spec', 'ports'], {})])

            for pod_value in api_resp["items"]:
                get_endpoint_metrics(pod_value, eps_data, ports)

            eps_data['eps'] = json.dumps(eps_data['eps'])
            self.value_dict.update(eps_data)


def get_endpoint_metrics(pod_value, eps_dict, ports):
    try:
        if eps_dict['ready_status'] != 'false':
            for cnd in pod_value['status']['conditions']:
                if cnd['type'] == 'Ready' and cnd['status'] != 'True':
                    eps_dict['ready_status'] = 'false'
                    return
        eps_dict['eps'][pod_value['status']['podIP']] = ports
    except Exception:
        return
