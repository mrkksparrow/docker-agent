import copy

from com.manageengine.monagent.kubernetes.Collector.DataCollectorInterface import DataCollector
from com.manageengine.monagent.kubernetes.Parser.ParserFactory import get_prometheus_parser
from com.manageengine.monagent.kubernetes.ClusterAgent import ClusterAgentUtil
from com.manageengine.monagent.kubernetes import KubeUtil, KubeGlobal
from com.manageengine.monagent.kubernetes.Logging import KubeLogger as AgentLogger

import traceback

LAST_CONFIG_IDS = {
    'all_pods': []
}
CONFIG_VS_RD = {
    'DaemonSets': 'Daemonset',
    'Deployments': 'Deployment',
    'Ingresses': 'Ingress',
    'StatefulSets': 'Statefulset',
    'Services': 'Service',
    'Nodes': 'Node',
    'Namespaces': 'Namespace',
    'PersistentVolumeClaim': 'PVC'
}


class ResourceDependency(DataCollector):
    def __init__(self, dc_requisites_obj):
        super().__init__(dc_requisites_obj)
        self.controller_relational = None
        self.svc_relational = {}
        self.pod_name = None
        self.namespace = None
        self.final_json = {'resources': {}, 'Ingress': {}}
        self.newly_added_resources = {}
        self.send_complete_dependency = False

    def get_cluster_agent_request_params(self):
        return {
            'kube_ids': KubeGlobal.kubeIds,
            'pod_list': KubeGlobal.CLUSTER_POD_LIST,
            'send_complete_dependency': KubeUtil.is_eligible_to_execute("resourcedependency_complete", KubeGlobal.DC_START_TIME)
        }

    def collect_data(self):
        self.send_complete_dependency = KubeUtil.is_eligible_to_execute("resourcedependency_complete", KubeGlobal.DC_START_TIME)
        self.get_newly_added_resources()

        if self.newly_added_resources or self.send_complete_dependency:
            self.controller_relational = get_prometheus_parser('ResourceDependency')().get_data()
            KubeUtil.get_api_data_by_limit(
                KubeGlobal.apiEndpoint + KubeGlobal.API_ENDPOINT_RES_NAME_MAP['Services'],
                self.hash_service_selectors,
                self.svc_relational
            )
            self.build_pod_dependency()
            if not self.send_complete_dependency:
                self.remove_old_resources()

    def get_data_for_cluster_agent(self, req_params=None):
        KubeGlobal.kubeIds = req_params['kube_ids']
        KubeGlobal.CLUSTER_POD_LIST = req_params['pod_list']
        self.send_complete_dependency = req_params['send_complete_dependency']
        self.get_newly_added_resources()

        if self.newly_added_resources or self.send_complete_dependency:
            self.controller_relational = ClusterAgentUtil.get_parsed_data_for_ca("resource_dependency_ksm")
            self.svc_relational = ClusterAgentUtil.get_parsed_data_for_ca("service_rs")
            self.build_pod_dependency()
            if not self.send_complete_dependency:
                self.remove_old_resources()
        return self.final_json

    def build_pod_dependency(self):
        for pod_name, pod_value in self.controller_relational.get('Pod', {}).items():
            self.namespace = pod_value[0]['ns']
            self.pod_name = pod_name
            self.final_json['resources'][self.pod_name] = {
                'Namespace': self.namespace,
                'Node': pod_value[0]['node']
            }
            if self.pod_name in self.controller_relational['Container']:
                self.final_json['resources'][self.pod_name]['Container'] = [
                    '{}_{}'.format(
                        cont_name['cont_name'], self.pod_name
                    ) for cont_name in self.controller_relational['Container'][self.pod_name]
                ]
            self.identify_owner_controller()
            self.build_svc_relation()
            self.build_pv_relation()
        self.final_json['Ingress'] = self.controller_relational.get('Ingress', {})

    def identify_owner_controller(self):
        if self.pod_name in self.controller_relational['Owner']:
            owner_kind = self.controller_relational['Owner'][self.pod_name][0].get('kind')
            owner_name = self.controller_relational['Owner'][self.pod_name][0].get('owner_name') + '_' + self.namespace
            if owner_kind == 'ReplicaSet':
                if owner_name in self.controller_relational['ReplicaSet'] and self.controller_relational['ReplicaSet'][owner_name][0]['owner_kind'] == 'Deployment':
                    deploy_name = self.controller_relational['ReplicaSet'][owner_name][0]['owner_name'] + '_' + self.namespace
                    self.final_json['resources'][self.pod_name]['Deployment'] = deploy_name
                    self.check_hpa_exists(deploy_name, 'Deployment')
            elif owner_kind == 'StatefulSet':
                self.final_json['resources'][self.pod_name]['Statefulset'] = owner_name
                self.check_hpa_exists(owner_name, owner_kind)
            elif owner_kind == 'DaemonSet':
                self.final_json['resources'][self.pod_name]['Daemonset'] = owner_name

    def build_svc_relation(self):
        if self.pod_name in self.svc_relational:
            self.final_json['resources'][self.pod_name]['Service'] = [svc + '_' + self.namespace for svc in self.svc_relational[self.pod_name]]

    def build_pv_relation(self):
        if self.pod_name in self.controller_relational['PVC']:
            self.final_json['resources'][self.pod_name]['PVC'] = []
            for pvc in self.controller_relational['PVC'][self.pod_name]:
                if pvc in self.controller_relational['PV']:
                    self.final_json['resources'][self.pod_name]['PVC'].append({pvc: self.controller_relational['PV'][pvc][0]['pv']})

    def check_hpa_exists(self, child_name, child_kind):
        if child_name in self.controller_relational['HPA'] and self.controller_relational['HPA'][child_name][0]['child_kind'] == child_kind:
            self.final_json['resources'][self.pod_name]['HPA'] = self.controller_relational['HPA'][child_name][0]['hpa'] + '_' + self.namespace

    def hash_service_selectors(self, service_data, lookup_dict):
        try:
            for val in service_data['items']:
                try:
                    name = val['metadata']['name']
                    ns = val['metadata']['namespace']
                    if 'spec' in val and 'selector' in val['spec']:
                        sel = val['spec']['selector']
                        match_labels = []
                        for key, value in sel.items():
                            match_labels.append("{}%3D{}".format(key, value))

                        status, api_resp = KubeUtil.curl_api_with_token(KubeGlobal.apiEndpoint + "/api/v1/namespaces/{}/pods?labelSelector={}".format(ns, ",".join(match_labels)))
                        if status == 200:
                            for pod_value in api_resp["items"]:
                                pod_name = pod_value['metadata']['name'] + "_" + ns
                                if pod_name not in lookup_dict:
                                    lookup_dict[pod_name] = []
                                lookup_dict[pod_name].append(name)
                except Exception:
                    continue
        except Exception as e:
            traceback.print_exc()

    def remove_old_resources(self):
        # removing pods if either itself or relatives are not newly added
        pods_to_remove = []
        for pod_name, pod_relatives in self.final_json.get("resources", {}).items():
            if 'Pods' in self.newly_added_resources and pod_name in self.newly_added_resources['Pods']:
                continue

            remove_flag = 1
            for relative_type, relative_name in pod_relatives.items():
                if relative_type in self.newly_added_resources:
                    if not isinstance(relative_name, list):
                        if relative_name in self.newly_added_resources[relative_type]:
                            remove_flag = 0
                    else:
                        for relative in relative_name:
                            name = list(relative.keys())[0] if isinstance(relative, dict) else relative
                            if name in self.newly_added_resources[relative_type]:
                                remove_flag = 0

                if not remove_flag:
                    break

            if remove_flag:
                pods_to_remove.append(pod_name)

        for pod in pods_to_remove:
            self.final_json['resources'].pop(pod, None)

        # removing Ingress if ingress is not newly added
        ingress_to_remove = []
        for ingress in self.final_json.get('Ingress'):
            if 'Ingress' not in self.newly_added_resources or ingress not in self.newly_added_resources['Ingress']:
                ingress_to_remove.append(ingress)

        for ingress in ingress_to_remove:
            self.final_json['Ingress'].pop(ingress, None)

    def get_newly_added_resources(self):
        global LAST_CONFIG_IDS
        try:
            # detecting newly added workloads
            for res_type, resources in KubeGlobal.kubeIds.items():
                if res_type in ['Pods', 'ReplicaSets', 'Jobs', 'Endpoints']:
                    continue

                res_type_node_name = CONFIG_VS_RD[res_type] if res_type in CONFIG_VS_RD else res_type
                for res_name in resources:
                    if res_type not in LAST_CONFIG_IDS or res_name not in LAST_CONFIG_IDS[res_type]:
                        if res_type_node_name not in self.newly_added_resources:
                            self.newly_added_resources[res_type_node_name] = []
                        self.newly_added_resources[res_type_node_name].append(res_name)

            # detecting newly added pods
            newly_added_pods = list(filter(lambda pod_name: pod_name not in LAST_CONFIG_IDS['all_pods'], KubeGlobal.CLUSTER_POD_LIST))
            if newly_added_pods:
                self.newly_added_resources['Pods'] = newly_added_pods

            if self.newly_added_resources:
                AgentLogger.log(AgentLogger.KUBERNETES, "Newly added resources for ResourceDependency task - {}".format(self.newly_added_resources))
        except Exception:
            traceback.print_exc()
        LAST_CONFIG_IDS = copy.deepcopy(KubeGlobal.kubeIds)
        LAST_CONFIG_IDS['all_pods'] = KubeGlobal.CLUSTER_POD_LIST.copy()
