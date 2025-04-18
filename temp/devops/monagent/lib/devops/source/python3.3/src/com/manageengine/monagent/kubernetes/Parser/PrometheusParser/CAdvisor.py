from com.manageengine.monagent.kubernetes.Parser.StateMetricsParser import PrometheusParser
from com.manageengine.monagent.kubernetes import KubeGlobal, KubeUtil

families = {
    'container_memory_working_set_bytes': ['Pods', ['pod', 'namespace'], 'KCAMUB', {'id': 'cid'}],
    'container_memory_cache': ['Pods', ['pod', 'namespace'], 'KCAMC', None],
    'container_memory_rss': ['Pods', ['pod', 'namespace'], 'KCAMRSS', None],
    'container_memory_swap': ['Pods', ['pod', 'namespace'], 'KCAMSWP', None],
    'container_file_descriptors': ['Pods', ['pod', 'namespace'], 'KCAFD', None],
    'container_network_transmit_bytes': ['Pods', ['pod', 'namespace'], 'KCANTB', None],
    'container_network_receive_bytes': ['Pods', ['pod', 'namespace'], 'KCANRB', None],
    'container_network_receive_errors': ['Pods', ['pod', 'namespace'], 'KCANERR', None],
    'container_network_receive_packets_dropped': ['Pods', ['pod', 'namespace'], 'KCANPD', None],
    'container_network_receive_packets': ['Pods', ['pod', 'namespace'], 'KCANPD', None],
    'container_network_transmit_packets': ['Pods', ['pod', 'namespace'], 'KCANPD', None],
    'container_processes': ['Pods', ['pod', 'namespace'], 'KCANP', None],
    'container_sockets': ['Pods', ['pod', 'namespace'], 'KCACS', None],
    'container_threads': ['Pods', ['pod', 'namespace'], 'KCACT', None],
    'container_memory_failcnt': ['Pods', ['pod', 'namespace'], 'KCAMFCT', None],
    'container_cpu_cfs_throttled_periods': ['Pods', ['pod', 'namespace'], 'throttled_periods', None],
    'container_cpu_cfs_periods': ['Pods', ['pod', 'namespace'], 'total_periods', None],
    'container_cpu_cfs_throttled_seconds': ['Pods', ['pod', 'namespace'], 'throttled_sec', None]
}
custom_parsers_family_names = [
    'container_memory_working_set_bytes',
    'container_memory_cache',
    'container_memory_rss',
    'container_memory_swap',
    'container_network_transmit_packets',
    'container_cpu_cfs_throttled_periods',
    'container_cpu_cfs_periods',
    'container_cpu_cfs_throttled_seconds'
]


class CAdvisor(PrometheusParser):
    def __init__(self):
        super().__init__(
            ("https://[{}]:{}/metrics/cadvisor" if ":" in KubeGlobal.IP_ADDRESS else "https://{}:{}/metrics/cadvisor")
            .format(KubeGlobal.IP_ADDRESS, KubeGlobal.kubeletStatsPort)
        )
        self.families = families
        self.token_needed = True
        self.custom_parsers_family_names = custom_parsers_family_names

    def container_memory_working_set_bytes(self, sample):
        self.value_dict['KCAMUB'] = sample.value / 1048576

    def container_memory_cache(self, sample):
        self.value_dict['KCAMC'] = sample.value / 1048576

    def container_memory_rss(self, sample):
        self.value_dict['KCAMRSS'] = sample.value / 1048576

    def container_memory_swap(self, sample):
        self.value_dict['KCAMSWP'] = sample.value / 1048576

    def container_cpu_cfs_throttled_periods(self, sample):
        self.value_dict['throttled_periods'] = KubeUtil.get_counter_value(
            self.labels['container']+self.labels['pod']+self.labels['namespace']+'KCTHP',
            sample.value,
            True
        )

    def container_cpu_cfs_periods(self, sample):
        self.value_dict['total_periods'] = KubeUtil.get_counter_value(
            self.labels['container']+self.labels['pod']+self.labels['namespace']+'KCP',
            sample.value,
            True
        )

    def container_cpu_cfs_throttled_seconds(self, sample):
        self.value_dict['throttled_sec'] = KubeUtil.get_counter_value(
            self.labels['container']+self.labels['pod']+self.labels['namespace']+'KCTHS',
            sample.value,
            True
        )

    def init_value_dict(self):
        family_template = self.families[self.family_name]
        root_name = self.get_root_name(family_template[1])

        if root_name:
            if root_name not in self.final_dict[family_template[0]]:
                self.final_dict[family_template[0]][root_name] = {
                    'Cont': {}
                }

            if self.labels['container']:
                if self.labels['container'] not in self.final_dict[family_template[0]][root_name]['Cont']:
                    self.final_dict[family_template[0]][root_name]['Cont'][self.labels['container']] = {}

                self.value_dict = self.final_dict[family_template[0]][root_name]['Cont'][self.labels['container']]
                return True
        return False

