from abc import abstractmethod
from com.manageengine.monagent.kubernetes.KubeUtil import curl_api_with_token, getAge
from com.manageengine.monagent.kubernetes import KubeGlobal, KubeUtil
from com.manageengine.monagent.kubernetes.Logging import KubeLogger
import traceback
import copy
from datetime import datetime

try:
    import yaml
except Exception:
    pass


class JSONParser:
    def __init__(self, type=None):
        self.type = type
        self.final_dict = {}    # contains all the resources data as key: value pair
        self.value_dict = {}    # contains data for particular resource, used in iterating the raw value
        self.api_url = KubeGlobal.apiEndpoint + KubeGlobal.API_ENDPOINT_RES_NAME_MAP[type] if type else None
        self.raw_data = None
        self.is_namespaces = True
        self.fetch_with_limit = True
        self.certificate_verification = True
        self.metadata_needed = True
        self.paths_to_iterate = "items"
        self.cluster_level_metrics = {}
        self.registered_resource_key = copy.deepcopy(KubeGlobal.DISCOVERED_RESOURCE_CONFIG_STORAGE.get(type, {}))

    @abstractmethod
    def get_metadata(self):
        self.get_namespaces_resource_metadata() if self.is_namespaces else self.get_resource_metadata()

    @abstractmethod
    def get_perf_metrics(self):
        pass

    @abstractmethod
    def get_aggregated_metrics(self):
        pass

    @abstractmethod
    def get_discovery_data(self, response):
        for value in response[self.paths_to_iterate]:
            self.raw_data, self.value_dict = value, {}
            root_name = self.get_root_name()
            self.registered_resource_key.pop(root_name, None)

            if int(KubeUtil.getAgeInSec(self.get_2nd_path_value(['metadata', 'creationTimestamp']))) <= int(KubeGlobal.KUBE_INSTANT_DISCOVERY_SETTINGS[self.type]):
                self.get_metadata()
                self.get_perf_metrics()
                self.save_value_dict(root_name)
        self.get_termination_data()

    @abstractmethod
    def get_termination_data(self):
        if self.registered_resource_key:
            for terminated_resource in self.registered_resource_key:
                name = self.registered_resource_key[terminated_resource]['name'] if 'name' in self.registered_resource_key[terminated_resource] else self.registered_resource_key[terminated_resource]['Na']
                ns = self.registered_resource_key[terminated_resource].get("NS")

                status, response = KubeUtil.curl_api_with_token(
                    self.api_url + (
                        "&fieldSelector=metadata.name={}".format(name) if not self.is_namespaces else "&fieldSelector=metadata.name={},metadata.namespace={}".format(name, ns)
                    )
                )
                if status == 200 and not response.get("items", None):
                    self.final_dict[terminated_resource] = KubeGlobal.DISCOVERED_RESOURCE_CONFIG_STORAGE[self.type].pop(terminated_resource)
                    self.final_dict[terminated_resource]["deleted"] = "true"

    @abstractmethod
    def get_dc_data(self, response):
        try:
            for value in response[self.paths_to_iterate]:
                try:
                    self.raw_data, self.value_dict = value, {}
                    root_name = self.get_root_name()

                    if self.metadata_needed:
                        self.get_metadata()
                    self.get_perf_metrics()
                    self.get_aggregated_metrics()
                    self.save_value_dict(root_name)
                except Exception as e:
                    traceback.print_exc()
                    KubeLogger.log(KubeLogger.KUBERNETES, 'Exception in get_dc_data {}'.format(e))
        except Exception:
            traceback.print_exc()

    def parse_yaml_data(self, response):
        try:
            from com.manageengine.monagent.kubernetes.Collector.YAMLFetcher import SUCCEEDED_RESOURCES
            api_version = response['apiVersion']
            kind = response['kind'].split('List')[0]
            for value in response[self.paths_to_iterate]:
                self.raw_data = value
                root_name = self.get_root_name()
                kube_id = KubeGlobal.kubeIds.get(self.type, {}).get(root_name, {}).get('id')
                if kube_id:
                    rv = self.raw_data['metadata']['resourceVersion']
                    modified_timestamp = None
                    is_eligible = False
                    if root_name not in KubeGlobal.RESOURCE_VERSIONS[self.type]:
                        modified_timestamp = self.get_last_modified_time()[0]
                        is_eligible = True
                    # skipping the resource version check for nodes. Only sent for 1st time
                    elif KubeGlobal.RESOURCE_VERSIONS[self.type][root_name]['rv'] != rv and self.type != 'Nodes':
                        modified_timestamp, date_obj = self.get_last_modified_time()
                        if not date_obj:
                            is_eligible = True
                        elif date_obj > datetime.strptime(' '.join(KubeGlobal.RESOURCE_VERSIONS[self.type][root_name]['time'].split('T')).split('Z')[0]+'.0000', '%Y-%m-%d %H:%M:%S.%f'):
                            is_eligible = True

                    if is_eligible:
                        self.raw_data['metadata'].get('annotations', {}).pop('kubectl.kubernetes.io/last-applied-configuration', None)
                        self.raw_data.pop("status", None)
                        self.raw_data['apiVersion'] = api_version
                        self.raw_data['kind'] = kind
                        self.final_dict[root_name] = {
                            'id': kube_id,
                            'Version': modified_timestamp,
                            'rv': modified_timestamp
                        }
                        self.raw_data['metadata'].pop('managedFields', None)
                        self.final_dict[root_name]['yaml'] = yaml.dump(self.raw_data)
                        SUCCEEDED_RESOURCES.pop(kube_id, None)

                    if root_name not in KubeGlobal.RESOURCE_VERSIONS[self.type]:
                        KubeGlobal.RESOURCE_VERSIONS[self.type][root_name] = {}

                    KubeGlobal.RESOURCE_VERSIONS[self.type][root_name]['rv'] = rv
                    if modified_timestamp:
                        KubeGlobal.RESOURCE_VERSIONS[self.type][root_name]['time'] = modified_timestamp
        except Exception:
            traceback.print_exc()

    def get_last_modified_time(self):
        lmt = None
        try:
            timestamp = ""
            for update in self.raw_data['metadata']['managedFields']:
                if 'time' in update and update.get('manager', '') != 'kube-controller-manager' and update.get('subresource', '') != 'status' and 'f:status' not in update.get('fieldsV1', {}):
                    updated_time = datetime.strptime(' '.join(update['time'].split('T')).split('Z')[0]+'.0000', '%Y-%m-%d %H:%M:%S.%f')
                    if not lmt or updated_time > lmt:
                        lmt = updated_time
                        timestamp = update['time']
            if not timestamp:
                timestamp = self.raw_data['metadata']['creationTimestamp']
            return timestamp, lmt
        except Exception:
            traceback.print_exc()
            return self.raw_data['metadata']['creationTimestamp'], lmt

    @abstractmethod
    def save_value_dict(self, root_name):
        self.final_dict[root_name] = self.value_dict

    @abstractmethod
    def get_root_name(self):
        if not self.is_namespaces:
            return self.raw_data['metadata']['name']
        return self.raw_data['metadata']['name'] + '_' + self.raw_data['metadata']['namespace']

    def get_data(self, discovery=False, yaml=False):
        self.get_data_by_limit(discovery=discovery, yaml=yaml) if self.fetch_with_limit else self.get_data_without_limit()
        if self.cluster_level_metrics:
            self.final_dict["aggregated_metrics"] = self.cluster_level_metrics
        return self.final_dict

    def get_data_by_limit(self, discovery=False, yaml=False, continue_token=None):
        status, response = curl_api_with_token(self.api_url + (("&continue=" + continue_token) if continue_token else ""), self.certificate_verification)
        if status == 200 and response:
            if discovery:
                self.get_discovery_data(response)
            elif yaml:
                self.parse_yaml_data(response)
            else:
                self.get_dc_data(response)
            if 'continue' in response['metadata'] and response['metadata']['remainingItemCount'] > 0:
                self.get_data_by_limit(discovery=discovery, yaml=yaml, continue_token=response['metadata']['continue'])

    def get_data_without_limit(self):
        status, response = curl_api_with_token(self.api_url, self.certificate_verification)
        if status == 200 and response:
            self.get_dc_data(response)

    def get_namespaces_resource_metadata(self):
        self.value_dict = {
            "Na": self.raw_data['metadata']['name'],
            "NS": self.raw_data['metadata']['namespace'],
            "UID": self.raw_data['metadata']['uid'],
            "CT": self.raw_data['metadata']['creationTimestamp'],
            "rv": self.raw_data['metadata']['resourceVersion'],
            "age": getAge(self.raw_data['metadata']['creationTimestamp'], datetime.now())
        }

    def get_resource_metadata(self):
        self.value_dict = {
            "Na": self.raw_data['metadata']['name'],
            "UID": self.raw_data['metadata']['uid'],
            "CT": self.raw_data['metadata']['creationTimestamp'],
            "rv": self.raw_data['metadata']['resourceVersion'],
            "age": getAge(self.raw_data['metadata']['creationTimestamp'], datetime.now())
        }

    def aggregate_cluster_metrics(self, key_name, value):
        self.cluster_level_metrics[key_name] = self.cluster_level_metrics.get(key_name, 0) + value

    def get_1st_path_value(self, path, default_value=None):
        try:
            return self.raw_data[path[0]]
        except KeyError:
            return default_value

    def get_2nd_path_value(self, path, default_value=None):
        try:
            return self.raw_data[path[0]][path[1]]
        except KeyError:
            return default_value

    def get_3rd_path_value(self, path, default_value=None):
        try:
            return self.raw_data[path[0]][path[1]][path[2]]
        except KeyError:
            return default_value

    def get_4th_path_value(self, path, default_value=None):
        try:
            return self.raw_data[path[0]][path[1]][path[2]][path[3]]
        except KeyError:
            return default_value

    def get_5th_path_value(self, path, default_value=None):
        try:
            return self.raw_data[path[0]][path[1]][path[2]][path[3]][path[4]]
        except KeyError:
            return default_value
