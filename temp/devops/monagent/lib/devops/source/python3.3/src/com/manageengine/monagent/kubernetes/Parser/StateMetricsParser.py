import traceback
from abc import abstractmethod

from com.manageengine.monagent.kubernetes.KubeUtil import curl_api_without_token, curl_api_with_token
from prometheus_client.parser import text_string_to_metric_families


class PrometheusParser:
    def __init__(self, url):
        self.url = url
        self.labels = None
        self.final_dict = {}
        self.value_dict = {}
        self.family_name = None
        self.custom_parsers_family_names = {}
        self.families = {}
        self.token_needed = False

        """
        self.families contains dict of families where each dict contains one list for parsing
        self.families = {
            'family_name': [JSON node name, [list of labels for root_name], Metric Name, {metrics from labels}]
        }
        
        sample one:
            self.families = {
                'kube_pod_phase': ['Pods', ['name', 'namespace'], 'Ph', {'phase': 'Ph', 'name': 'Na'}]
            } 
        """

    def get_data(self):
        status, response = curl_api_without_token(self.url) if not self.token_needed else curl_api_with_token(self.url, False)
        if status == 200:
            self.parse_families(text_string_to_metric_families(response))
        else:
            self.final_dict['DCErrors'] = {
                'exporter': {status: response}
            }
        return self.final_dict

    def parse_families(self, families):
        for family in families:
            if family.name in self.families:
                self.family_name = family.name
                if self.families[self.family_name][0] not in self.final_dict:
                    self.final_dict[self.families[self.family_name][0]] = {}
                self.parse_samples(family.samples)

    def parse_samples(self, samples):
        try:
            for sample in samples:
                self.labels = sample.labels

                if self.init_value_dict():
                    if self.families[self.family_name][3]:
                        self.fetch_label_metrics()

                    if self.family_name in self.custom_parsers_family_names:
                        getattr(self, self.family_name)(sample)
                    elif self.families[self.family_name][2]:
                        self.value_dict[self.families[self.family_name][2]] = sample.value
        except Exception:
            traceback.print_exc()

    def get_root_name(self, keys):
        return_str = []
        for key in keys:
            if not self.labels[key]:
                return None
            return_str.append(self.labels[key])
        return "_".join(return_str)

    @abstractmethod
    def init_value_dict(self):
        family_template = self.families[self.family_name]
        if family_template[1]:
            root_name = self.get_root_name(family_template[1])

            if root_name:
                if root_name not in self.final_dict[family_template[0]]:
                    self.final_dict[family_template[0]][root_name] = {}

                self.value_dict = self.final_dict[family_template[0]][root_name]
                return True
            return False
        else:
            self.value_dict = self.final_dict[family_template[0]]
            return True

    def fetch_label_metrics(self):
        for key, value in self.families[self.family_name][3].items():
            self.value_dict[value] = self.labels[key]
