from com.manageengine.monagent.kubernetes.Parser.StateMetricsParser import PrometheusParser
from com.manageengine.monagent.kubernetes import KubeGlobal

families = {
    'kube_pod_owner': ['Owner', ['pod', 'namespace'], None, {'owner_kind': 'kind', 'owner_name': 'owner_name'}],
    'kube_pod_info': ['Pod', ['pod', 'namespace'], None, {'node': 'node', 'namespace': 'ns'}],
    'kube_pod_container_info': ['Container', ['pod', 'namespace'], None, {'container': 'cont_name'}],
    'kube_replicaset_owner': ['ReplicaSet', ['replicaset', 'namespace'], None, {'owner_name': 'owner_name', 'owner_kind': 'owner_kind'}],
    'kube_ingress_path': ['Ingress', ['ingress', 'namespace'], None, None],
    'kube_horizontalpodautoscaler_info': ['HPA', ['scaletargetref_name', 'namespace'], None, {'scaletargetref_kind': 'child_kind', 'horizontalpodautoscaler': 'hpa'}],
    'kube_pod_spec_volumes_persistentvolumeclaims_info': ['PVC', ['pod', 'namespace'], None, None],
    'kube_persistentvolume_claim_ref': ['PV', ['name', 'claim_namespace'], None, {'persistentvolume': 'pv'}]
}

custom_parser_family_name = ['kube_ingress_path', 'kube_pod_spec_volumes_persistentvolumeclaims_info']


class ResourceDependency(PrometheusParser):
    def __init__(self):
        super().__init__(KubeGlobal.kubeStateMetricsUrl + '/metrics')
        self.families = families
        self.custom_parsers_family_names = custom_parser_family_name

    def init_value_dict(self):
        family_template = self.families[self.family_name]
        if family_template[1]:
            root_name = self.get_root_name(family_template[1])

            if root_name:
                if root_name not in self.final_dict[family_template[0]]:
                    self.final_dict[family_template[0]][root_name] = []

                self.value_dict = self.final_dict[family_template[0]][root_name]
                return True
            return False
        else:
            self.value_dict = self.final_dict[family_template[0]]
            return True

    def kube_ingress_path(self, value):
        self.value_dict.append(self.labels['service_name'] + '_' + self.labels['namespace'])

    def kube_pod_spec_volumes_persistentvolumeclaims_info(self, value):
        self.value_dict.append(self.labels['persistentvolumeclaim'] + '_' + self.labels['namespace'])

    def fetch_label_metrics(self):
        self.value_dict.append({
            value: self.labels[key] for key, value in self.families[self.family_name][3].items()
        })
