import traceback

from com.manageengine.monagent.kubernetes.Parser.JSONParserInterface import JSONParser
from com.manageengine.monagent.kubernetes import KubeGlobal, KubeUtil
import json


class Pods(JSONParser):
    def __init__(self):
        super().__init__('Pods')
        self.api_url += '&fieldSelector=spec.nodeName=' + KubeGlobal.KUBELET_NODE_NAME

    def get_termination_data(self):
        self.api_url = KubeGlobal.apiEndpoint + KubeGlobal.API_ENDPOINT_RES_NAME_MAP[self.type]
        super().get_termination_data()

    def get_metadata(self):
        super().get_metadata()
        self.value_dict['GN'] = self.get_2nd_path_value(['metadata', 'generateName'])
        self.value_dict['RP'] = self.get_2nd_path_value(['spec', 'restartPolicy'])
        self.value_dict['TGS'] = self.get_2nd_path_value(['spec', 'terminationGracePeriodSeconds'])
        self.value_dict['DNSP'] = self.get_2nd_path_value(['spec', 'dnsPolicy'])
        self.value_dict['SAN'] = self.get_2nd_path_value(['spec', 'serviceAccountName'])
        self.value_dict['SA'] = self.get_2nd_path_value(['spec', 'serviceAccount'])
        self.value_dict['NN'] = self.get_2nd_path_value(['spec', 'nodeName'])
        self.value_dict['Pr'] = self.get_2nd_path_value(['spec', 'priority'])
        self.value_dict['owner_kind'], self.value_dict['owner_name'] = self.get_pod_owner_data()
        self.value_dict['node'] = self.get_2nd_path_value(['spec', 'nodeName'])
        self.value_dict['tolerations'] = self.get_pod_toleration()

    def get_perf_metrics(self):
        try:
            self.value_dict['HIP'] = self.get_2nd_path_value(['status', 'hostIP'])
            self.value_dict['Ph'] = self.get_2nd_path_value(['status', 'phase'])
            self.value_dict['PIP'] = self.get_2nd_path_value(['status', 'podIP'])
            self.value_dict['SaT'] = self.get_2nd_path_value('status', 'startTime')
            self.value_dict['QosC'] = self.get_2nd_path_value('status', 'qosClass')
            self.value_dict['PFR'] = self.get_2nd_path_value(['status', 'reason'])
            self.value_dict['p_status'] = None
            self.value_dict.update({
                'PRC': 0,
                'rd_c': 0,
                'tc': 0,
                'KPRCPI': 0,
                'PRLCC': 0,
                'PRLMB': 0,
                'PRRCC': 0,
                'PRMB': 0
            })

            # pod conditions
            self.value_dict['Cnds'] = {
                cnd['type']: {
                    'St': cnd['status'],
                    'LPT': cnd['lastProbeTime'],
                    'LTT': cnd['lastTransitionTime']
                } for cnd in self.get_2nd_path_value(['status', 'conditions'], [])
            }
            self.value_dict['KPSR'] = 0 if 'Ready' not in self.value_dict['Cnds'] or not self.value_dict['Cnds']['Ready']['St'] else 1
            self.parse_container_data()

            # container and pod status based metrics
            for cont_status in self.get_2nd_path_value(['status', 'containerStatuses'], []):
                self.value_dict['Cont'][cont_status['name']]['RC'] = cont_status.get('restartCount', 0)
                self.value_dict['Cont'][cont_status['name']]["KCRCPI"] = KubeUtil.get_counter_value(self.raw_data['metadata']['uid']+cont_status['name']+'KCRCPI', cont_status.get('restartCount', 0), True)
                self.value_dict['Cont'][cont_status['name']]['IM'] = cont_status['image']
                self.value_dict['Cont'][cont_status['name']]['IMId'] = cont_status['imageID']
                self.value_dict['Cont'][cont_status['name']]['CId'] = cont_status.get('containerID')
                self.value_dict['Cont'][cont_status['name']]['KPCSRe'] = cont_status.get('ready')
                self.value_dict['rd_c'] = self.value_dict['rd_c'] + 1 if cont_status.get('ready') else self.value_dict['rd_c']
                self.value_dict['PRC'] += cont_status.get('restartCount', 0)

                if "waiting" in cont_status.get('state', '') and "reason" in cont_status.get('state', '')["waiting"]:
                    message = cont_status['state']['waiting'].get('message')
                    self.value_dict['Cont'][cont_status['name']]['Ph'] = "waiting"
                    self.value_dict['Cont'][cont_status['name']]['cont_status'] = self.value_dict['p_status'] = cont_status['state']["waiting"]["reason"]
                    self.value_dict['Cont'][cont_status['name']]['reason_cont_status'] = message
                    self.value_dict['Cont'][cont_status['name']]['reason_KPCSRe'] = message
                    self.value_dict['Cont'][cont_status['name']]['reason_Ph'] = message
                elif "terminated" in cont_status.get('state', '') and "reason" in cont_status.get('state', '')["terminated"]:
                    reason = cont_status['state']["terminated"]["reason"]
                    message = cont_status['state']['terminated'].get('message')
                    self.value_dict['Cont'][cont_status['name']]["Ph"] = 'terminated'
                    self.value_dict['Cont'][cont_status['name']]['cont_status'] = reason
                    self.value_dict['Cont'][cont_status['name']]['reason_cont_status'] = message
                    self.value_dict['Cont'][cont_status['name']]['reason_KPCSRe'] = message
                    if reason != 'Completed' and 'p_status' not in self.value_dict:
                        self.value_dict['p_status'] = reason
                        self.value_dict['Cont'][cont_status['name']]['reason_Ph'] = message
                else:
                    self.value_dict['Cont'][cont_status['name']]['Ph'] = 'Running'
                    self.value_dict['Cont'][cont_status['name']]['cont_status'] = "Running"

            self.value_dict['KPRCPI'] = KubeUtil.get_counter_value(self.raw_data['metadata']['uid']+'KPRCPI', self.value_dict['PRC'], True)

            if self.value_dict['PFR']:
                self.value_dict['p_status'] = self.value_dict['PFR']
                self.value_dict['reason_Ph'] = self.get_2nd_path_value(['status', 'message'])

            if not self.value_dict['p_status']:
                self.value_dict['p_status'] = self.value_dict['Ph']
        except Exception:
            traceback.print_exc()

    def get_pod_owner_data(self):
        try:
            owner_ref = self.get_2nd_path_value(['metadata', 'ownerReferences'], [])
            if owner_ref and len(owner_ref) > 0 and 'kind' in owner_ref[0]:
                self.value_dict['owner_info'] = "{}_{}_{}".format(owner_ref[0]['kind'], owner_ref[0]['name'], self.value_dict['NS'])
                return owner_ref[0]['kind'], owner_ref[0]['name']
        except Exception:
            return "", ""
        return "", ""

    def parse_container_data(self):
        self.value_dict['Cont'] = {}
        for container in self.get_2nd_path_value(['spec', 'containers']):
            self.value_dict['tc'] += 1
            self.value_dict['Cont'][container['name']] = {
                'Na': container['name'],
                'Im': container['image'],
                'TMP': container.get('terminationMessagePath', ''),
                'TMPo': container.get('terminationMessagePolicy', ''),
                'IPPo': container.get('imagePullPolicy', ''),
                'ContPo': json.dumps({
                    port['containerPort']: {
                        'Pro': container.get('protocol'),
                        'Na': container['name']
                    } for port in container.get('ports', [])
                })
            }
            self.get_request_limit_data(container)

    def get_request_limit_data(self, container):
        cont_name = container['name']
        requested_resource = container.get('resources', {}).get('requests')
        resource_limits = container.get('resources', {}).get('limits')

        if resource_limits:
            if 'cpu' in resource_limits:
                prlcc = KubeUtil.convert_cpu_values_to_standard_units(resource_limits['cpu'])
                self.value_dict['Cont'][cont_name]['KPCRLCC'] = prlcc
                self.value_dict['Cont'][cont_name]['RLCPU'] = prlcc
                self.value_dict['PRLCC'] += prlcc

            if 'memory' in resource_limits:
                prlmb = KubeUtil.convert_values_to_standard_units(resource_limits['memory']) / 1048576
                self.value_dict['Cont'][cont_name]['KPCRLMB'] = prlmb
                self.value_dict['Cont'][cont_name]['RLMe'] = prlmb
                self.value_dict['PRLMB'] += prlmb

        if requested_resource:
            if 'cpu' in requested_resource:
                prrcc = KubeUtil.convert_cpu_values_to_standard_units(requested_resource['cpu'])
                self.value_dict['Cont'][cont_name]['KPCRRCC'] = prrcc
                self.value_dict['Cont'][cont_name]['RRCPU'] = prrcc
                self.value_dict['PRRCC'] += prrcc

            if 'memory' in requested_resource:
                prmb = KubeUtil.convert_values_to_standard_units(requested_resource['memory']) / 1048576
                self.value_dict['Cont'][cont_name]['KPCRRMB'] = prmb
                self.value_dict['Cont'][cont_name]['RRMe'] = prmb
                self.value_dict['PRMB'] += prmb

    def get_pod_toleration(self):
        pod_tolerations = {}
        for each in self.get_2nd_path_value(['spec', 'tolerations'], []):
            tolk = each["key"] if "key" in each else ""
            tolop = each["operator"] if "operator" in each else ""
            toleff = each["effect"] if "effect" in each else ""
            tolsecs = each["tolerationSeconds"] if "tolerationSeconds" in each else ""
            if tolsecs:
                pod_tolerations[tolk] = toleff + " " + "op = " + tolop + " for " + str(tolsecs) + "s"
            else:
                pod_tolerations[tolk] = toleff + " " + "op = " + tolop
        return json.dumps(pod_tolerations)
