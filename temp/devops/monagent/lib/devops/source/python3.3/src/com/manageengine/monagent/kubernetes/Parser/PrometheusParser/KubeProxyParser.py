import time
import math

from com.manageengine.monagent.kubernetes.Parser.StateMetricsParser import PrometheusParser
from com.manageengine.monagent.kubernetes import KubeGlobal, KubeUtil


families = {
    'process_cpu_seconds': ['KubeProxy', None, None, None],
    'process_resident_memory_bytes': ['KubeProxy', None, 'rss_mem', None],
    'process_virtual_memory_bytes': ['KubeProxy', None, 'virtual_mem', None],
    'rest_client_exec_plugin_certificate_rotation_age': ['KubeProxy', None, None, None],
    'rest_client_exec_plugin_ttl_seconds': ['KubeProxy', None, 'exec_plugin_ttl', None],
    'rest_client_request_duration_seconds': ['KubeProxy', None, None, None],
    'rest_client_requests': ['KubeProxy', None, None, None],
    'kubeproxy_sync_proxy_rules_duration_seconds': ['KubeProxy', None, None, None],
    'kubeproxy_sync_proxy_rules_endpoint_changes_pending': ['KubeProxy', None, 'proxy_rule_endpoint_change_pending', None],
    'kubeproxy_sync_proxy_rules_endpoint_changes_total': ['KubeProxy', None, 'proxy_rule_endpoint_change_total', None],
    'kubeproxy_sync_proxy_rules_iptables_restore_failures': ['KubeProxy', None, None, None],
    'kubeproxy_sync_proxy_rules_last_queued_timestamp_seconds': ['KubeProxy', None, 'last_queued_time', None],
    'kubeproxy_sync_proxy_rules_last_timestamp_seconds': ['KubeProxy', None, 'last_synced_time', None],
    'kubeproxy_sync_proxy_rules_iptables_total': ['KubeProxy', None, None, None],
    'kubeproxy_sync_proxy_rules_service_changes_pending': ['KubeProxy', None, 'service_change_pending', None],
    'kubeproxy_sync_proxy_rules_service_changes': ['KubeProxy', None, None, None],
    'kubeproxy_network_programming_duration_seconds': ['KubeProxy', None, None, None],
    'process_start_time_seconds': ['KubeProxy', None, 'start_time', None],
    'process_open_fds': ['KubeProxy', None, 'open_fd', None],
    'go_threads': ['KubeProxy', None, 'go_thread', None],
    'go_goroutines': ['KubeProxy', None, 'goroutines', None]
}
custom_parsers_family = [
    'process_cpu_seconds',
    'rest_client_exec_plugin_certificate_rotation_age',
    'rest_client_request_duration_seconds',
    'rest_client_requests',
    'kubeproxy_sync_proxy_rules_duration_seconds',
    'kubeproxy_sync_proxy_rules_iptables_restore_failures',
    'kubeproxy_sync_proxy_rules_iptables_total',
    'kubeproxy_sync_proxy_rules_service_changes',
    'kubeproxy_network_programming_duration_seconds',
    'kubeproxy_sync_proxy_rules_last_queued_timestamp_seconds',
    'kubeproxy_sync_proxy_rules_last_timestamp_seconds',
    'rest_client_exec_plugin_ttl_seconds',
    'process_start_time_seconds'
]

class KubeProxy(PrometheusParser):
    def __init__(self):
        super().__init__(KubeUtil.construct_node_ip_url('http://{}:10249/metrics', KubeGlobal.IP_ADDRESS))
        self.families = families
        self.custom_parsers_family_names = custom_parsers_family
        self.token_needed = False

    def kubeproxy_sync_proxy_rules_last_queued_timestamp_seconds(self, sample):
        self.value_dict['last_queued_time'] = (sample.value * 1000) if isinstance(sample.value, int) or isinstance(sample.value, float) else str(sample.value)

    def kubeproxy_sync_proxy_rules_last_timestamp_seconds(self, sample):
        self.value_dict['last_synced_time'] = (sample.value * 1000) if isinstance(sample.value, int) or isinstance(sample.value, float) else str(sample.value)

    def rest_client_exec_plugin_ttl_seconds(self, sample):
        self.value_dict['exec_plugin_ttl'] = (sample.value * 1000) if not math.isinf(sample.value) else "infinity"

    def process_start_time_seconds(self, sample):
        self.value_dict['start_time'] = (sample.value * 1000) if isinstance(sample.value, int) or isinstance(sample.value, float) else str(sample.value)

    def process_cpu_seconds(self, sample):
        self.value_dict['process_cpu'] = KubeUtil.get_counter_value('process_cpu', sample.value, True)

    def rest_client_exec_plugin_certificate_rotation_age(self, sample):
        if sample.name.endswith('_sum'):
            self.value_dict['plugin_cert_rotation_age_sum'] = KubeUtil.get_counter_value('plugin_cert_rotation_age_sum', sample.value, True)
        if sample.name.endswith('_count'):
            self.value_dict['plugin_cert_rotation_age_count'] = KubeUtil.get_counter_value('plugin_cert_rotation_age_count', sample.value, True)

        if self.value_dict.get('plugin_cert_rotation_age_sum') and self.value_dict.get('plugin_cert_rotation_age_count'):
            self.value_dict['plugin_cert_rotation_age'] = round(self.value_dict['plugin_cert_rotation_age_sum'] / self.value_dict['plugin_cert_rotation_age_count'], 2)
        else:
            self.value_dict['plugin_cert_rotation_age'] = 0

    def rest_client_request_duration_seconds(self, sample):
        if sample.name.endswith('_sum'):
            if 'request_verb' not in self.value_dict or self.labels['verb'] not in self.value_dict['request_verb']:
                self.value_dict['request_verb'] = self.value_dict.get('request_verb', {})
                self.value_dict['request_verb'][self.labels['verb']] = {}
            if 'request_host_duration' not in self.value_dict or self.labels['host'] not in self.value_dict['request_host_duration']:
                self.value_dict['request_host_duration'] = self.value_dict.get('request_host_duration', {})
                self.value_dict['request_host_duration'][self.labels['host']] = {}

            value = KubeUtil.get_counter_value('duration' + self.labels['verb'] + self.labels['host'], sample.value, True)
            self.value_dict['request_verb'][self.labels['verb']]['duration'] = value + self.value_dict['request_verb'][self.labels['verb']].get('duration', 0)
            self.value_dict['request_host_duration'][self.labels['host']][self.labels['verb']] = value

    def rest_client_requests(self, sample):
        if 'request_verb' not in self.value_dict or self.labels['method'] not in self.value_dict['request_verb']:
            self.value_dict['request_verb'] = self.value_dict.get('request_verb', {})
            self.value_dict['request_verb'][self.labels['method']] = {}
        if 'request_code' not in self.value_dict or self.labels['code'] not in self.value_dict['request_code']:
            self.value_dict['request_code'] = self.value_dict.get('request_code', {})
            self.value_dict['request_code'][self.labels['code']] = {}
        if 'request_host_verb' not in self.value_dict or self.labels['host'] not in self.value_dict['request_host_verb']:
            self.value_dict['request_host_verb'] = self.value_dict.get('request_host_verb', {})
            self.value_dict['request_host_verb'][self.labels['host']] = {}
        if 'request_host_code' not in self.value_dict or self.labels['host'] not in self.value_dict['request_host_code']:
            self.value_dict['request_host_code'] = self.value_dict.get('request_host_code', {})
            self.value_dict['request_host_code'][self.labels['host']] = {}

        count_pi = KubeUtil.get_counter_value('count' + self.labels['host'] + self.labels['code'] + self.labels['method'], sample.value, True)
        self.value_dict['request_verb'][self.labels['method']]['count'] = sample.value + self.value_dict['request_verb'][self.labels['method']].get('count', 0)
        self.value_dict['request_verb'][self.labels['method']]['count_pi'] = count_pi + self.value_dict['request_verb'][self.labels['method']].get('count_pi', 0)
        self.value_dict['request_code'][self.labels['code']]['count'] = sample.value + self.value_dict['request_code'][self.labels['code']].get('count', 0)
        self.value_dict['request_code'][self.labels['code']]['count_pi'] = count_pi + self.value_dict['request_code'][self.labels['code']].get('count_pi', 0)
        self.value_dict['request_host_verb'][self.labels['host']][self.labels['method']] = count_pi + self.value_dict['request_host_verb'][self.labels['host']].get(self.labels['method'], 0)
        self.value_dict['request_host_code'][self.labels['host']][self.labels['code']] = count_pi + self.value_dict['request_host_code'][self.labels['host']].get(self.labels['code'], 0)

    def kubeproxy_sync_proxy_rules_duration_seconds(self, sample):
        if sample.name.endswith('_sum'):
            self.value_dict['proxy_rule_sync_latency_sum'] = KubeUtil.get_counter_value('sync_proxy_s', sample.value, True)
        if sample.name.endswith('_count'):
            self.value_dict['proxy_rule_sync_latency_count'] = KubeUtil.get_counter_value('sync_proxy_c', sample.value, True)

        if self.value_dict.get('proxy_rule_sync_latency_sum') and self.value_dict.get('proxy_rule_sync_latency_count'):
            self.value_dict['proxy_rule_sync_latency'] = round(self.value_dict['proxy_rule_sync_latency_sum'] / self.value_dict['proxy_rule_sync_latency_count'], 2)
        else:
            self.value_dict['proxy_rule_sync_latency'] = 0

    def kubeproxy_sync_proxy_rules_iptables_restore_failures(self, sample):
        self.value_dict['iptables_restore_failed_tot'] = sample.value
        self.value_dict['iptables_restore_failed_pi'] = KubeUtil.get_counter_value('iptables_restore_failed_pi', sample.value, True)

    def kubeproxy_sync_proxy_rules_iptables_total(self, sample):
        self.value_dict['total_rules_synced'] = self.value_dict.get('total_rules_synced', 0) + sample.value

    def kubeproxy_sync_proxy_rules_service_changes(self, sample):
        self.value_dict['service_change_tot'] = sample.value
        self.value_dict['service_change_pi'] = KubeUtil.get_counter_value('service_change', sample.value, True)

    def kubeproxy_network_programming_duration_seconds(self, sample):
        if sample.name.endswith('_sum'):
            self.value_dict['network_program_time_sum'] = KubeUtil.get_counter_value('npts', sample.value, True)
        if sample.name.endswith('_count'):
            self.value_dict['network_program_time_count'] = KubeUtil.get_counter_value('nptc', sample.value, True)

        if self.value_dict.get('network_program_time_sum') and self.value_dict.get('network_program_time_count'):
            self.value_dict['network_program_time'] = round(self.value_dict['network_program_time_sum'] / self.value_dict['network_program_time_count'], 2)
        else:
            self.value_dict['network_program_time'] = 0
