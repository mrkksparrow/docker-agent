'''
@author: bharath.veerakumar

Created on Feb 20 2023
'''


import traceback
from com.manageengine.monagent.kubernetes.Collector.DataCollectorInterface import DataCollector
from com.manageengine.monagent.kubernetes import KubeUtil, KubeGlobal
from com.manageengine.monagent.kubernetes.Logging import KubeLogger as AgentLogger


class GuidanceMetrics(DataCollector):
    def collect_data(self):
        self.get_gr_metrics_for_conf_agent() if KubeUtil.is_conf_agent() else self.get_gr_metrics_for_perf_agent()

    def get_data_for_cluster_agent(self, req_params=None):
        self.get_gr_metrics_for_conf_agent()
        return self.final_json

    def get_gr_metrics_for_conf_agent(self):
        for res_type in ["DaemonSets", "Deployments", "StatefulSets"]:
            url = KubeGlobal.apiEndpoint + KubeGlobal.API_ENDPOINT_RES_NAME_MAP[res_type]
            self.final_json[res_type] = {}
            KubeUtil.get_api_data_by_limit(url, self.process_workloads_raw_data, res_type)

    def get_gr_metrics_for_perf_agent(self):
        self.final_json['Pods'] = {
            pods['metadata']['name'] + "_" + pods['metadata']['namespace']: {
                "GRPWO": "ownerReferences" not in pods['metadata']
            } for pods in KubeGlobal.NODE_BASE_PODS_CONFIGS['items']
        }

    def process_workloads_raw_data(self, api_resp, res_type):
        try:
            final_dict = self.final_json[res_type]
            for res_value in api_resp["items"]:
                containers_list = res_value["spec"]["template"]["spec"].get("containers", {})
                pods_scc = res_value["spec"]["template"]["spec"].get("securityContext", {})
                res_name = res_value['metadata']['name'] + "_" + res_value['metadata']['namespace']
                final_dict[res_name] = {}
                inner_dict = final_dict[res_name]

                if type(pods_scc) != dict:
                    pods_scc = {}

                for key in ["GRLPF", "GRRPF", "GRSCROF", "GRSCAPE", "GRSCPR", "GRSCRNR", "GRTNS", "GRMEMR", "GRCPUR", "GRMEML", "GRCPUL", "GRIPP"]:
                    inner_dict[key] = []

                for val in containers_list:
                    try:
                        cont_name = val["name"]
                        security_ctx = KubeUtil.MergeDataDictionaries(val.get("securityContext", {}), pods_scc) # SCC can be set through pod level, So need to merge both
                        img_tag = val.get("image", ":latest").split(":")
                        res_limit = val.get("resources", {}).get("limits", {})
                        res_req = val.get("resources", {}).get("requests", {})

                        if "livenessProbe" not in val:  # Liveness Probe Missing
                            inner_dict["GRLPF"].append(cont_name)

                        if "readinessProbe" not in val:  # Readiness Probe Missing
                            inner_dict["GRRPF"].append(cont_name)

                        if not security_ctx.get("readOnlyRootFilesystem", False):
                            inner_dict["GRSCROF"].append(cont_name)  # Fails when securityContext.ReadOnlyFileSystem is false.

                        if security_ctx.get("allowPrivilegeEscalation", True):
                            inner_dict["GRSCAPE"].append(cont_name) # Fails when securityContext.allowPrivilegedEscalations is true.

                        if security_ctx.get("privileged", False):
                            inner_dict["GRSCPR"].append(cont_name)  # Fails when securityContext.privileged is true.

                        if not security_ctx.get("runAsNonRoot", False):
                            inner_dict["GRSCRNR"].append(cont_name)  # Fails when securityContext.runAsNonRoot is not true.

                        if len(img_tag) == 1 or img_tag[-1] == "latest":
                            inner_dict["GRTNS"].append(cont_name)   # Tag Not Specified

                        if not val.get("imagePullPolicy") == "Always":
                            inner_dict["GRIPP"].append(cont_name)   # Pull Policy Not Always

                        if "cpu" not in res_limit:
                            inner_dict["GRCPUL"].append(cont_name)  # CPU Limits Missing

                        if "memory" not in res_limit:
                            inner_dict["GRMEML"].append(cont_name)  # Mem Limits Missing

                        if "cpu" not in res_req:
                            inner_dict["GRCPUR"].append(cont_name)  # CPU Requests Missing

                        if "memory" not in res_req:
                            inner_dict["GRMEMR"].append(cont_name)  # Mem Requests Missing
                    except Exception as e:
                        AgentLogger.log(AgentLogger.KUBERNETES, "Exc -> guidance metrics -> {}".format(e))
                        traceback.print_exc()

                for key in ["GRLPF", "GRRPF", "GRSCROF", "GRSCAPE", "GRSCPR", "GRSCRNR", "GRTNS", "GRMEMR", "GRCPUR", "GRMEML", "GRCPUL", "GRIPP"]:
                    inner_dict[key] = ",".join(inner_dict[key]) if inner_dict[key] else "-"

                if res_type in ['Deployments', 'StatefulSets']:
                    inner_dict['GRDMR'] = res_value['spec']['replicas'] > 1
        except Exception as e:
            AgentLogger.log(AgentLogger.KUBERNETES, "Exc -> guidance metrics -> {}".format(e))
            traceback.print_exc()
