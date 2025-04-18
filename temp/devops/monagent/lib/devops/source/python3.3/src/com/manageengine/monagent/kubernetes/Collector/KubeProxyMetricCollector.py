from com.manageengine.monagent.kubernetes.Collector.DataCollectorInterface import DataCollector
from com.manageengine.monagent.kubernetes import KubeUtil, KubeGlobal
from com.manageengine.monagent.kubernetes.Parser.PrometheusParser.KubeProxyParser import KubeProxy


class KubeProxyMetricCollector(DataCollector):
    def collect_data(self):
        status, response = KubeUtil.curl_api_without_token(KubeUtil.construct_node_ip_url('http://{}:10249/metrics', KubeGlobal.IP_ADDRESS))
        if status == 200:
            kube_proxy_json = KubeProxy().get_data()
            self.final_json = {
                'KubeProxy': {}
            }
            self.final_json['KubeProxy'][KubeGlobal.KUBELET_NODE_NAME] = kube_proxy_json.get('KubeProxy', {})
            self.final_json['KubeProxy'][KubeGlobal.KUBELET_NODE_NAME]['DCErrors'] = kube_proxy_json.get('DCErrors', {})
            self.decide_health_check_status()
            self.final_json['KubeProxy'][KubeGlobal.KUBELET_NODE_NAME].update({
                'host': KubeGlobal.KUBELET_NODE_NAME,
                'Hostname': KubeGlobal.KUBELET_NODE_NAME,
                'cp_type': 'KUBERNETES_KUBE_PROXY'
            })
            if 'KubeProxy' not in KubeGlobal.kubeIds or KubeGlobal.KUBELET_NODE_NAME not in KubeGlobal.kubeIds['KubeProxy']:
                self.final_json['KubeProxy'][KubeGlobal.KUBELET_NODE_NAME]['id'] = ''
                self.final_json['perf'] = 'false'
            else:
                self.final_json['KubeProxy'][KubeGlobal.KUBELET_NODE_NAME]['id'] = KubeGlobal.kubeIds['KubeProxy'][KubeGlobal.KUBELET_NODE_NAME].get('id', '')
                self.final_json['perf'] = 'true'

    def decide_health_check_status(self):
        kube_proxy_url = KubeUtil.construct_node_ip_url('http://{}:10256', KubeGlobal.IP_ADDRESS)
        status, response = KubeUtil.curl_api_without_token(kube_proxy_url + '/healthz')
        if status == 200:
            self.final_json['KubeProxy'][KubeGlobal.KUBELET_NODE_NAME]['healthz_check_status'] = 1
        else:
            self.final_json['KubeProxy'][KubeGlobal.KUBELET_NODE_NAME]['healthz_check_status'] = 0
            self.final_json['KubeProxy'][KubeGlobal.KUBELET_NODE_NAME]['DCErrors']['healthz_check_status'] = {status: response}

        status, response = KubeUtil.curl_api_without_token(kube_proxy_url + '/livez')
        if status == 200:
            self.final_json['KubeProxy'][KubeGlobal.KUBELET_NODE_NAME]['livez_check_status'] = 1
        else:
            self.final_json['KubeProxy'][KubeGlobal.KUBELET_NODE_NAME]['livez_check_status'] = 0
            self.final_json['KubeProxy'][KubeGlobal.KUBELET_NODE_NAME]['DCErrors']['livez_check_status'] = {status: response}
