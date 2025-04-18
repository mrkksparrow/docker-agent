import traceback

from com.manageengine.monagent.kubernetes import KubeGlobal, KubeUtil
from com.manageengine.monagent.kubernetes.Logging import KubeLogger as AgentLogger
from com.manageengine.monagent.kubernetes.Parser.PrometheusParserInterface import PrometheusParser


def exception_handler(func):
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            AgentLogger.log(AgentLogger.KUBERNETES, "*** EXCEPTION *** => [APIServerMetricsParser] => {} => {} => {} ******".format(func.__name__, e, traceback.format_exc()))
    return wrapper


class APIServerMetrics(PrometheusParser):
    @exception_handler
    def __init__(self, apiserver_config):
        apiserver_endpoint = "https://{}:{}/metrics".format(apiserver_config["ip"],apiserver_config["port"])
        self.healthz_endpoint = "https://{}:{}/healthz".format(apiserver_config["ip"],apiserver_config["port"])
        self.livez_endpoint = "https://{}:{}/livez".format(apiserver_config["ip"],apiserver_config["port"])
        self.eks_monitor = True if "eks" in apiserver_config and apiserver_config["eks"] else False
        super().__init__(apiserver_endpoint)
        self.parser_config = {
            "apiserver_audit_event": [
                {
                    "short_name": "AAE",
                    "group_name": "",
                },
            ],
            "apiserver_audit_requests_rejected": [
                {
                    "short_name": "ARR",
                    "group_name": "",
                },
            ],
            "apiserver_current_inqueue_requests": [
                {
                    "short_name": "CIQR",
                    "sum": ["", "CIQR", "sum_only"]
                },
            ],
            "apiserver_kube_aggregator_x509_insecure_sha1": [
                {
                    "short_name": "KAIS",
                    "group_name": "",
                },
            ],
            "apiserver_webhooks_x509_insecure_sha1": [
                {
                    "short_name": "AWIS",
                    "group_name": "",
                },
            ],
            "apiserver_request_aborts": [
                {
                    "short_name": "ARA",
                    "sum": ["", "ARA", "sum_only"]
                },
            ],
            "apiserver_requested_deprecated_apis": [
                {
                    "short_name": "ARDA",
                    "sum": ["", "ARDA", "sum_only"]
                },
            ],
            "apiserver_tls_handshake_errors": [
                {
                    "short_name": "ATHE",
                    "group_name": "",
                },
            ],
            "apiserver_admission_webhook_admission_duration_seconds": [
                {
                    "short_name": "WADS",
                    "sum": ["", "WADS", "sum_only"],

                },
            ],
            "apiserver_admission_controller_admission_duration_seconds": [
                {
                    "short_name": "CADS",
                    "round_value": 2,
                    "sum": ["", "CADS", "sum_only"],

                },
            ],
            "etcd_request_duration_seconds": [
                {
                    "short_name": "ERDS",
                    "sum": ["", "ERDS", "sum_only"],

                },
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
            "process_virtual_memory_bytes": [
                {
                    "short_name": "PVMB",
                    "group_name": "",
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
            "apiserver_current_inflight_requests": [
                {
                    "short_name": "ACIR",
                    "value_type": float,
                    "sum": ["", "ACIR", "sum_only"],
                },
            ],
            "apiserver_storage_objects": [
                {
                    "short_name": "ASO",
                    "value_type": int,
                    "sum": ["", "ASOT"],
                    "group_name": "stored_objects",
                    "group_labels": ["resource"],
                    "labels": {
                        "resource": "rs",
                    }
                },
            ],
            "apiserver_storage_db_total_size_in_bytes": [
                self.parse_apiserver_storage_db_total_size_in_bytes,
            ],
            "apiserver_response_sizes": [
                {
                    "short_name": "ARS",
                    "group_name": "apiserver_resource",
                    "round_value": 2,
                    "labels": {
                        "resource": "rs",
                    },
                    "sum": ["", "ARST"],
                    "group_labels": ["resource"],
                },
            ],
            "apiserver_request_duration_seconds": [
                {
                    "short_name": "ARDS",
                    "group_name": "apiserver_resource",
                    "round_value": 2,
                    "labels": {
                        "resource": "rs",
                    },
                    "sum": ["", "ARDST"],
                    "group_labels": ["resource"],
                },
            ],
            "apiserver_registered_watchers": [
                {
                    "short_name": "ARW",
                    "value_type": int,
                    "group_name": "ARW",
                    "labels": {
                        "kind": "ki",
                    },
                    "group_labels": ["kind"]
                },
            ],
            "rest_client_requests": [
                {
                    "short_name": "RCR",
                    "group_name": "request_count_code",
                    "labels": {
                        "code": "cd",
                    },
                    "group_labels": ["code"],
                },
                {
                    "short_name": "RCR",
                    "group_name": "request_count_verb",
                    "labels": {
                        "method": "vb",
                    },
                    "group_labels": ["method"],
                },
                {
                    "short_name": "RCR",
                    "group_name": "request_count_host",
                    "labels": {
                        "host": "ho",
                    },
                    "group_labels": ["host"],
                },
            ],
            "apiserver_request": [
                {
                    "short_name": "ASR",
                    "value_type": int,
                    "group_name": "request_count_code",
                    "labels": {
                        "code": "cd",
                    },
                    "group_labels": ["code"],
                },
                {
                    "short_name": "ASR",
                    "value_type": int,
                    "group_name": "apiserver_resource",
                    "round_value": 2,
                    "labels": {
                        "resource": "rs",
                    },
                    "group_labels": ["resource"],
                },
                {
                    "short_name": "ASR",
                    "value_type": int,
                    "group_name": "request_count_verb",
                    "labels": {
                        "verb": "vb",
                    },
                    "group_labels": ["verb"],
                },
                {
                    "short_name": "ASRT",
                    "value_type": int,
                    "sum": ["", "ASRT", "sum_only"],
                },
            ],
            "apiserver_longrunning_requests": [
                {
                    "short_name": "ALR",
                    "value_type": int,
                    "round_value": 2,
                    "group_name": "long_running_request",
                    "labels": {
                        "resource": "rs",
                        "verb": "vb",
                    },
                    "group_labels": ["resource", "verb"],
                },
            ],
            "grpc_client_handled": [
                {
                    "short_name": "GCH",
                    "value_type": int,
                    "group_name": "grpc_request_serv_meth",
                    "labels": {
                        "grpc_service": "gs",
                        "grpc_method": "gm",
                    },
                    "group_labels": ["grpc_service", "grpc_method"],
                },
                {
                    "short_name": "GCH",
                    "value_type": int,
                    "group_name": "grpc_request_code",
                    "labels": {
                        "grpc_code": "gc",
                    },
                    "group_labels": ["grpc_code"],
                },
            ],
            "kubernetes_feature_enabled": [
                {
                    "short_name": "KFE",
                    "value_type": int,
                    "group_name": "kube_features",
                    "onchange": True,
                    "labels": {
                        "name": "na",
                        "stage": "st",
                    },
                    "group_labels": ["name"]
                },
            ],
            "workqueue_adds": [
                {
                    "short_name": "WQA",
                    "value_type": int,
                    "round_value": 2,
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
                    "round_value": 2,
                    "group_name": "workqueue",
                    "labels": {
                        "name": "na",
                    },
                    "group_labels": ["name"]
                },
            ],
            "authentication_duration_seconds": [
                {
                    "short_name": "ADS",
                    "group_name": "authentication_attempts",
                    "round_value": 2,
                    "labels": {
                        "result": "re"
                    },
                    "group_labels": ["result"],
                },
            ],
        }
        self.get_data()
        self.handle_eks_monitors()
        self.decide_health_check_status()
        self.parse_apiserver_resource()
        self.parse_workqueue()
        self.parse_stored_objects()
        self.parse_long_running_request()
        self.change_data_format(apiserver_config)

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
    def handle_eks_monitors(self):
        self.final_data["bulk_dc"] = "true" if self.eks_monitor else "false"

    @exception_handler
    def parse_apiserver_storage_db_total_size_in_bytes(self, family_list):
        for entry in family_list:
            if "endpoint" in entry.labels and str(KubeGlobal.IP_ADDRESS) in entry.labels["endpoint"]:
                self.final_data["SDTS"] = entry.value

    @exception_handler
    def parse_apiserver_resource(self):
        if "apiserver_resource" in self.final_data:
            apiserver_resource_data_copy = self.final_data.pop("apiserver_resource")
            for each_resource in apiserver_resource_data_copy:
                if "ARDSS" in apiserver_resource_data_copy[each_resource]:
                    apiserver_resource_data_copy[each_resource]["ARDSS"] = round(apiserver_resource_data_copy[each_resource]["ARDSS"], 2)
            self.final_data["apiserver_resource_rd"] = self.get_top_n_data(apiserver_resource_data_copy, "ARDSS", True, 10)
            self.final_data["apiserver_resource_rs"] = self.get_top_n_data(apiserver_resource_data_copy, "ARSS", True, 10)
            self.final_data["apiserver_resource_rc"] = self.get_top_n_data(apiserver_resource_data_copy, "ASR", True, 10)

    @exception_handler
    def parse_workqueue(self):
        if "workqueue" in self.final_data:
            workqueue_data_copy = self.final_data.pop("workqueue")
            self.final_data["workqueue_add"]   = self.get_top_n_data(workqueue_data_copy, "WQA", True, 10)
            self.final_data["workqueue_depth"] = self.get_top_n_data(workqueue_data_copy, "WQD", True, 10)

    @exception_handler
    def parse_stored_objects(self):
        if "stored_objects" in self.final_data:
            self.final_data["stored_objects"] = self.get_top_n_data(self.final_data["stored_objects"], "ASO", True, 10)

    @exception_handler
    def parse_long_running_request(self):
        if "long_running_request" in self.final_data:
            self.final_data["long_running_request"] = self.get_top_n_data(self.final_data["long_running_request"], "ALR", True, 10)

    @exception_handler
    def change_data_format(self, apiserver_config):
        apiserver_keyname = "{}:{}".format(apiserver_config["ip"],apiserver_config["port"])
        self.final_data.update({"host": apiserver_keyname, "cp_type": "KUBERNETES_API_SERVER", "Hostname": KubeGlobal.KUBELET_NODE_NAME})
        self.final_data = {
            apiserver_keyname : self.final_data
        }
