'''
@author: bharath.veerakumar

Created on Feb 20 2023
'''


import os
import traceback

from com.manageengine.monagent.kubernetes import KubeGlobal, KubeUtil
from com.manageengine.monagent.kubernetes.Collector.NPCDataCollector import NPCDataCollector
from com.manageengine.monagent.kubernetes.Logging import KubeLogger as AgentLogger


class SidecarNPCCollector(NPCDataCollector):

    def merge_apis_data(self, k8s_api_data, kubelet_data, cadvisor_data):
        perf_data = {}
        pod_data = {}
        node_data = {}
        sidecar_pod_name = os.environ.get("S247_POD_NAME") + "_" + os.environ.get("S247_POD_NS")
        try:
            node_data[KubeGlobal.KUBELET_NODE_NAME] = kubelet_data["Nodes"][KubeGlobal.KUBELET_NODE_NAME]
            pod_data[sidecar_pod_name] = kubelet_data.pop("Pods")[sidecar_pod_name]

            if "Pods" in self.ksm_data and sidecar_pod_name in self.ksm_data["Pods"]:
                pod_data[sidecar_pod_name].update(self.ksm_data["Pods"][sidecar_pod_name])

            if "Nodes" in self.ksm_data and KubeGlobal.KUBELET_NODE_NAME in self.ksm_data["Nodes"]:
                node_data[KubeGlobal.KUBELET_NODE_NAME].update(self.ksm_data["Nodes"][KubeGlobal.KUBELET_NODE_NAME])

            keys_to_remove = []
            for cont_key, cont_val in cadvisor_data.items():
                if cont_key in self.ksm_data["Cont"] and (cont_val["Po"]+"_"+cont_val["NS"]) == sidecar_pod_name:
                    cadvisor_data[cont_key].update(self.ksm_data["Cont"][cont_key])
                else:
                    keys_to_remove.append(cont_key)

            for key in keys_to_remove:
                cadvisor_data.pop(key, None)
        except Exception as e:
            traceback.print_exc()
            AgentLogger.log(AgentLogger.KUBERNETES, "Exc in collect_cadvisor_data {}".format(e))
        finally:
            perf_data['Nodes'] = node_data
            perf_data['Pods'] = pod_data
            perf_data['Cont'] = cadvisor_data
            self.final_json = KubeUtil.MergeDataDictionaries(perf_data, k8s_api_data)