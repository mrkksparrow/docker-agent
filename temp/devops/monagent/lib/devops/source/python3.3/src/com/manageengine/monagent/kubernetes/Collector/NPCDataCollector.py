'''
@author: bharath.veerakumar

Created on Feb 20 2023
'''
import json
import traceback

from com.manageengine.monagent.kubernetes import KubeUtil
from com.manageengine.monagent.kubernetes.KubeUtil import exception_handler
from com.manageengine.monagent.kubernetes import KubeGlobal
from com.manageengine.monagent.kubernetes.Collector.DataCollectorInterface import DataCollector
from com.manageengine.monagent.kubernetes.Parser.ParserFactory import get_json_parser, get_prometheus_parser
from com.manageengine.monagent.kubernetes.Logging import KubeLogger as AgentLogger
from abc import abstractmethod


class NPCDataCollector(DataCollector):
    def collect_data(self):
        self.merge_apis_data()
        # need to process all the resources individually, because to calculate percentage, capacity metrics from ksm & usage metrics from kubelet
        self.process_node_metrics()
        self.process_pod_metrics()

    @abstractmethod
    def merge_apis_data(self):
        # merging k8s api, ksm, kubelet & cadvisor apis data
        self.final_json = KubeUtil.MergeDataDictionaries(
            KubeUtil.MergeDataDictionaries(
                get_json_parser("KubeletMetrics")().get_data(),
                {
                    "Nodes": get_json_parser("Nodes")().get_data(),
                    "Pods": get_json_parser("Pods")().get_data()
                }
            ),
            get_prometheus_parser("CAdvisor")().get_data()
        )

    @exception_handler
    def process_node_metrics(self):
        node_data = self.final_json['Nodes'][KubeGlobal.KUBELET_NODE_NAME]
        node_data.update({
            'NCR': 0,
            'NCL': 0,
            'NMR': 0,
            'NML': 0,
            'throttled_sec': 0,
            'throttled_periods': 0,
            'total_periods': 0,
            'KNRCPI': 0,
            'KNPC': 0,
            'KNRC': 0
        })
        node_data["mem_perc"] = KubeUtil.calc_perc(node_data["WSB"], node_data["KNSCMB"])
        node_data["cpu_perc"] = KubeUtil.calc_perc(node_data["UNC"], int(node_data["KNSCCC"]) * 1000)
        node_data["alloc_mem_perc"] = KubeUtil.calc_perc(node_data["WSB"], node_data["KNSAMB"])
        node_data["alloc_cpu_perc"] = KubeUtil.calc_perc(node_data["UNC"], int(node_data["KNSACC"]) * 1000)
        node_data["disk_perc"] = KubeUtil.calc_perc(node_data["FSUB"], node_data["FSCB"])
        node_data["pod_perc"] = KubeUtil.calc_perc(len(self.final_json['Pods']), node_data["KNSAP"])

        if KubeGlobal.NODE_AGENT_STATS:
            node_data['da_stats'] = json.dumps(KubeGlobal.NODE_AGENT_STATS)
            KubeGlobal.NODE_AGENT_STATS = {}

    def process_pod_metrics(self):
        try:
            for pod_name, pod_metrics in self.final_json['Pods'].items():
                try:
                    pod_metrics.update({
                        'throttled_sec': 0,
                        'total_periods': 0,
                        'throttled_periods': 0
                    })
                    cpu_limit, mem_limit = pod_metrics.get("PRLCC", 0), pod_metrics.get("PRLMB", 0)
                    cpu_req, mem_req = pod_metrics.get("PRRCC", 0), pod_metrics.get("PRMB", 0)

                    # percentage metrics
                    if cpu_limit and 'UNC' in pod_metrics:
                        pod_metrics['CPU'] = KubeUtil.calc_perc(pod_metrics["UNC"], cpu_limit)
                    if mem_limit and 'UB' in pod_metrics:
                        pod_metrics['MEM'] = KubeUtil.calc_perc(pod_metrics['UB'], mem_limit)

                    # Slack metric
                    if cpu_req and "UNC" in pod_metrics:
                        pod_metrics["cpu_slack_mic"] = cpu_req - pod_metrics["UNC"]
                        pod_metrics["cpu_slack_perc"] = KubeUtil.calc_perc(pod_metrics["UNC"], cpu_req)
                    if mem_req and "UB" in pod_metrics:
                        pod_metrics["mem_slack_mib"] = mem_req - pod_metrics["UB"]
                        pod_metrics["mem_slack_perc"] = KubeUtil.calc_perc(pod_metrics["UB"], mem_req)

                    self.process_cont_metrics(pod_metrics["Cont"], pod_metrics)

                    pod_metrics['cpu_throttle_mic'] = (pod_metrics['throttled_sec'] / 300) * 1000

                    self.final_json['Nodes'][KubeGlobal.KUBELET_NODE_NAME]['NCR'] += cpu_req
                    self.final_json['Nodes'][KubeGlobal.KUBELET_NODE_NAME]['NCL'] += cpu_limit
                    self.final_json['Nodes'][KubeGlobal.KUBELET_NODE_NAME]['NMR'] += mem_req
                    self.final_json['Nodes'][KubeGlobal.KUBELET_NODE_NAME]['NML'] += mem_limit
                    self.final_json['Nodes'][KubeGlobal.KUBELET_NODE_NAME]['throttled_sec'] += pod_metrics['throttled_sec']
                    self.final_json['Nodes'][KubeGlobal.KUBELET_NODE_NAME]['throttled_periods'] += pod_metrics['throttled_periods']
                    self.final_json['Nodes'][KubeGlobal.KUBELET_NODE_NAME]['total_periods'] += pod_metrics['total_periods']
                    self.final_json['Nodes'][KubeGlobal.KUBELET_NODE_NAME]['KNRC'] += pod_metrics['PRC']
                    self.final_json['Nodes'][KubeGlobal.KUBELET_NODE_NAME]['KNRCPI'] += pod_metrics['KPRCPI']
                    self.final_json['Nodes'][KubeGlobal.KUBELET_NODE_NAME]['KNPC'] += 1
                except Exception as e:
                    AgentLogger.log(AgentLogger.KUBERNETES, "Exception in process_pod_metrics (pod iteration) - {}".format(e))
                    traceback.print_exc()

            self.final_json['Nodes'][KubeGlobal.KUBELET_NODE_NAME]['cpu_throttle_mic'] = (self.final_json['Nodes'][KubeGlobal.KUBELET_NODE_NAME]['throttled_sec'] / 300) * 1000
            self.final_json['Nodes'][KubeGlobal.KUBELET_NODE_NAME]['cpu_throttle_perc'] = (
                KubeUtil.calc_perc(
                    self.final_json['Nodes'][KubeGlobal.KUBELET_NODE_NAME]['throttled_periods'],
                    self.final_json['Nodes'][KubeGlobal.KUBELET_NODE_NAME]['total_periods']
                )
            ) if self.final_json['Nodes'][KubeGlobal.KUBELET_NODE_NAME]['total_periods'] else 0
        except Exception as e:
            AgentLogger.log(AgentLogger.KUBERNETES, "Exception in process_pod_metrics - {}".format(e))
            traceback.print_exc()

    @exception_handler
    def process_cont_metrics(self, cont_data, pod_metrics):
        for cont_key, cont_metrics in cont_data.items():
            throttled_sec, total_periods, throttled_periods = cont_metrics.get("throttled_sec", 0), cont_metrics.get("total_periods", 0), cont_metrics.get("throttled_periods", 0)
            if "KCACPU" in cont_metrics and "KPCRLCC" in cont_metrics:
                cont_metrics['cpu_percent'] = (cont_metrics["KCACPU"] / cont_metrics["KPCRLCC"]) * 100
            if "KCAMUB" in cont_metrics and "KPCRLMB" in cont_metrics:
                cont_metrics["memory_percent"] = (cont_metrics["KCAMUB"] / cont_metrics["KPCRLMB"]) * 100

            # Slack metric
            if "KPCRRCC" in cont_metrics and "KCACPU" in cont_metrics:
                cont_metrics["cpu_slack_mic"] = cont_metrics["KPCRRCC"] - cont_metrics["KCACPU"]
                cont_metrics["cpu_slack_perc"] = KubeUtil.calc_perc(cont_metrics["KCACPU"], cont_metrics["KPCRRCC"])
            if "KPCRRMB" in cont_metrics and "KCAMUB" in cont_metrics:
                cont_metrics["mem_slack_mib"] = cont_metrics["KPCRRMB"] - cont_metrics["KCAMUB"]
                cont_metrics["mem_slack_perc"] = KubeUtil.calc_perc(cont_metrics["KCAMUB"], cont_metrics["KPCRRMB"])

            cont_metrics['cpu_throttle_mic'] = (throttled_sec / 300) * 1000
            pod_metrics["throttled_sec"] += throttled_sec
            pod_metrics["total_periods"] += total_periods
            pod_metrics["throttled_periods"] += throttled_periods

            if total_periods:
                cont_metrics["cpu_throttle_perc"] = KubeUtil.calc_perc(throttled_periods, total_periods)

        if pod_metrics['total_periods']:
            pod_metrics["cpu_throttle_perc"] = KubeUtil.calc_perc(pod_metrics["throttled_periods"], pod_metrics["total_periods"])
