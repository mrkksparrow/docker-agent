'''
@author: bharath.veerakumar

Created on Feb 20 2023
'''


from com.manageengine.monagent.kubernetes.Logging import KubeLogger as AgentLogger
from com.manageengine.monagent.kubernetes import KubeUtil
from com.manageengine.monagent.kubernetes import KubeGlobal
from com.manageengine.monagent.kubernetes.ClusterAgent import ClusterAgentUtil
from com.manageengine.monagent.kubernetes.Collector.DataCollectorInterface import DataCollector
from com.manageengine.monagent.kubernetes.Parser.PrometheusParser.NPCStateMetricsParser import NPCStateMetrics
from abc import abstractmethod
import traceback
import json
import math
import time
from concurrent.futures import ThreadPoolExecutor

PHASE_METRIC_NAME = {
    'Running': 'KPR',
    'Pending': 'KPP',
    'Succeeded': 'KPS',
    'Failed': 'KPF',
    'Unknown': 'KPU'
}


class ClusterMetricsAggregator(DataCollector):
    def __init__(self, dc_requisites_obj):
        super().__init__(dc_requisites_obj)
        self.cluster_aggregated_metrics = None
        self.final_json = None
        self.init_metrics_dict()
        self.service_selectors = {}
        self.rs_deploy_map = {}

    def collect_data(self):
        try:
            self.ksm_data = NPCStateMetrics().get_data()
            dc_start_time = time.time()

            KubeUtil.get_api_data_by_limit(
                KubeGlobal.apiEndpoint + KubeGlobal.API_ENDPOINT_RES_NAME_MAP['Services'], self.hash_service_selectors, self.service_selectors
            )

            with ThreadPoolExecutor(max_workers=math.ceil(len(self.ksm_data["Nodes"]) / 10)) as exe:
                for node_name in self.ksm_data["Nodes"].keys():
                    exe.submit(self.aggregate_metrics, node_name)

            self.aggregate_deployment_perf_values()
            self.calculate_cluster_capacity()
            self.aggregate_container_metrics()
            self.final_json["kubernetes"]["CMA_DC_TIME"] = time.time() - dc_start_time
        except Exception:
            traceback.print_exc()

    def get_data_for_cluster_agent(self, req_params=None):
        dc_start_time = time.time()
        self.ksm_data = ClusterAgentUtil.get_parsed_data_for_ca("npc_ksm")
        self.service_selectors = ClusterAgentUtil.get_parsed_data_for_ca("service_pod_map")
        self.rs_deploy_map = ClusterAgentUtil.get_parsed_data_for_ca("rs_deploy_map")

        for node_name, kubelet_data in ClusterAgentUtil.get_parsed_data_for_ca("all_kubelet").items():
            self.aggregate_metrics(node_name, kubelet_data)

        self.aggregate_deployment_perf_values()
        self.calculate_cluster_capacity()
        self.aggregate_container_metrics()
        self.final_json["kubernetes"]["CMA_DC_TIME"] = time.time() - dc_start_time
        return self.final_json

    def aggregate_metrics(self, node_name, kubelet_data=None):
        try:
            if not kubelet_data:
                kubelet_data = KubeUtil.curl_api_with_token(KubeGlobal.apiEndpoint + '/api/v1/nodes/{}/proxy/stats/summary'.format(node_name))[1]

            self.aggregate_cluster_metrics(kubelet_data["node"], self.ksm_data["Nodes"][node_name])

            if self.dc_requisites_obj.workloads_aggregation_needed:
                self.aggregate_workload_metrics(kubelet_data["pods"], self.ksm_data["Pods"])
                return

            # no need to call this method if aggregate_workload_metrics method has been called
            self.calculate_reserved_metrics()
        except Exception as e:
            AgentLogger.log(AgentLogger.KUBERNETES, "Exception -> aggregate_metrics -> {}".format(e))
            traceback.print_exc()

    def aggregate_cluster_metrics(self, node_data, kube_state_data):
        try:
            # cpu
            self.cluster_aggregated_metrics['totalCoresUse'] += float(node_data["cpu"]["usageNanoCores"]) / 1000000000
            self.cluster_aggregated_metrics['totalCapaCores'] += float(kube_state_data["KNSCCC"])
            self.cluster_aggregated_metrics['cpuAllocatable'] += float(kube_state_data["KNSACC"])

            # mem
            self.cluster_aggregated_metrics['totalMemUse'] += float(node_data["memory"]["workingSetBytes"]) / 1073741824
            self.cluster_aggregated_metrics['memCapacity'] += float(kube_state_data["KNSCMB"]) / 1073741824
            self.cluster_aggregated_metrics['memAllocatable'] += float(kube_state_data["KNSAMB"]) / 1073741824

            # disk
            if "fs" in node_data:
                self.cluster_aggregated_metrics['avaiStorage'] += float(node_data["fs"]["capacityBytes"]) / 1073741824
                self.cluster_aggregated_metrics['usedStorage'] += float(node_data["fs"]["usedBytes"]) / 1073741824

            # pods
            self.cluster_aggregated_metrics['podsAllocatable'] += float(kube_state_data["KNSAP"])

            # node dashboard metrics
            # need to remove this. we have this metrics for cluster dashboard as well
            self.final_json['kubernetes']['KNTC'] += kube_state_data['KNSCCC']
            self.final_json['kubernetes']['KNAC'] += kube_state_data['KNSACC']
            self.final_json['kubernetes']['KNTM'] += int(kube_state_data['KNSCMG'])
            # self.final_json['kubernetes']['KNAM'] += kube_state_data['KNSAMG']
            self.final_json['kubernetes']['KNPA'] += kube_state_data['KNSAP']
        except Exception as e:
            AgentLogger.log(AgentLogger.KUBERNETES, "Exception -> aggregate_cluster_metrics -> {}".format(e))
            traceback.print_exc()

    def calculate_reserved_metrics(self):
        for pod_state_data in self.ksm_data["Pods"]:
            self.cluster_aggregated_metrics["KCCR"] += ((float(pod_state_data["PRMB"]) if "PRMB" in pod_state_data else 0) / 1000)
            self.cluster_aggregated_metrics["KCMR"] += ((float(pod_state_data["PRRCC"]) if "PRRCC" in pod_state_data else 0) / 1024)

    @abstractmethod
    def get_pod_name_namespace(self, pod_data):
        ns = pod_data['podRef']['namespace']
        return pod_data['podRef']['name'] + '_' + ns, ns

    @abstractmethod
    def construct_pod_perf_value(self, pod, pod_state_data, pod_name):
        return {
            'cpu_used': float(pod["cpu"]["usageNanoCores"]) / 1000000,
            'mem_used': float(pod["memory"]["workingSetBytes"]) / 1048576,
            'rss_mem_used': float(pod["memory"]["rssBytes"]) / 1048576,
            'mem_req': float(pod_state_data["PRMB"]) if "PRMB" in pod_state_data else 0,
            'cpu_req': float(pod_state_data["PRRCC"]) if "PRRCC" in pod_state_data else 0,
            'mem_limit': float(pod_state_data["PRLMB"]) if "PRLMB" in pod_state_data else 0,
            'cpu_limit': float(pod_state_data["PRLCC"]) if "PRLCC" in pod_state_data else 0,
            'rc': float(pod_state_data['RC']) if 'RC' in pod_state_data else 0,
            'rx': KubeUtil.get_counter_value(pod_name+"_CMA_RX", float(pod["network"].get("rxBytes", 0)) / 1024, True),
            'tx': KubeUtil.get_counter_value(pod_name+"_CMA_TX", float(pod["network"].get("txBytes", 0)) / 1024, True)
        }

    @abstractmethod
    def construct_container_perf_value(self, pod, pod_state_data, pod_name):
        perf_values = {
            'cpu_used': 0,
            'mem_used': 0,
            'rss_mem_used': 0,
            'mem_req': 0,
            'cpu_req': 0,
            'mem_limit': 0,
            'cpu_limit': 0,
            'rc': 0,
            'rx': 0,
            'tx': 0
        }
        try:
            for container in pod['containers']:
                perf_values['cpu_used'] += float(container["cpu"].get("usageNanoCores", 0)) / 1000000
                perf_values['mem_used'] += float(container["memory"].get("workingSetBytes", 0)) / 1048576
                perf_values['rss_mem_used'] += float(container["memory"].get("rssBytes", 0)) / 1048576
                perf_values['cpu_used'] += float(container["cpu"].get("usageNanoCores", 0)) / 1000000
                perf_values['rx'] += KubeUtil.get_counter_value(pod_name+"_CMA_RX", float(container.get("network", {}).get("rxBytes", 0)) / 1024, True)
                perf_values['tx'] += KubeUtil.get_counter_value(pod_name+"_CMA_TX", float(container.get("network", {}).get("txBytes", 0)) / 1024, True)

            perf_values['mem_req'] = float(pod_state_data["PRMB"]) if "PRMB" in pod_state_data else 0
            perf_values['cpu_req'] = float(pod_state_data["PRRCC"]) if "PRRCC" in pod_state_data else 0
            perf_values['mem_limit'] = float(pod_state_data["PRLMB"]) if "PRLMB" in pod_state_data else 0
            perf_values['cpu_limit'] = float(pod_state_data["PRLCC"]) if "PRLCC" in pod_state_data else 0
            perf_values['rc'] = float(pod_state_data['RC']) if 'RC' in pod_state_data else 0
        except Exception:
            traceback.print_exc()
        return perf_values

    def aggregate_workload_metrics(self, pods_data, kube_state_data):
        try:
            is_trace_called = 0
            for pod in pods_data:
                try:
                    pod_name, namespace = ((pod['podRef']['name'] + '_' + pod['podRef']['namespace'], pod['podRef']['namespace']) if 'podRef' in pod else (pod['metadata']['name'] + '_' + pod['metadata']['namespace'], pod['metadata']['namespace']))
                    service_name, pod_state_data = self.service_selectors.get(pod_name), kube_state_data[pod_name]

                    perf_value_dict = self.construct_pod_perf_value(pod, pod_state_data, pod_name) if not KubeGlobal.KUBELET_ERROR else self.construct_container_perf_value(pod, pod_state_data, pod_name)

                    # aggregating cluster reserved metrics
                    self.cluster_aggregated_metrics["KCCR"] += (perf_value_dict['cpu_req'] / 1000)  # cpu reserved
                    self.cluster_aggregated_metrics["KCMR"] += (perf_value_dict['mem_req'] / 1024)  # memory reserved
                    self.cluster_aggregated_metrics['CC'] += len(pod_state_data['Cont'])

                    # namespace performance & ns, cluster level phase metrics aggregation
                    self.aggregate_perf_values_to_owner_dict('Namespaces', namespace, perf_value_dict)
                    self.final_json['Namespaces'][namespace][pod_state_data["Ph"]] = self.final_json['Namespaces'][namespace].get(pod_state_data["Ph"], 0) + 1
                    self.final_json['kubernetes'][PHASE_METRIC_NAME[pod_state_data["Ph"]]] += 1
                    self.final_json['Namespaces'][namespace]["PC"] = self.final_json['Namespaces'][namespace].get("PC", 0) + 1

                    # service performance metrics aggregation
                    if service_name:
                        self.aggregate_perf_values_to_owner_dict('Services', service_name, perf_value_dict)

                    # workloads level metrics aggregation
                    if pod_state_data["owner_kind"] in ['DaemonSet', 'ReplicaSet', 'StatefulSet']:
                        self.aggregate_perf_values_to_owner_dict(
                            pod_state_data["owner_kind"]+"s",
                            pod_state_data["owner_name"]+"_"+namespace,
                            perf_value_dict
                        )

                    # pvc utilization metric
                    self.get_pvc_utilization_metric(pod.get("volume", []))
                except Exception:
                    if not is_trace_called:
                        traceback.print_exc()
                        is_trace_called = 1
        except Exception as e:
            AgentLogger.log(AgentLogger.KUBERNETES, "Exception -> aggregate_workload_metrics -> {}".format(e))
            traceback.print_exc()

    def get_pvc_utilization_metric(self, volume_list):
        for volume in volume_list:
            if "pvcRef" in volume:
                self.final_json["PersistentVolumeClaim"][volume["pvcRef"]["name"] + "_" + volume["pvcRef"]["namespace"]] = {
                    "used": volume["usedBytes"],
                    "available": volume["availableBytes"],
                    "capacity": volume["capacityBytes"],
                    "used_perc": volume['usedBytes'] / volume["capacityBytes"] * 100,
                    "available_perc": volume["availableBytes"] / volume["capacityBytes"] * 100
                }

    def calculate_cluster_capacity(self):
        try:
            self.final_json['kubernetes']["cpu_used"] = self.cluster_aggregated_metrics['totalCoresUse']
            self.final_json['kubernetes']["cpu_capacity"] = self.cluster_aggregated_metrics['totalCapaCores']
            self.final_json['kubernetes']["cpu_allocatable"] = self.cluster_aggregated_metrics['cpuAllocatable']
            self.final_json['kubernetes']["cpu_reserved"] = self.cluster_aggregated_metrics["KCCR"]

            self.final_json['kubernetes']["mem_used"] = self.cluster_aggregated_metrics['totalMemUse']
            self.final_json['kubernetes']["mem_capacity"] = self.cluster_aggregated_metrics['memCapacity']
            self.final_json['kubernetes']["mem_allocatable"] = self.cluster_aggregated_metrics['memAllocatable']
            self.final_json['kubernetes']["mem_reserved"] = self.cluster_aggregated_metrics["KCMR"]

            self.final_json['kubernetes']["disk_used"] = self.cluster_aggregated_metrics['usedStorage']
            self.final_json['kubernetes']["disk_capacity"] = self.cluster_aggregated_metrics['avaiStorage']

            self.final_json['kubernetes']["pods_perc"] = (KubeUtil.get_count_metric(KubeGlobal.apiEndpoint + KubeGlobal.API_ENDPOINT_RES_NAME_MAP['Pods'] + '?limit=1') / self.cluster_aggregated_metrics['podsAllocatable']) * 100

            self.final_json['kubernetes']["cpu_perc"] = (self.final_json['kubernetes']["cpu_used"] / self.final_json['kubernetes']["cpu_capacity"]) * 100
            self.final_json['kubernetes']["mem_perc"] = (self.final_json['kubernetes']["mem_used"] / self.final_json['kubernetes']["mem_capacity"]) * 100
            self.final_json['kubernetes']["res_cpu_perc"] = (self.final_json['kubernetes']["cpu_reserved"] / self.final_json['kubernetes']["cpu_allocatable"]) * 100
            self.final_json['kubernetes']["res_mem_perc"] = (self.final_json['kubernetes']["mem_reserved"] / self.final_json['kubernetes']["mem_allocatable"]) * 100
            self.final_json['kubernetes']['CC'] = self.cluster_aggregated_metrics['CC']
            self.final_json['kubernetes']['KNNR'] = len(self.ksm_data['Nodes'])

            if self.cluster_aggregated_metrics['avaiStorage']:
                self.final_json['kubernetes']["disk_perc"] = (self.cluster_aggregated_metrics['usedStorage'] / self.cluster_aggregated_metrics['avaiStorage']) * 100

            AgentLogger.log(AgentLogger.DA, "cluster metrics {}".format(json.dumps(self.final_json)))
        except Exception as e:
            AgentLogger.log(AgentLogger.KUBERNETES, "Exception -> calculate_cluster_capacity -> {}".format(e))
            traceback.print_exc()

    def hash_service_selectors(self, service_data, lookup_dict):
        try:
            for val in service_data['items']:
                try:
                    name = val['metadata']['name']
                    ns = val['metadata']['namespace']
                    svc_name = name + "_" + ns
                    sel = val['spec']['selector']
                    match_labels = []
                    for key, value in sel.items():
                        match_labels.append("{}%3D{}".format(key, value))

                    status, api_resp = KubeUtil.curl_api_with_token(KubeGlobal.apiEndpoint + "/api/v1/namespaces/{}/pods?labelSelector={}".format(ns, ",".join(match_labels)))
                    if status == 200:
                        for pod_value in api_resp.get("items", []):
                            lookup_dict[pod_value['metadata']['name'] + "_" + ns] = svc_name
                except Exception:
                    continue
        except Exception as e:
            AgentLogger.log(AgentLogger.KUBERNETES, "Exception -> hash_service_selectors -> {}".format(e))

    def aggregate_deployment_perf_values(self):
        self.final_json["Deployments"] = {}
        for rs_name, rs_value in self.final_json.get("ReplicaSets", {}).items():
            if self.rs_deploy_map:
                deploy_name = self.rs_deploy_map[rs_name][0]['owner_name']+'_'+rs_name.split('_')[1]
            else:
                deploy_name = KubeUtil.find_replicaset_owner(rs_name)

            if deploy_name:
                self.final_json["Deployments"][deploy_name] = rs_value
        self.final_json.pop("ReplicaSets", None)

    def aggregate_perf_values_to_owner_dict(self, owner_kind, owner_name, perf_value_dict):
        try:
            if owner_name not in self.final_json[owner_kind]:
                self.init_final_dict_for_workloads(owner_kind, owner_name)
            self.add_perf_values_to_dict(owner_kind, owner_name, self.final_json, perf_value_dict)
        except Exception as e:
            AgentLogger.log(AgentLogger.KUBERNETES, "Exception -> aggregate_ns_perf_values -> {}".format(e))
            traceback.print_exc()

    def init_final_dict_for_workloads(self, owner_kind, owner_name):
        self.final_json[owner_kind][owner_name] = {
             'cpu_used': 0,
             'mem_used': 0,
             'rss_mem_used': 0,
             'cpu_req': 0,
             'mem_req': 0,
             'cpu_limit': 0,
             'mem_limit': 0,
             'rx': 0,
             'tx': 0,
             'rc': 0
        }

    def aggregate_container_metrics(self):
        if 'kubernetes' in self.ksm_data:
            self.final_json["kubernetes"]["CTR_C"] = self.ksm_data['kubernetes'].pop("CTR_Completed", 0)
            self.final_json["kubernetes"]["CTR_OOM"] = self.ksm_data['kubernetes'].pop("CTR_OOMKilled", 0)
            self.final_json["kubernetes"]["CRT_E"] = self.ksm_data['kubernetes'].pop("CTR_Error", 0)
            self.final_json["kubernetes"]["CTR_CCR"] = self.ksm_data['kubernetes'].pop("CTR_ContainerCannotRun", 0)
            self.final_json["kubernetes"]["CTR_DE"] = self.ksm_data['kubernetes'].pop("CTR_DeadlineExceeded", 0)
            self.final_json["kubernetes"]["CTR_E"] = self.ksm_data['kubernetes'].pop("CTR_Evicted", 0)
            self.final_json["kubernetes"]["CWR_CC"] = self.ksm_data['kubernetes'].pop("CWR_ContainerCreating", 0)
            self.final_json["kubernetes"]["CWR_CLP"] = self.ksm_data['kubernetes'].pop("CWR_CrashLoopBackOff", 0)
            self.final_json["kubernetes"]["CWR_CE"] = self.ksm_data['kubernetes'].pop("CWR_CreateContainerConfigError", 0)
            self.final_json["kubernetes"]["CWR_EI"] = self.ksm_data['kubernetes'].pop("CWR_ErrImagePull", 0)
            self.final_json["kubernetes"]["CWR_IP"] = self.ksm_data['kubernetes'].pop("CWR_ImagePullBackOff", 0)
            self.final_json["kubernetes"]["CWR_CCE"] = self.ksm_data['kubernetes'].pop("CWR_CreateContainerError", 0)
            self.final_json["kubernetes"]["CWR_II"] = self.ksm_data['kubernetes'].pop("CWR_InvalidImageName", 0)
            self.final_json['kubernetes']['KPCST'] = self.ksm_data['kubernetes'].pop('KPCST', 0)
            self.final_json['kubernetes']['KPCSR'] = self.ksm_data['kubernetes'].pop('KPCSR', 0)
            self.final_json['kubernetes']['KPCSW'] = self.ksm_data['kubernetes'].pop('KPCSW', 0)

    def add_perf_values_to_dict(self, owner_kind, owner_name, metric_dict, perf_values):
        try:
            owner_dict = metric_dict[owner_kind][owner_name]
            owner_dict["cpu_used"] += perf_values['cpu_used']
            owner_dict["mem_used"] += perf_values['mem_used']
            owner_dict["rss_mem_used"] += perf_values['rss_mem_used']
            owner_dict["mem_req"] += perf_values['mem_req']
            owner_dict["cpu_req"] += perf_values['cpu_req']
            owner_dict["cpu_limit"] += perf_values['cpu_limit']
            owner_dict["mem_limit"] += perf_values['mem_limit']
            owner_dict["rx"] += perf_values['rx']
            owner_dict["tx"] += perf_values['tx']
            owner_dict['rc'] += perf_values['rc']
        except Exception as e:
            AgentLogger.log(AgentLogger.KUBERNETES, "Exception -> add_perf_values_to_dict -> {}".format(e))
            traceback.print_exc()

    def init_metrics_dict(self):
        self.cluster_aggregated_metrics = {
            'totalCoresUse': 0,
            'totalCapaCores': 0,
            'cpuAllocatable': 0,
            'totalMemUse': 0,
            'memCapacity': 0,
            'memAllocatable': 0,
            'avaiStorage': 0,
            'usedStorage': 0,
            'podsAllocatable': 0,
            'podsScheduled': 0,
            "KCCR": 0,
            "KCMR": 0,
            'CC': 0
        }

        if not self.dc_requisites_obj.workloads_aggregation_needed:
            self.final_json = {
                "kubernetes": {
                    "KNR": 0,
                    "KNNR": 0,
                    "KNTC": 0,
                    "KNAC": 0,
                    "KNTM": 0,
                    "KNAM": 0,
                    "KNPA": 0,
                    "KPR": 0,
                    "KPS": 0,
                    "KPP": 0,
                    "KPF": 0,
                    "KPU": 0
                }
            }
        else:
            self.final_json = {
                "PersistentVolumeClaim": {},
                "DaemonSets": {},
                "Deployments": {},
                "StatefulSets": {},
                "ReplicaSets": {},
                "Namespaces": {},
                "Services": {},
                "kubernetes": {
                    "KNR": 0,
                    "KNNR": 0,
                    "KNTC": 0,
                    "KNAC": 0,
                    "KNTM": 0,
                    "KNAM": 0,
                    "KNPA": 0,
                    "KPR": 0,
                    "KPS": 0,
                    "KPP": 0,
                    "KPF": 0,
                    "KPU": 0
                }
            }
