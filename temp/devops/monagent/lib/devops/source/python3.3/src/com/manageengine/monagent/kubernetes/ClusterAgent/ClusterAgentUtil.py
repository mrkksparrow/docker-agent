import time, os, json, traceback, fcntl
from com.manageengine.monagent.kubernetes import KubeUtil, KubeGlobal
from com.manageengine.monagent.kubernetes.Logging import KubeLogger as AgentLogger


def check_and_discover_cluster_agent_svc():
    try:
        url = "/api/v1/services?labelSelector={}%3D{}"
        for key, value in [("app.kubernetes.io/name", "site24x7-cluster-agent"), ("name", "site24x7-cluster-agent")]:
            status, resp = KubeUtil.curl_api_with_token(KubeGlobal.host + url.format(key, value))

            if status == 200 and "items" in resp and len(resp["items"]):
                svc_data = resp['items'][0]
                KubeGlobal.CLUSTER_AGENT_SVC = "http://{}.{}:5000".format(svc_data["metadata"]["name"], svc_data["metadata"]["namespace"])
                if KubeUtil.is_conf_agent():
                    status, response = KubeUtil.curl_api_without_token(KubeGlobal.CLUSTER_AGENT_SVC + '/ca/version')
                    KubeGlobal.CLUSTER_AGENT_STATS["version"] = response
                    KubeGlobal.CLUSTER_AGENT_STATS["cluster_agent_status"] = 1 if int(response) >= KubeGlobal.LOWEST_SUPPORTED_CLUSTER_AGENT_VERSION and KubeUtil.is_eligible_to_execute("clusteragent", KubeGlobal.DC_START_TIME) else 0
                return
    except Exception:
        traceback.print_exc()
    KubeGlobal.CLUSTER_AGENT_STATS["cluster_agent_status"] = 0
    KubeGlobal.CLUSTER_AGENT_SVC = None


def check_last_mtime(file_path, expiry_time = None):
    return True if time.time() - os.stat(file_path).st_mtime <= float(60 if not expiry_time else expiry_time) else False


def get_ca_parsed_data(data_type, req_params, method_type='GET'):
    try:
        bef_req = time.time()
        url = KubeGlobal.CLUSTER_AGENT_SVC + KubeGlobal.CLUSTER_AGENT_URL_DATA_TYPE_MAP[data_type]
        KubeGlobal.CLUSTER_AGENT_STATS[data_type]['req_cnt'] = KubeGlobal.CLUSTER_AGENT_STATS[data_type].get('req_cnt', 0) + 1

        if method_type == "GET" and req_params:
            param_ls = []
            for key, value in req_params.items():
                param_ls.append('{}={}'.format(key, value))
            url += '?{}'.format('&'.join(param_ls))

        status, resp = KubeUtil.curl_api_without_token(url, method=method_type, request_body=req_params)
        KubeGlobal.CLUSTER_AGENT_STATS[data_type][status] = KubeGlobal.CLUSTER_AGENT_STATS[data_type].get(status, 0) + 1
        if status == 200:
            resp_time = time.time() - bef_req
            KubeGlobal.CLUSTER_AGENT_STATS[data_type]["req_failure"] = 0
            KubeGlobal.CLUSTER_AGENT_STATS[data_type]["response_time"] = resp_time
            AgentLogger.log(AgentLogger.KUBERNETES, "********* Cluster agent responded in {} for {} *********".format(resp_time, data_type))
            return json.loads(resp)
    except Exception as e:
        AgentLogger.console_logger.warning("Exception in get_ca_parsed_data - > {}".format(e))
        traceback.print_exc()
    AgentLogger.log(AgentLogger.KUBERNETES, "******** Cluster Agent not Ready - {} - {} *********".format(data_type, KubeGlobal.CLUSTER_AGENT_STATS[data_type]))
    return None


def get_parsed_data_for_ca(data_type):
    if KubeGlobal.IS_CLUSTER_AGENT:
        # checking if exists in cache (npc_ksm is required for aggregation)
        file_path = KubeGlobal.PARSED_DATA_FOLDER_PATH + '/{}'.format(KubeGlobal.DATA_TYPE_PARSED_FILE_MAP[data_type])
        parsed_data = read_json_from_file(file_path)

        return parsed_data
    return None


def get_ksm_api_resp():
    ksm_data = None
    if os.path.exists(KubeGlobal.KSM_OUTPUT_FILE) and check_last_mtime(KubeGlobal.KSM_OUTPUT_FILE):
        with open(KubeGlobal.KSM_OUTPUT_FILE, 'r') as read_obj:
            ksm_data = read_obj.read()
    return ksm_data


def read_json_from_file(file_path):
    try:
        if os.path.exists(file_path) and check_last_mtime(file_path):
            with ReadOrWriteWithFileLock(file_path, 'r') as read_obj:
                parsed_data = read_obj.read_json()
            return parsed_data
    except Exception:
        traceback.print_exc()
    return None


def remove_invalid_nodes(data_type, resp_json):
    if data_type in ["conf"]:
        update_needed = False
        if data_type == "conf":
            update_needed = True

        invalid_nodes = []
        for key_name in resp_json.keys():
            if not KubeUtil.is_eligible_to_execute(key_name.lower(), KubeGlobal.DC_START_TIME, update_needed):
                invalid_nodes.append(key_name)

        for key in invalid_nodes:
            resp_json.pop(key)


def upgrade_cluster_agent():
    try:
        status, response = KubeUtil.curl_api_with_token(KubeGlobal.apiEndpoint + '/api/v1/pods?labelSelector=app.kubernetes.io/name%3Dsite24x7-cluster-agent')
        if status == 200 and response and "items" in response:
            url = 'http://{}:5000/ca/initiate_agent_upgrade'
            for pods in response["items"]:
                try:
                    pod_ip = pods['status']['podIP']
                    status, response = KubeUtil.curl_api_without_token(url.format(pod_ip))
                    if status == 200:
                        continue
                    AgentLogger.log(AgentLogger.KUBERNETES, "****** Cluster Agent not upgraded {} ********".format(pod_ip))
                except Exception:
                    traceback.print_exc()
    except Exception:
        traceback.print_exc()


class ReadOrWriteWithFileLock:
    def __init__(self, file_path, mode):
        self.file_path = file_path
        self.os_file_obj = os.open(file_path, os.O_RDWR | os.O_CREAT if mode == 'w' else os.O_RDONLY)
        self.file_obj = None
        self.access_mode = mode

    def __enter__(self):
        fcntl.flock(self.os_file_obj, fcntl.LOCK_EX)
        self.file_obj = open(self.file_path, self.access_mode)
        return self

    def write(self, content):
        self.file_obj.write(content)

    def write_json(self, content):
        json.dump(content, self.file_obj)

    def read(self):
        return self.file_obj.read()

    def read_json(self):
        return json.load(self.file_obj)

    def __exit__(self, exc_type, exc_val, exc_tb):
        fcntl.flock(self.os_file_obj, fcntl.LOCK_UN)
        self.file_obj.close()
        os.close(self.os_file_obj)
