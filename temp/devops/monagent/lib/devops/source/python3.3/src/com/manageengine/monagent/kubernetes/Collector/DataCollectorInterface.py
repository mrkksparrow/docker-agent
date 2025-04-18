'''
@author: bharath.veerakumar

Created on Feb 20 2023
'''


import sys
import traceback
import time
import copy
from itertools import islice
from com.manageengine.monagent.kubernetes import KubeUtil, KubeGlobal
from com.manageengine.monagent.kubernetes.ClusterAgent import ClusterAgentUtil
from com.manageengine.monagent.kubernetes.KubeUtil import exception_handler
from com.manageengine.monagent.kubernetes.Logging import KubeLogger as AgentLogger
from abc import abstractmethod
from concurrent.futures import ThreadPoolExecutor, as_completed



'''
Extend this class for k8s Data Collections
(extended it for NPCDataCollector, ConfDataCollector, EventCollector, ResourceDependency, ClusterMetricsAggregator, GuidanceMetrics, SidecarNPCCollector)
'''

class DataCollector:
    def __init__(self, dc_requisites_obj):
        self.dc_requisites_obj = dc_requisites_obj
        self.ksm_data = None
        self.final_splitted_data = []
        self.final_json = {}
        self.is_conf_dc = False

    # This method is for strategies to be followed by normal agent to fetch the respective data irrespective
    # of the cluster agent availability
    @abstractmethod
    def collect_data(self):
        pass

    # This method is for fetching the respective data from cluster agent to serve the normal agent
    @abstractmethod
    def get_data_for_cluster_agent(self, req_params=None):
        self.collect_data()
        return self.final_json

    def execute_dc_tasks(self):
        if KubeUtil.is_eligible_to_execute(self.dc_requisites_obj.dc_name, KubeGlobal.DC_START_TIME) or self.dc_requisites_obj.on_demand_exec:
            if self.dc_requisites_obj.perf_agent_tasks:
                if not self.check_eligibility_for_perf_agent_tasks():
                    return []
                AgentLogger.console_logger.info("Executing perf agent tasks {}".format(self.dc_requisites_obj.dc_name))

            if self.dc_requisites_obj.dependent_classes:
                if self.dc_requisites_obj.parallel_execution_needed:
                    self.execute_parallely()
                else:
                    self.final_json = self.initiate_dc()
                    for dc_obj in self.dc_requisites_obj.dependent_classes:
                        if KubeUtil.is_eligible_to_execute(dc_obj.dc_name, KubeGlobal.DC_START_TIME):
                            self.final_json = KubeUtil.MergeDataDictionaries(self.final_json, dc_obj.dc_class(dc_obj).initiate_dc())

                if self.dc_requisites_obj.split_data_required:
                    self.split_data()
                    if self.dc_requisites_obj.instant_push:
                        getattr(sys.modules['com.manageengine.monagent.kubernetes_monitoring.KubernetesExecutor'], 'write_data_to_file')(self.final_splitted_data)
                        return []
                    return self.final_splitted_data

                self.final_json["upload_dir_code"] = self.dc_requisites_obj.servlet_name
                return [self.final_json]
            else:
                return self.initiate_dc()
        return []

    def check_eligibility_for_perf_agent_tasks(self):
        task_name = self.dc_requisites_obj.dc_name + '_lut'
        status, response = KubeUtil.curl_api_with_token(KubeGlobal.apiEndpoint + KubeGlobal.s247ConfigMapPath)
        if status == 200:
            configmap_data = response['data']
            if task_name not in configmap_data or time.time() - float(configmap_data[task_name]) >= float(KubeGlobal.KUBE_GLOBAL_SETTINGS[self.dc_requisites_obj.dc_name]):
                data = {
                    'data': {
                        task_name: str(time.time())
                    },
                    'metadata': {
                        'resourceVersion': str(response['metadata']['resourceVersion'])
                    }
                }
                update_status, update_response = KubeUtil.update_s247_configmap(data)
                if update_status == 200:
                    return True
                elif update_status == 409:
                    self.check_eligibility_for_perf_agent_tasks()
        return False

    def execute_parallely(self):
        final_json = {}
        with ThreadPoolExecutor(max_workers=2) as exe:
            futures = [exe.submit(self.initiate_dc)]

            for obj in self.dc_requisites_obj.dependent_classes:
                if KubeUtil.is_eligible_to_execute(obj.dc_name, KubeGlobal.DC_START_TIME):
                    futures.append(
                        exe.submit(
                            obj.dc_class(obj).initiate_dc
                        )
                    )

            for future in as_completed(futures):
                final_json = KubeUtil.MergeDataDictionaries(final_json, future.result())

        self.final_json = final_json

    def initiate_dc(self):
        try:
            dc_start = time.time()
            self.get_from_cluster_agent() if self.dc_requisites_obj.use_cluster_agent else self.collect_data()

            if self.dc_requisites_obj.dc_type_needed:
                self.is_conf_dc = KubeUtil.is_eligible_to_execute(self.dc_requisites_obj.dc_name + "_" + "discovery", KubeGlobal.DC_START_TIME)

            if self.dc_requisites_obj.id_mapping_needed:
                self.map_id()

            if self.dc_requisites_obj.termination_needed and self.is_conf_dc:
                self.execute_termination_task()

            if self.dc_requisites_obj.split_data_required and not self.dc_requisites_obj.dependent_classes:
                self.split_data()
                time_taken = time.time() - dc_start
                KubeGlobal.NODE_AGENT_STATS[self.dc_requisites_obj.dc_name] = time_taken
                AgentLogger.log(AgentLogger.KUBERNETES, "***** Time taken for DC-{} {} ******\n".format(self.dc_requisites_obj.dc_name, time_taken))
                if self.dc_requisites_obj.instant_push:
                    getattr(sys.modules['com.manageengine.monagent.kubernetes_monitoring.KubernetesExecutor'], 'write_data_to_file')(self.final_splitted_data)
                    return []
                return self.final_splitted_data

            time_taken = time.time() - dc_start
            KubeGlobal.NODE_AGENT_STATS[self.dc_requisites_obj.dc_name] = time_taken
            AgentLogger.log(AgentLogger.KUBERNETES, "***** Time taken for DC-{} {} ******\n".format(self.dc_requisites_obj.dc_name, time_taken))
        except Exception:
            traceback.print_exc()
        return self.final_json

    @abstractmethod
    def get_from_cluster_agent(self):
        if KubeGlobal.CLUSTER_AGENT_STATS['cluster_agent_status']:
            data_from_ca = ClusterAgentUtil.get_ca_parsed_data(self.dc_requisites_obj.dc_name, self.get_cluster_agent_request_params(), method_type=self.dc_requisites_obj.ca_request_type)
            if data_from_ca is not None:
                self.final_json = data_from_ca
                return True
        self.collect_data()

    @abstractmethod
    def get_cluster_agent_request_params(self):
        return None

    @exception_handler
    def map_id(self):
        for grp_name, grp_value in self.final_json.items():
            if grp_name in KubeGlobal.API_ENDPOINT_RES_NAME_MAP:
                grp_ids = KubeGlobal.kubeIds.get(grp_name, {})
                for res_name, res_value in grp_value.items():
                    if res_name in grp_ids:
                        res_value['id'] = grp_ids[res_name].get('id')

                        for cont_name, cont_value in res_value.get("Cont", {}).items():
                            cont_value['id'] = grp_ids[res_name].get('Cont', {}).get(cont_name, {}).get('id')

    def execute_termination_task(self):
        with ThreadPoolExecutor(max_workers=4) as exe:
            if KubeGlobal.kubeIds:
                for group_type, group_value in KubeGlobal.kubeIds.items():
                    if group_type not in KubeGlobal.TERMINATION_NOT_SUPPORTED_GRPS:
                        url = KubeGlobal.apiEndpoint + KubeGlobal.API_ENDPOINT_RES_NAME_MAP[group_type] + '&fieldSelector=metadata.name={}'
                        is_namespaced = group_type not in KubeGlobal.NO_NS_UNIQUNESS_TYPES
                        if is_namespaced:
                            url += ',metadata.namespace={}'
                        exe.submit(self.mark_deleted_data, group_type, group_value, is_namespaced, url)

    @exception_handler
    def mark_deleted_data(self, group_type, group_value, is_namespaced, url):
        termination_start_time = time.time()
        for res_name, res_val in group_value.items():
            if group_type not in self.final_json or res_name not in self.final_json[group_type]:
                name, ns = res_name.split("_") if is_namespaced else (res_name, None)
                status, resp = KubeUtil.curl_api_with_token(url.format(name, ns) if is_namespaced else url.format(name))
                if status == 200 and len(resp.get("items", [])) == 0:
                    self.final_json[group_type] = self.final_json.get(group_type, {})
                    self.final_json[group_type][res_name] = res_val
                    self.final_json[group_type][res_name]["deleted"] = "true"

        AgentLogger.log(AgentLogger.KUBERNETES, "****** Time taken for finding termination for {}, {} ******".format(group_type, time.time() - termination_start_time))

    @exception_handler
    @abstractmethod
    def split_data(self):
        prevChildDict = {}
        finalFileDict = {}
        currPrevCount = 0
        splitNumber = 0

        chunkSize = self.dc_requisites_obj.child_write_count
        ct = int(round(time.time()*1000))

        pushFlag = False
        for k, v in self.final_json.items():
            if v and (type(v) != dict or k == "kubernetes"):
                # v["cluster_agent"] = KubeGlobal.CLUSTER_AGENT_STATS
                prevChildDict[k] = v
                continue

            for v1 in KubeUtil.dict_chunks(v, chunkSize):
                vLen = len(v1)
                if currPrevCount + vLen == chunkSize:
                    finalFileDict = copy.deepcopy(prevChildDict)
                    finalFileDict[k] = finalFileDict.get(k, {})
                    finalFileDict[k].update(v1)
                    KubeUtil.clear_and_init_dict(prevChildDict)
                    currPrevCount = 0
                    pushFlag = True
                elif currPrevCount + vLen < chunkSize:
                    prevChildDict[k] = prevChildDict.get(k, {})
                    prevChildDict[k].update(v1)
                    currPrevCount += vLen
                else:
                    if k not in prevChildDict: prevChildDict[k] = {}
                    prevChildDict[k].update(dict(islice(v1.items(), chunkSize - currPrevCount)))
                    finalFileDict = copy.deepcopy(prevChildDict)
                    KubeUtil.clear_and_init_dict(prevChildDict)
                    prevChildDict[k] = dict(islice(v1.items(), chunkSize - currPrevCount, vLen))
                    currPrevCount = currPrevCount + vLen - chunkSize
                    pushFlag = True

                if pushFlag:
                    pushFlag = False
                    splitNumber += 1
                    self.push_to_file_list(finalFileDict, ct)

        if currPrevCount > 0 or "kubernetes" in prevChildDict:
            splitNumber += 1
            self.push_to_file_list(prevChildDict, ct)

            AgentLogger.log(AgentLogger.KUBERNETES, 'last zip count - {0}'.format(splitNumber))

    def push_to_file_list(self, file_data, ct):
        file_data["ct"] = ct
        file_data["upload_dir_code"] = self.dc_requisites_obj.servlet_name

        if self.dc_requisites_obj.dc_type_needed:
            file_data["perf"] = "false" if self.is_conf_dc else "true"

        self.final_splitted_data.append(copy.deepcopy(file_data))
        KubeUtil.clear_and_init_dict(file_data)


class DCRequisites:
    def __init__(self):
        self.node_base_ksm_needed = False
        self.child_write_count = 500
        self.servlet_name = "003"
        self.termination_needed = False
        self.dc_type_needed = False
        self.dc_name = "DataCollector"
        self.dc_class = None
        self.split_data_required = False
        self.dependent_classes = []
        self.use_cluster_agent = False
        self.id_mapping_needed = False
        self.workloads_aggregation_needed = True
        self.is_sidecar_agent = False
        self.is_pre_parsing_needed = False
        self.parallel_execution_needed = False
        self.perf_agent_tasks = False
        self.instant_push = False
        self.ca_request_type = "GET"
        self.on_demand_exec = False

    def set_node_base_ksm_needed(self, boolean):
        self.node_base_ksm_needed = boolean

    def set_child_write_count(self, count):
        self.child_write_count = count

    def set_servlet_name(self, servlet):
        self.servlet_name = servlet

    def set_termination_needed(self, boolean):
        self.termination_needed = boolean

    def set_dc_type_needed(self, boolean):
        self.dc_type_needed = boolean

    def set_dc_name(self, name):
        self.dc_name = name

    def set_dc_class(self, class_name):
        self.dc_class = class_name

    def set_split_data_required(self, boolean):
        self.split_data_required = boolean

    def set_child_task_classes(self, requisites_objs):
        self.dependent_classes = requisites_objs

    def get_from_cluster_agent(self, boolean):
        KubeGlobal.CLUSTER_AGENT_STATS[self.dc_name] = {}
        KubeGlobal.CLUSTER_AGENT_URL_DATA_TYPE_MAP[self.dc_name] = '/pd/get_dc_json/' + self.dc_name
        self.use_cluster_agent = boolean

    def set_id_mapping_needed(self, boolean):
        self.id_mapping_needed = boolean

    def set_workloads_aggregation_needed(self, boolean):
        self.workloads_aggregation_needed = boolean

    def set_is_sidecar_agent(self, boolean):
        self.is_sidecar_agent = boolean

    def set_is_pre_parsing_needed(self, boolean):
        self.is_pre_parsing_needed = boolean

    def set_is_perf_agent_tasks(self, boolean):
        KubeGlobal.S247_CONFIGMAP_SYSTEM_KEYS.append(self.dc_name + '_lut')
        self.perf_agent_tasks = boolean

    def set_instant_push_needed(self, boolean):
        self.instant_push = boolean

    def set_cluster_req_type(self, request_type):
        self.ca_request_type = request_type

    def set_on_demand_exec_needed(self, boolean):
        self.on_demand_exec = boolean

