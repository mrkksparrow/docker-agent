from com.manageengine.monagent.kubernetes.Parser.JSONParserInterface import JSONParser
from com.manageengine.monagent.kubernetes import KubeGlobal


class KubeletMetrics(JSONParser):
    def __init__(self, is_alternate_needed=False):
        super().__init__()
        self.metadata_needed = False
        self.paths_to_iterate = "pods"
        self.fetch_with_limit = False
        self.certificate_verification = False
        if is_alternate_needed:
            self.api_url = KubeGlobal.apiEndpoint + KubeGlobal.API_ENDPOINT_RES_NAME_MAP['kubeletStatsProxy'].format(KubeGlobal.KUBELET_NODE_NAME)
        else:
            self.api_url = ('https://[{}]:10250/stats/summary' if ":" in KubeGlobal.IP_ADDRESS else 'https://{}:10250/stats/summary').format(KubeGlobal.IP_ADDRESS)

    def get_dc_data(self, response):
        self.raw_data = response['node']
        KubeGlobal.KUBELET_NODE_NAME = self.raw_data['nodeName']
        self.parse_node_metrics()
        super().get_dc_data(response)

    def save_value_dict(self, root_name):
        self.final_dict['Pods'][root_name] = self.value_dict

    def get_root_name(self):
        return self.raw_data['podRef']['name'] + '_' + self.raw_data['podRef']['namespace']

    def get_perf_metrics(self):
        if KubeGlobal.KUBELET_ERROR:
            self.aggregate_container_perf_metrics()
            return

        # cpu metrics
        self.value_dict['UNC'] = self.get_2nd_path_value(['cpu', 'usageNanoCores'], 0) / 1000000
        self.value_dict['UNCS'] = self.get_2nd_path_value(['cpu', 'usageCoreNanoSeconds'], 0)

        # memory metrics
        self.value_dict['AB'] = self.get_2nd_path_value(['memory', 'availableBytes'])
        self.value_dict['UB'] = self.get_2nd_path_value(['memory', 'workingSetBytes']) / 1048576
        self.value_dict['RSSB'] = self.get_2nd_path_value(['memory', 'rssBytes']) / 1048576
        self.value_dict['PF'] = self.get_2nd_path_value(['memory', 'pageFaults'])

        # ephemeral storage metrics
        self.value_dict['EUB'] = self.get_2nd_path_value(['ephemeral-storage', 'usedBytes'])
        self.value_dict['ECB'] = self.get_2nd_path_value(['ephemeral-storage', 'capacityBytes'])

        # network metrics
        self.value_dict['NT'] = self.get_2nd_path_value(['network', 'time'])
        self.value_dict['NeN'] = self.get_2nd_path_value(['network', 'name'])
        self.value_dict['RB'] = self.get_2nd_path_value(['network', 'rxBytes'], 0) / 1024
        self.value_dict['RE'] = self.get_2nd_path_value(['network', 'rxErrors'])
        self.value_dict['TE'] = self.get_2nd_path_value(['network', 'txErrors'])
        self.value_dict['TB'] = self.get_2nd_path_value(['network', 'txBytes'], 0) / 1024

        # container cpu metric
        self.value_dict['Cont'] = {
            container['name']: {
                'KCACPU': container['cpu']['usageNanoCores'] / 1000000
            } for container in self.get_1st_path_value(['containers'], [])
        }

    def aggregate_container_perf_metrics(self):
        self.value_dict['Cont'] = {}
        for container in self.get_1st_path_value(['containers']):
            # memory metrics
            self.value_dict['AB'] = self.value_dict.get('AB', 0) + container['memory'].get('availableBytes', 0)
            self.value_dict['UB'] = self.value_dict.get('UB', 0) + (container['memory'].get('workingSetBytes', 0) / 1048576)
            self.value_dict['RSSB'] = self.value_dict.get('RSSB', 0) + (container['memory'].get('rssBytes', 0) / 1048576)
            self.value_dict['PF'] = self.value_dict.get('PF', 0) + container['memory'].get('pageFaults', 0)

            # cpu metrics
            self.value_dict['UNC'] = self.value_dict.get('UNC', 0) + (container['cpu'].get('usageNanoCores', 0) / 1000000)
            self.value_dict['UNCS'] = self.value_dict.get('UNCS', 0) + container['cpu'].get('usageCoreNanoSeconds', 0)

            # container cpu metric
            self.value_dict['Cont'][container['name']] = {
                'KCACPU': container['cpu']['usageNanoCores'] / 1000000
            }

    def parse_node_metrics(self):
        self.final_dict = {
            'Nodes': {
                self.get_1st_path_value(['nodeName']): {
                    'UNC': self.get_2nd_path_value(['cpu', 'usageNanoCores'], 0) / 1000000,
                    'UNS': self.get_2nd_path_value(['cpu', 'usageCoreNanoSeconds'], 0),
                    'CPUT': self.get_2nd_path_value(['cpu', 'time']),
                    'MT': self.get_2nd_path_value(['memory', 'time']),
                    'MAB': self.get_2nd_path_value(['memory', 'availableBytes'], 0),
                    'MUB': self.get_2nd_path_value(['memory', 'usageBytes'], 0),
                    'WSB': self.get_2nd_path_value(['memory', 'workingSetBytes'], 0),
                    'RSSB': self.get_2nd_path_value(['memory', 'rssBytes'], 0) / 1048576,
                    'PF': self.get_2nd_path_value(['memory', 'pageFaults'], 0),
                    'NeN': self.get_2nd_path_value(['network', 'name']),
                    'RB': self.get_2nd_path_value(['network', 'rxBytes'], 0),
                    'RE': self.get_2nd_path_value(['network', 'rxErrors'], 0),
                    'TE': self.get_2nd_path_value(['network', 'txErrors'], 0),
                    'TB': self.get_2nd_path_value(['network', 'txBytes'], 0),
                    'FSAB': self.get_2nd_path_value(['fs', 'availableBytes'], 0) / 1073741824,
                    'FSCB': self.get_2nd_path_value(['fs', 'capacityBytes'], 0) / 1073741824,
                    'FSUB': self.get_2nd_path_value(['fs', 'usedBytes'], 0) / 1073741824,
                    'FSINF': self.get_2nd_path_value(['fs', 'inodesFree'], 0),
                    'FSIN': self.get_2nd_path_value(['fs', 'inodes'], 0),
                    'FSINU': self.get_2nd_path_value(['fs', 'inodesUsed'], 0)
                }
            },
            'Pods': {}
        }
