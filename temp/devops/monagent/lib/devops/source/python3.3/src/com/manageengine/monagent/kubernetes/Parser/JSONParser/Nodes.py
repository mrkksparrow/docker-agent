from com.manageengine.monagent.kubernetes.Parser.JSONParserInterface import JSONParser
from com.manageengine.monagent.kubernetes import KubeGlobal, KubeUtil
import json


class Nodes(JSONParser):
    def __init__(self):
        super().__init__('Nodes')
        self.is_namespaces = False
        self.api_url += '&fieldSelector=metadata.name=' + KubeGlobal.KUBELET_NODE_NAME

    def get_data(self, discovery=False, yaml=False):
        if yaml or discovery:
            self.api_url = KubeGlobal.apiEndpoint + KubeGlobal.API_ENDPOINT_RES_NAME_MAP['Nodes']
        return super().get_data(discovery=discovery, yaml=yaml)

    def get_discovery_data(self, response):
        for value in response[self.paths_to_iterate]:
            self.registered_resource_key.pop(value['metadata']['name'], None)
        self.get_termination_data()

    def get_metadata(self):
        super().get_metadata()
        self.value_dict['An'] = json.dumps(self.get_2nd_path_value(['metadata', 'annotations']))
        self.value_dict['Lb'] = json.dumps(self.get_2nd_path_value(['metadata', 'labels']))
        self.value_dict['pCIDR'] = self.get_2nd_path_value(['spec', 'podCIDR'])
        self.value_dict['pID'] = self.get_2nd_path_value(['spec', 'providerID'])
        self.value_dict['CAVAD'] = self.get_2nd_path_value(['status', 'attachable-volumes-azure-disk'])
        self.value_dict['KV'] = self.get_3rd_path_value(['status', 'nodeInfo', 'kernelVersion'])
        self.value_dict['KuV'] = self.get_3rd_path_value(['status', 'nodeInfo', 'kubeletVersion'])
        self.value_dict['CRTV'] = self.get_3rd_path_value(['status', 'nodeInfo', 'containerRuntimeVersion'])
        self.value_dict['MaId'] = self.get_3rd_path_value(['status', 'nodeInfo', 'machineID'])
        self.value_dict['KPV'] = self.get_3rd_path_value(['status', 'nodeInfo', 'kubeProxyVersion'])
        self.value_dict['BId'] = self.get_3rd_path_value(['status', 'nodeInfo', 'bootID'])
        self.value_dict['OSI'] = self.get_3rd_path_value(['status', 'nodeInfo', 'osImage'])
        self.value_dict['Ar'] = self.get_3rd_path_value(['status', 'nodeInfo', 'architecture'])
        self.value_dict['SUUID'] = self.get_3rd_path_value(['status', 'nodeInfo', 'systemUUID'])
        self.value_dict['OS'] = self.get_3rd_path_value(['status', 'nodeInfo', 'operatingSystem'])
        self.value_dict["taints"] = json.dumps({
            each['key']: '=' + each.get('value', '') + ":" + each['effect'] for each in self.get_2nd_path_value(['spec', 'taints'], [])
        })

    def get_perf_metrics(self):
        # capacity metrics
        self.value_dict['CCPU'] = self.get_3rd_path_value(['status', 'capacity', 'cpu'])
        self.value_dict['CMem'] = self.get_3rd_path_value(['status', 'capacity', 'memory'])
        self.value_dict['CPC'] = self.get_3rd_path_value(['status', 'capacity', 'pods'])
        self.value_dict['CESTO'] = self.get_3rd_path_value(['status', 'capacity', 'ephemeral-storage'])
        self.value_dict['CHP1'] = self.get_3rd_path_value(['status', 'capacity', 'hugepages-1Gi'])
        self.value_dict['CHP2'] = self.get_3rd_path_value(['status', 'capacity', 'hugepages-2Mi'])

        # allocatable metrics
        self.value_dict['AAVAD'] = self.get_3rd_path_value(['status', 'allocatable', 'attachable-volumes-azure-disk'])
        self.value_dict['ACPU'] = self.get_3rd_path_value(['status', 'allocatable', 'cpu'])
        self.value_dict['AESTO'] = self.get_3rd_path_value(['status', 'allocatable', "ephemeral-storage"])
        self.value_dict['AHP1'] = self.get_3rd_path_value(['status', 'allocatable', "hugepages-1Gi"])
        self.value_dict["AHP2"] = self.get_3rd_path_value(['status', 'allocatable', "hugepages-2Mi"])
        self.value_dict['AMem'] = self.get_3rd_path_value(['status', 'allocatable', 'memory'])
        self.value_dict['APC'] = self.get_3rd_path_value(['status', 'allocatable', 'pods'])

        # capacity metrics
        self.value_dict['KNSCCC'] = KubeUtil.convert_cpu_values_to_standard_units(self.get_3rd_path_value(['status', 'capacity', 'cpu'], 0)) / 1000
        self.value_dict['KNSCMB'] = KubeUtil.convert_values_to_standard_units(self.get_3rd_path_value(['status', 'capacity', 'memory']))
        self.value_dict['KNSCMG'] = self.value_dict['KNSCMB'] / 1073741824
        self.value_dict['KNSCP'] = self.get_3rd_path_value(['status', 'capacity', 'pods'])

        # allocatable metrics
        self.value_dict['KNSACC'] = KubeUtil.convert_cpu_values_to_standard_units(self.get_3rd_path_value(['status', 'allocatable', 'cpu'], 0)) / 1000
        self.value_dict['KNSAMB'] = KubeUtil.convert_values_to_standard_units(self.get_3rd_path_value(['status', 'allocatable', 'memory']))
        self.value_dict['KNSAMG'] = self.value_dict['KNSAMB'] / 1073741824
        self.value_dict['KNSAP'] = self.get_3rd_path_value(['status', 'allocatable', 'pods'])

        # conditions
        self.value_dict['Cnds'] = {
            cnds['type']: {
                'St': cnds['status'],
                'LHBT': cnds['lastHeartbeatTime'],
                'LTT': cnds['lastTransitionTime'],
                'Re': cnds['reason'],
                'Me': cnds['message']
            } for cnds in self.get_2nd_path_value(['status', 'conditions'])
        }

        # ready status
        self.value_dict["ready_status"] = "Ready" if self.value_dict['Cnds'].get("Ready").get("St") == "True" else "Not Ready"

        # schedulability
        self.value_dict['KNSU'] = 1 if self.get_2nd_path_value(['spec', 'unschedulable'], False) else 0
