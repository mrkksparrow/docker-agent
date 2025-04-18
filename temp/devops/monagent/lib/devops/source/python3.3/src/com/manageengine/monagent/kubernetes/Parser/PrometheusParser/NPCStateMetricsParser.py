from com.manageengine.monagent.kubernetes.Parser.StateMetricsParser import PrometheusParser
from com.manageengine.monagent.kubernetes import KubeGlobal

families = {
    'kube_node_spec_unschedulable': ['Nodes', ['node'], 'KNSU', None],
    'kube_node_status_capacity': ['Nodes', ['node'], None, {'node': 'No'}],
    'kube_node_status_allocatable': ['Nodes', ['node'], None, None],
    'kube_pod_status_phase': ['Pods', ['pod', 'namespace'], None, {'namespace': 'NS', 'pod': 'Na'}],
    'kube_pod_container_resource_requests': ['Pods', ['pod', 'namespace'], None, None],
    'kube_pod_container_resource_limits': ['Pods', ['pod', 'namespace'], None, None],
    'kube_pod_owner': ['Pods', ['pod', 'namespace'], None, {'owner_kind': 'owner_kind', 'owner_name': 'owner_name'}],
    'kube_pod_info': ['Pods', ['pod', 'namespace'], None, {'node': 'No'}],
    'kube_pod_container_status_waiting': ['Pods', ['pod', 'namespace'], None, None],
    'kube_pod_container_status_running': ['Pods', ['pod', 'namespace'], None, None],
    'kube_pod_container_status_terminated': ['Pods', ['pod', 'namespace'], None, None],
    'kube_pod_status_ready': ['Pods', ['pod', 'namespace'], "KPSR", None],
    'kube_pod_container_status_restarts': ['Pods', ['pod', 'namespace'], None, None],
    'kube_pod_container_status_waiting_reason': ['kubernetes', None, None, None],
    'kube_pod_container_status_terminated_reason': ['kubernetes', None, None, None],
    'kube_pod_container_status_ready': ['kubernetes', None, None, None]
}
custom_parsers_family_names = [
    'kube_node_status_capacity',
    'kube_node_status_allocatable',
    'kube_pod_status_phase',
    'kube_pod_container_resource_requests',
    'kube_pod_container_resource_limits',
    'kube_pod_container_status_waiting',
    'kube_pod_container_status_running',
    'kube_pod_container_status_terminated',
    'kube_pod_container_status_restarts',
    'kube_pod_container_status_waiting_reason',
    'kube_pod_container_status_terminated_reason'
]


class NPCStateMetrics(PrometheusParser):
    def __init__(self):
        super().__init__(KubeGlobal.kubeStateMetricsUrl + '/metrics')
        self.families = families
        self.custom_parsers_family_names = custom_parsers_family_names

    def kube_pod_container_status_terminated(self, sample):
        self.value_dict['Cont'] = self.value_dict.get('Cont', {})
        self.value_dict['Cont'][self.labels['container']] = self.value_dict['Cont'].get(self.labels['container'], {})
        self.value_dict['Cont'][self.labels['container']]['KPCST'] = sample.value

    def kube_pod_container_status_running(self, sample):
        self.value_dict['Cont'] = self.value_dict.get('Cont', {})
        self.value_dict['Cont'][self.labels['container']] = self.value_dict['Cont'].get(self.labels['container'], {})
        self.value_dict['Cont'][self.labels['container']]['KPCSR'] = sample.value

    def kube_pod_container_status_waiting(self, sample):
        self.value_dict['Cont'] = self.value_dict.get('Cont', {})
        self.value_dict['Cont'][self.labels['container']] = self.value_dict['Cont'].get(self.labels['container'], {})
        self.value_dict['Cont'][self.labels['container']]['KPCSW'] = sample.value

    def kube_pod_container_status_waiting_reason(self, sample):
        reason_key = 'CWR_' + self.labels['reason']
        self.value_dict[reason_key] = self.value_dict.get(reason_key, 0) + 1
        self.value_dict['KPCSW'] = self.value_dict.get('KPCSW', 0) + 1

    def kube_pod_container_status_terminated_reason(self, sample):
        reason_key = 'CTR_' + self.labels['reason']
        self.value_dict[reason_key] = self.value_dict.get(reason_key, 0) + 1
        self.value_dict['KPCST'] = self.value_dict.get('KPCST', 0) + 1

    def kube_pod_container_status_ready(self, sample):
        self.value_dict['KPCSR'] = self.value_dict.get('KPCSR', 0) + sample.value

    def kube_pod_container_resource_limits(self, sample):
        self.value_dict['Cont'] = self.value_dict.get('Cont', {})
        self.value_dict['Cont'][self.labels['container']] = self.value_dict['Cont'].get(self.labels['container'], {})
        metric_type = self.labels['resource']

        if metric_type == 'cpu':
            self.value_dict['PRLCC'] = self.value_dict.get('PRLCC', 0) + sample.value * 1000
            self.value_dict['Cont'][self.labels['container']]['KPCRLCC'] = self.value_dict['Cont'][self.labels['container']].get("KPCRLCC", 0) + sample.value * 1000
        elif metric_type == 'memory':
            self.value_dict['PRLMB'] = self.value_dict.get('PRLMB', 0) + sample.value / 1048576
            self.value_dict['Cont'][self.labels['container']]['KPCRLMB'] = self.value_dict['Cont'][self.labels['container']].get("KPCRLMB", 0) + sample.value / 1048576

    def kube_pod_container_resource_requests(self, sample):
        self.value_dict['Cont'] = self.value_dict.get('Cont', {})
        self.value_dict['Cont'][self.labels['container']] = self.value_dict['Cont'].get(self.labels['container'], {})
        metric_type = self.labels['resource']

        if metric_type == 'cpu':
            self.value_dict['PRRCC'] = self.value_dict.get('PRRCC', 0) + sample.value * 1000
            self.value_dict['Cont'][self.labels['container']]['KPCRRCC'] = self.value_dict['Cont'][self.labels['container']].get("KPCRRCC", 0) + sample.value * 1000
        elif metric_type == 'memory':
            self.value_dict['PRMB'] = self.value_dict.get('PRMB', 0) + sample.value / 1048576
            self.value_dict['Cont'][self.labels['container']]['KPCRRMB'] = self.value_dict['Cont'][self.labels['container']].get("KPCRRMB", 0) + sample.value / 1048576

    def kube_pod_status_phase(self, sample):
        if sample.value == 1:
            self.value_dict['Ph'] = self.labels['phase']

    def kube_node_status_capacity(self, sample):
        metric_type = self.labels['resource']
        if metric_type == 'cpu':
            self.value_dict['KNSCCC'] = sample.value
        elif metric_type == 'pods':
            self.value_dict['KNSCP'] = sample.value
        elif metric_type == 'memory':
            self.value_dict['KNSCMG'] = sample.value / 1073741824
            self.value_dict['KNSCMB'] = sample.value

    def kube_node_status_allocatable(self, sample):
        metric_type = self.labels['resource']
        if metric_type == 'cpu':
            self.value_dict['KNSACC'] = sample.value
        elif metric_type == 'pods':
            self.value_dict['KNSAP'] = sample.value
        elif metric_type == 'memory':
            self.value_dict['KNSAMB'] = sample.value

    def kube_pod_container_status_restarts(self, sample):
        self.value_dict['RC'] = self.value_dict.get('RC', 0) + sample.value
