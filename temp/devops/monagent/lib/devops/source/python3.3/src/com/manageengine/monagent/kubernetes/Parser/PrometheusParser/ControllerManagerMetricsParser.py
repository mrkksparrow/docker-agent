import traceback

from com.manageengine.monagent.kubernetes import KubeGlobal, KubeUtil
from com.manageengine.monagent.kubernetes.Logging import KubeLogger as AgentLogger
from com.manageengine.monagent.kubernetes.Parser.PrometheusParserInterface import PrometheusParser


def exception_handler(func):
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            AgentLogger.log(AgentLogger.KUBERNETES, "*** EXCEPTION *** => [ControllerManagerMetricsParser] => {} => {} => {} ******".format(func.__name__, e, traceback.format_exc()))
    return wrapper


class ControllerManagerMetrics(PrometheusParser):
    @exception_handler
    def __init__(self, controllermanager_config):
        controllermanager_endpoint = "https://{}:{}/metrics".format(controllermanager_config["ip"],controllermanager_config["port"])
        self.healthz_endpoint = "https://{}:{}/healthz".format(controllermanager_config["ip"],controllermanager_config["port"])
        self.livez_endpoint = "https://{}:{}/livez".format(controllermanager_config["ip"],controllermanager_config["port"])
        super().__init__(controllermanager_endpoint)
        self.parser_config = {
            "workqueue_adds": [
                {
                    "short_name": "WQA",
                    "value_type": int,
                    "group_name": "workqueue",
                    "labels": {
                        "name": "na",
                    },
                    "group_labels": ["name"]
                },
            ],
            "workqueue_depth": [
                {
                    "short_name": "WQD",
                    "value_type": int,
                    "group_name": "workqueue",
                    "labels": {
                        "name": "na",
                    },
                    "group_labels": ["name"]
                },
            ],
            "workqueue_queue_duration_seconds": [
                {
                    "short_name": "WQDS",
                    "group_name": "workqueue",
                    "round_value": 2,
                    "labels": {
                        "name": "na",
                    },
                    "group_labels": ["name"],
                },
            ],
            "workqueue_retries": [
                {
                    "short_name": "WQT",
                    "group_name": "workqueue",
                    "round_value": 2,
                    "labels": {
                        "name": "na",
                    },
                    "group_labels": ["name"],
                },
            ],
            "workqueue_unfinished_work_seconds": [
                {
                    "short_name": "WUWS",
                    "group_name": "workqueue",
                    "round_value": 2,
                    "labels": {
                        "name": "na",
                    },
                    "group_labels": ["name"],
                },
            ],
            "workqueue_work_duration_seconds": [
                {
                    "short_name": "WWDS",
                    "group_name": "workqueue",
                    "round_value": 2,
                    "labels": {
                        "name": "na",
                    },
                    "group_labels": ["name"],
                },
            ],
            "workqueue_longest_running_processor_seconds": [
                {
                    "short_name": "WLRP",
                    "value_type": int,
                    "group_name": "workqueue",
                    "labels": {
                        "name": "na",
                    },
                    "group_labels": ["name"],
                },
            ],
            "go_threads": [
                {
                    "short_name": "GT",
                    "group_name": "",
                },
            ],
            "go_goroutines": [
                {
                    "short_name": "GR",
                    "group_name": "",
                },
            ],
            "rest_client_requests": [
                {
                    "short_name": "RCR",
                    "group_name": "request_count_code",
                    "round_value": 2,
                    "labels": {
                        "code": "cd",
                    },
                    "group_labels": ["code"],
                },
                {
                    "short_name": "RCR",
                    "group_name": "request_count_verb",
                    "round_value": 2,
                    "labels": {
                        "method": "vb",
                    },
                    "group_labels": ["method"],
                },
                {
                    "short_name": "RCR",
                    "group_name": "request_count_host",
                    "round_value": 2,
                    "labels": {
                        "host": "ho",
                    },
                    "group_labels": ["host"],
                },
            ],
            "rest_client_request_duration_seconds": [
                {
                    "short_name": "RCRD",
                    "group_name": "request_count_verb",
                    "round_value": 2,
                    "labels": {
                        "verb": "vb",
                    },
                    "group_labels": ["verb"],
                },
                {
                    "short_name": "RCRD",
                    "group_name": "request_count_host",
                    "round_value": 2,
                    "labels": {
                        "host": "ho",
                    },
                    "group_labels": ["host"],
                },
                {
                    "short_name": "RCRD",
                    "sum": ["", "RCRD", "sum_only"],
                },
            ],
            "job_controller_terminated_pods_tracking_finalizer": [
                {
                    "short_name": "JCTPA",
                    "group_name": "",
                    "match_labels": {
                        "event": "add",
                    },
                },
                {
                    "short_name": "JCTPD",
                    "group_name": "",
                    "match_labels": {
                        "event": "delete",
                    },
                },
            ],
            "leader_election_master_status": [
                self.parse_leader_election_master_status,
            ],
            "process_resident_memory_bytes": [
                {
                    "short_name": "PRMB",
                    "group_name": "",
                },
            ],
            "process_cpu_seconds": [
                {
                    "short_name": "PCS",
                    "group_name": "",
                },
            ],
            "process_open_fds": [
                {
                    "short_name": "POF",
                    "group_name": "",
                },
            ],
            "process_max_fds": [
                {
                    "short_name": "PMF",
                    "group_name": "",
                },
            ],
            "process_virtual_memory_bytes": [
                {
                    "short_name": "PVMB",
                    "group_name": "",
                },
            ],
        }
        self.get_data()
        self.decide_health_check_status()
        self.parse_workqueue()
        self.change_data_format(controllermanager_config)

    @exception_handler
    def decide_health_check_status(self):
        status, response = KubeUtil.curl_api_with_token(self.healthz_endpoint)
        if status == 200:
            self.final_data['healthz_check_status'] = 1
        else:
            self.final_data['healthz_check_status'] = 0
            self.final_data['DCErrors']['healthz_check_status'] = {status: response}

        status, response = KubeUtil.curl_api_with_token(self.livez_endpoint)
        if status == 200:
            self.final_data['livez_check_status'] = 1
        else:
            self.final_data['livez_check_status'] = 0
            self.final_data['DCErrors']['livez_check_status'] = {status: response}

    @exception_handler
    def parse_leader_election_master_status(self, family_list):
        for entry in family_list:
            if "name" in entry.labels and "kube-controller-manager" == entry.labels["name"]:
                if int(entry.value) == 1:
                    self.final_data["LEMS"] = "Master"
                elif int(entry.value) == 0:
                    self.final_data["LEMS"] = "Backup"
                else:
                    self.final_data["LEMS"] = str(entry.value)

    @exception_handler
    def parse_workqueue(self):
        if "workqueue" in self.final_data:
            workqueue_data_copy = self.final_data.pop("workqueue")
            self.final_data["workqueue_add"]             = self.get_top_n_data(workqueue_data_copy, "WQA", True, 10)
            self.final_data["workqueue_depth"]           = self.get_top_n_data(workqueue_data_copy, "WQD", True, 10)
            self.final_data["workqueue_retries"]         = self.get_top_n_data(workqueue_data_copy, "WQT", True, 10)
            self.final_data["workqueue_work_duration"]   = self.get_top_n_data(workqueue_data_copy, "WWDS", True, 10)
            self.final_data["workqueue_queue_duration"]  = self.get_top_n_data(workqueue_data_copy, "WQDS", True, 10)
            self.final_data["workqueue_unfinished_work"] = self.get_top_n_data(workqueue_data_copy, "WUWS", True, 10)
            self.final_data["workqueue_longest_running"] = self.get_top_n_data(workqueue_data_copy, "WLRP", True, 10)

    @exception_handler
    def change_data_format(self, controllermanager_config):
        controllermanager_keyname = "{}:{}".format(controllermanager_config["ip"],controllermanager_config["port"])
        self.final_data.update({"host": controllermanager_keyname, "cp_type": "KUBERNETES_CONTROLLER_MANAGER", "Hostname": KubeGlobal.KUBELET_NODE_NAME})
        self.final_data = {
            controllermanager_keyname : self.final_data
        }
