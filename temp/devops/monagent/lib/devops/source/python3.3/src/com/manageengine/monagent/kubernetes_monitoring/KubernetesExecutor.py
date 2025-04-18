import os
import time,random
import traceback
import sys

from six.moves.urllib.parse import urlencode
from com.manageengine.monagent.logger import AgentLogger
from com.manageengine.monagent.communication import CommunicationHandler
from com.manageengine.monagent import AgentConstants
from com.manageengine.monagent.scheduler import AgentScheduler
from com.manageengine.monagent.kubernetes import KubeGlobal, KubeDCExecutor
if 'com.manageengine.monagent.kubernetes.KubeUtil' in sys.modules:
    KubeUtil = sys.modules['com.manageengine.monagent.kubernetes.KubeUtil']
else:
    from com.manageengine.monagent.kubernetes import KubeUtil
from com.manageengine.monagent.util.AgentUtil import FileUtil,ZipUtil
from com.manageengine.monagent.util import AgentUtil

try:
    import configparser
except Exception as e:
    import ConfigParser as configparser

SCHEDULE_INFO = None


def schedule(rediscover=False):
    init()
    KubeDCExecutor.init()
    AgentLogger.log(AgentLogger.KUBERNETES, 'kuber scheduled : ')
    KubeGlobal.prevConfigDataTime = -1
    AgentLogger.log(AgentLogger.KUBERNETES, 'kube enabled... {0}'.format(KubeGlobal.monStatus))
    if KubeGlobal.monStatus == '1' or rediscover:
        discover_kubernetes()
        if KubeGlobal.mid != '0':
            AgentLogger.log(AgentLogger.KUBERNETES, '************ Schedule -> kubernetes present and scheduled ***********\n')
            time.sleep(random.randint(0, 10))  # to avoid the initial cluster agent struggle
            schedule_dc_tasks()
        else:
            AgentLogger.log(AgentLogger.KUBERNETES, '********** Schedule -> kubernetes not present and not scheduled ***********\n')
    else:
        AgentLogger.log(AgentLogger.KUBERNETES, 'kubernetes not enabled')

def init():
    if (AgentConstants.IP_ADDRESS == '127.0.0.1' or not AgentConstants.IP_ADDRESS) and 'NODE_IP' in os.environ:
        AgentConstants.IP_ADDRESS = os.environ['NODE_IP']
    KubeGlobal.IP_ADDRESS = AgentConstants.IP_ADDRESS

@KubeUtil.exception_handler
def schedule_dc_tasks():
    global SCHEDULE_INFO
    KubeDCExecutor.create_dc_objs()
    task = KubeDCExecutor.execute_tasks
    SCHEDULE_INFO = AgentScheduler.ScheduleInfo()
    SCHEDULE_INFO.setIsPeriodic(True)
    SCHEDULE_INFO.setSchedulerName('K8sScheduler')
    SCHEDULE_INFO.setTaskName(KubeGlobal.mid)
    SCHEDULE_INFO.setTime(time.time())
    SCHEDULE_INFO.setTask(task)
    SCHEDULE_INFO.setInterval(60)
    SCHEDULE_INFO.setCallback(write_data_to_file)
    SCHEDULE_INFO.setLogger(AgentLogger.KUBERNETES)
    AgentScheduler.schedule(SCHEDULE_INFO)
    AgentLogger.log(AgentLogger.KUBERNETES, 'scheduling done')



def write_data_to_file(data_files_list):
    data_files_path_list = {}
    try:
        if data_files_list:
            for each_data in data_files_list:
                dc_type="perf"
                #add mid
                if not ('mid' in each_data):
                    each_data["mid"] = KubeGlobal.mid
                #determining dc type
                if "kubelet" in each_data:
                    dc_type="kubelet"
                elif "perf" in each_data:
                    dc_type="conf" if each_data["perf"] == "false" else "perf"
                #add child count
                each_data["spc"] = KubeGlobal.childWriteCount
                #write to file
                upload_dir_code = each_data.pop("upload_dir_code")
                if AgentConstants.AGENT_UPLOAD_PROPERTIES_MAPPER[upload_dir_code]["content_type"] == "application/json":
                    AgentLogger.log(AgentLogger.DA,'Instant Json Data Upload - {}'.format(upload_dir_code))
                    AgentUtil.UploadUtil.uploadInstantJsonData(AgentConstants.AGENT_UPLOAD_PROPERTIES_MAPPER[upload_dir_code], each_data)
                else:
                    status,file_name = saveKubeData(each_data, dc_type, upload_dir_code)
                    data_files_path_list[upload_dir_code] = (data_files_path_list[upload_dir_code] + [file_name]) if upload_dir_code in data_files_path_list else [file_name]
                    AgentLogger.log(AgentLogger.DA,'Kube filename - {0}'.format(file_name))
            #zip file
            if data_files_path_list:
                for upload_code, file_list in data_files_path_list.items():
                    ZipUtil.zipFilesAtInstance([file_list],AgentConstants.AGENT_UPLOAD_PROPERTIES_MAPPER[upload_code])
        else:
            AgentLogger.log(AgentLogger.DA,'WriteDataToFile :: data is empty')
    except Exception as e:
        AgentLogger.log(AgentLogger.KUBERNETES,'WriteDataToFile -> Exception -> {0}'.format(e))

def saveKubeData(kube_data, dc_type, upload_dir_code):
    status = True
    file_name = None
    try:
        kube_data['MSPCUSTOMERID'] = AgentConstants.CUSTOMER_ID
        kube_data['AGENTKEY'] = AgentUtil.AGENT_CONFIG.get('AGENT_INFO', 'agent_key')
        file_name = FileUtil.getUniqueFileName(AgentUtil.AGENT_CONFIG.get('AGENT_INFO', 'agent_key'), dc_type)
        if file_name:
            file_path = os.path.join(AgentConstants.AGENT_UPLOAD_PROPERTIES_MAPPER[upload_dir_code]['data_path'], file_name)
            file_obj = AgentUtil.FileObject()
            file_obj.set_fileName(file_name)
            file_obj.set_filePath(file_path)
            file_obj.set_data(kube_data)
            file_obj.set_dataType('json' if type(kube_data) is dict else "xml")
            file_obj.set_mode('wb')
            file_obj.set_dataEncoding('UTF-16LE')
            file_obj.set_loggerName(AgentLogger.DA)
            status, file_path = FileUtil.saveData(file_obj)
    except Exception as e:
        AgentLogger.log([AgentLogger.KUBERNETES,AgentLogger.STDERR], '*************************** Exception while saving kubernetes collected data in data directory : '+'*************************** '+ repr(e) + '{}'.format(traceback.format_exc()))
        traceback.print_exc()
        status = False
    return status, file_name




"""
K8s Discovery Flow Start
"""
@KubeUtil.exception_handler
def discover_kubernetes(register=True):
    AgentLogger.log(AgentLogger.KUBERNETES, 'discovering kubernetes....')

    KubeUtil.get_bearer_token()
    KubeGlobal.kubernetesPresent = False
    control_plane_ip = KubeUtil.get_control_plane_ip()

    cmd = "ps -eF | grep kube"
    boolIsSuccess, cmdOutput = AgentUtil.executeCommand(cmd, AgentLogger.KUBERNETES)
    if cmdOutput:
        AgentLogger.debug(AgentLogger.KUBERNETES, 'DiscoverKubernetes -> process output -> ')
        AgentLogger.debug(AgentLogger.KUBERNETES, cmdOutput)
        if "kube-scheduler" in cmdOutput and "kube-controller-manager" in cmdOutput and "kube-apiserver" in cmdOutput:
            AgentLogger.log(AgentLogger.KUBERNETES, 'DiscoverKubernetes -> kubeproxy and kubelet running ')
            KubeGlobal.kubernetesPresent = True
            KubeGlobal.nodeType = "MasterNode"
        if "kube-proxy" in cmdOutput and "kubelet" in cmdOutput:
            AgentLogger.log(AgentLogger.KUBERNETES, 'DiscoverKubernetes -> kubeproxy and kubelet running ')
            KubeGlobal.kubernetesPresent = True
            KubeGlobal.nodeType = "WorkerNode"

    if not check_openshift_cluster():
        # to check from container agents
        if not KubeGlobal.kubernetesPresent:
            try:
                mountPath = "/host/proc"
                process_list = AgentUtil.process_through_mount(mountPath)
                for process in process_list:
                    AgentLogger.debug(AgentLogger.KUBERNETES, process)
                    try:
                        if "kubelet" in process and "--kubeconfig" in process:
                            KubeGlobal.kubernetesPresent = True
                            KubeGlobal.nodeType = "WorkerNode"
                            KubeGlobal.isContainerAgent = True
                            cmdOutput = process
                            break
                    except Exception as e:
                        traceback.print_exc()
            except Exception as e:
                AgentLogger.log(AgentLogger.KUBERNETES, "Exception while identifying Kube components through process {}".format(e))
                traceback.print_exc()

    if not KubeGlobal.clusterDN:
        KubeUtil.get_cluster_name_from_cloud_apis()

    if KubeGlobal.fargate or KubeGlobal.gkeAutoPilot:
        KubeGlobal.kubernetesPresent = True
        KubeGlobal.nodeType = "WorkerNode"
        KubeGlobal.kubeServer = control_plane_ip
        KubeGlobal.kubeCluster = "EKS_FARGATE" if KubeGlobal.fargate else "GKE_AUTOPILOT"

        if not KubeGlobal.clusterDN:
            KubeGlobal.clusterDN = KubeGlobal.kubeServer

    if KubeGlobal.kubernetesPresent and cmdOutput:
        # get kubelet.conf file location
        if "--kubeconfig=" in cmdOutput:
            for temp in cmdOutput.split(' '):
                if "--kubeconfig=" in temp:
                    confLoc = temp.split('=')[1]
                    AgentLogger.debug(AgentLogger.KUBERNETES, 'confLoc - {0}'.format(confLoc))
                    get_kubernetes_cluster_details(confLoc)
                    break
        elif "--kubeconfig" in cmdOutput:
            AgentLogger.debug(AgentLogger.KUBERNETES, '--kubeconfig present')
            flag = 0
            for temp in cmdOutput.split(' '):
                if flag == 1:
                    confLoc = temp
                    AgentLogger.debug(AgentLogger.KUBERNETES, 'confLoc - {0}'.format(confLoc))
                    get_kubernetes_cluster_details(confLoc)
                    break
                if "--kubeconfig" in temp:
                    flag = 1

            if not KubeGlobal.kubeServer or "127.0.0.1" in KubeGlobal.kubeServer or "localhost" in KubeGlobal.kubeServer:
                KubeGlobal.kubeServer = control_plane_ip
        elif control_plane_ip:
            KubeGlobal.kubernetesPresent = True
            KubeGlobal.nodeType = "WorkerNode"
            KubeGlobal.kubeServer = control_plane_ip
            KubeGlobal.kubeCluster = "default-cluster"
        else:
            AgentLogger.log(AgentLogger.KUBERNETES, 'Kubernetes not present')

    if not (KubeGlobal.kubeServer and KubeGlobal.kubernetesPresent) and control_plane_ip:
        KubeGlobal.kubernetesPresent = True
        KubeGlobal.nodeType = "WorkerNode"
        KubeGlobal.kubeServer = control_plane_ip
        KubeGlobal.kubeCluster = "default-cluster"

    if register and KubeGlobal.kubernetesPresent:
        KubeUtil.check_cluster_distribution()
        kubeKey = send_kube_discovery()
        if kubeKey and kubeKey != KubeGlobal.mid:
            AgentLogger.log(AgentLogger.KUBERNETES, "Kubernetes key received from server : " + str(kubeKey) + "\n")
            # set the monkey and make the moitor active
            KubeGlobal.set_mid(kubeKey)
            KubeGlobal.set_mon_status(1)
            # write to configFile
            KubeUtil.write_kubernetes_dc_config_to_file({KubeGlobal.configMidParam: kubeKey, KubeGlobal.configStatusParam: "1"})
        elif kubeKey == 'None':
            AgentLogger.log([AgentLogger.KUBERNETES, AgentLogger.CRITICAL], "KUBERNETES KEY not returned from server \n")

@KubeUtil.exception_handler
def get_kubernetes_cluster_details(confLoc):
    if KubeGlobal.isContainerAgent:
        AgentLogger.log(AgentLogger.KUBERNETES, 'get_kubernetes_cluster_details - containerAgent')
        confLoc = "/host/" + confLoc
    cmd = "cat " + confLoc
    AgentLogger.log(AgentLogger.KUBERNETES, 'confLoc - {0}'.format(cmd))
    boolIsSuccess, cmdOutput = AgentUtil.executeCommand(cmd, AgentLogger.KUBERNETES)
    if cmdOutput:
        AgentLogger.debug(AgentLogger.KUBERNETES, 'GetKubernetesClusterName -> process output -> {0}'.format(cmdOutput))
        for line in cmdOutput.split("\n"):
            if "server:" in line:
                KubeGlobal.kubeServer = line.split(':', 1)[1]
                AgentLogger.log(AgentLogger.KUBERNETES, 'GetKubernetesClusterName -> {0}'.format(KubeGlobal.kubeServer))
            if "cluster" in line:
                KubeGlobal.kubeCluster = line.split(':', 1)[1]
            if "namespace" in line:
                KubeGlobal.kubeNamespace = line.split(':', 1)[1]
    # temporary check for rancher setup
    if "KUBE_API_SERVER" in os.environ:
        KubeGlobal.kubeServer = os.environ["KUBE_API_SERVER"]
        AgentLogger.log(AgentLogger.KUBERNETES, 'Api Server Name taken from ENV {}'.format(KubeGlobal.kubeServer))

def check_openshift_cluster():
    is_openshift = False
    try:
        AgentLogger.log(AgentLogger.KUBERNETES,"***** CAME FIRST TO CHECK OPENSHIFT *****")
        status_code, json=KubeUtil.curl_api_with_token(KubeGlobal.host+'/apis/config.openshift.io/v1/clusterversions')
        if status_code == 200 and "items" in json and "spec" in json["items"][0] and "clusterID" in json["items"][0]["spec"]:
            cluster_id=json["items"][0]["spec"]["clusterID"] # can be sent while registering openshift cluster
            KubeGlobal.kubeCluster = "OpenShift"
            KubeGlobal.kubeUniqueID = cluster_id
            is_openshift = True
            KubeGlobal.kubernetesPresent = True
            KubeGlobal.isContainerAgent = True

            status = server_api_json = None
            status, server_api_json = KubeUtil.curl_api_with_token(KubeGlobal.host + "/apis/config.openshift.io/v1/infrastructures")
            if status and server_api_json:
                cluster_status = server_api_json["items"][0]["status"]
                KubeGlobal.kubeServer = cluster_status["apiServerURL"] if "apiServerURL" in cluster_status else None
                KubeGlobal.kubePlatform = cluster_status["platform"] if "platform" in cluster_status else None
            else:
                AgentLogger.log(AgentLogger.KUBERNETES,"***** Exception while getting openshift cluster server api ***** :: Status - {} :: Response :: {}".format(status, server_api_json))
                KubeGlobal.kubeServer = KubeUtil.get_cluster_DNS()


            status = node_list_json = None
            status, node_list_json = KubeUtil.curl_api_with_token(KubeGlobal.host + "/api/v1/nodes?fieldSelector=metadata.name=" + KubeGlobal.nodeName)
            if status and node_list_json:
                current_node = node_list_json["items"][0]
                node_metadata = current_node["metadata"]
                node_labels = node_metadata["labels"]
                if "node.openshift.io/os_id" in node_labels:
                    KubeGlobal.kubeCluster = "OpenSift"
                    if "node-role.kubernetes.io/control-plane" in node_labels and "node-role.kubernetes.io/master" in node_labels:
                        KubeGlobal.nodeType = "control-plane,master"
                    elif "node-role.kubernetes.io/infra" in node_labels and "node-role.kubernetes.io/worker" in node_labels:
                        KubeGlobal.nodeType = "infra,worker"
                    elif "node-role.kubernetes.io/master" in node_labels:
                        KubeGlobal.nodeType = "master"
                    elif "node-role.kubernetes.io/control-plane" in node_labels:
                        KubeGlobal.nodeType = "control-plane"
                    elif "node-role.kubernetes.io/infra" in node_labels:
                        KubeGlobal.nodeType = "infra"
                    elif "node-role.kubernetes.io/worker" in node_labels:
                        KubeGlobal.nodeType = "worker"
                    else:
                        # no other case, but still don't want to break old flow
                        KubeGlobal.nodeType = "WorkerNode"
            else:
                AgentLogger.log(AgentLogger.KUBERNETES,"***** Exception while getting current node role ***** :: Status - {} :: Response :: {}".format(status, server_api_json))
                KubeGlobal.nodeType = "WorkerNode"


    except Exception as e:
        is_openshift = False
        AgentLogger.log(AgentLogger.KUBERNETES, '***** Exception while discovering Openshift Cluster ***** :: Error - {0}'.format(e))
        traceback.print_exc()
    finally:
        return is_openshift

def send_kube_discovery():
    dict_requestParameters = {}
    str_url = None
    kubeKey = None
    try:
        dict_requestParameters['agentKey'] = AgentUtil.AGENT_CONFIG.get('AGENT_INFO', 'agent_key')
        dict_requestParameters['CUSTOMERID'] = AgentConstants.CUSTOMER_ID
        # dict_requestParameters['productVersion'] = AgentUtil.AGENT_CONFIG.get('AGENT_INFO', 'agent_version')
        dict_requestParameters['kubernetes'] = 'true'
        dict_requestParameters['bno'] = AgentConstants.AGENT_VERSION
        dict_requestParameters['REDISCOVER'] = "TRUE"
        if KubeGlobal.kubeServer:
            dict_requestParameters['kubeServer'] = KubeGlobal.kubeServer
        if KubeGlobal.kubeCluster:
            dict_requestParameters['kubeCluster'] = KubeGlobal.kubeCluster
        if KubeGlobal.kubeUniqueID:
            pass
            #dict_requestParameters['ClusterUID'] = KubeGlobal.kubeUniqueID
        if KubeGlobal.kubePlatform:
            pass
            #dict_requestParameters['kubePlatform'] = KubeGlobal.kubePlatform
        if KubeGlobal.nodeType:
            dict_requestParameters['kubeNodeType'] = KubeGlobal.nodeType
        if KubeGlobal.clusterDN and KubeGlobal.clusterDN != '""':
            dict_requestParameters['kubeClusterDN'] = KubeGlobal.clusterDN
        str_servlet = AgentConstants.APPLICATION_DISCOVERY_SERVLET
        if not dict_requestParameters == None:
            str_requestParameters = urlencode(dict_requestParameters)
            str_url = str_servlet + str_requestParameters
        requestInfo = CommunicationHandler.RequestInfo()
        requestInfo.set_loggerName(AgentLogger.KUBERNETES)
        requestInfo.set_method(AgentConstants.HTTP_GET)
        requestInfo.set_url(str_url)
        # requestInfo.set_data(str_dataToSend)
        requestInfo.set_dataType('application/json')
        requestInfo.add_header("Content-Type", 'application/json')
        requestInfo.add_header("Accept", "text/plain")
        requestInfo.add_header("Connection", 'close')
        AgentLogger.log(AgentLogger.KUBERNETES,"=========================== STARTING KUBERNETES REGISTRATION ========================")
        (bool_isSuccess, errorCode, dict_responseHeaders, dict_responseData) = CommunicationHandler.sendRequest(requestInfo)
        if dict_responseHeaders and 'kubeKey' in dict_responseHeaders:
            kubeKey = dict_responseHeaders['kubeKey']
        CommunicationHandler.handleResponseHeaders(dict_responseHeaders, dict_responseData, 'KUBERNETES DISCOVERY')
        if bool_isSuccess:
            AgentLogger.log(AgentLogger.KUBERNETES, " Server accepted data ")
    except Exception as e:
        AgentLogger.log(AgentLogger.KUBERNETES, " Exception while sending data {0}".format(e))
        traceback.print_exc()
    return kubeKey
"""
K8s Discovery Flow End
"""