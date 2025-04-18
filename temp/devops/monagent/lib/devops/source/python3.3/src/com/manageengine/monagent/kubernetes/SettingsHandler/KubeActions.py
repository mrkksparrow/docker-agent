import time

from com.manageengine.monagent.kubernetes import KubeGlobal, KubeUtil, KubeDCExecutor
from com.manageengine.monagent.kubernetes.ClusterAgent import ClusterAgentUtil
from com.manageengine.monagent.kubernetes.Logging import KubeLogger as AgentLogger
import json
import traceback
import os
import sys

try:
    from six.moves.urllib.parse import urlencode
except Exception:
    pass


def kube_agent_action_handler(wms_response):
    try:
        req_type = wms_response['REQUEST_TYPE']
        if req_type == 'KUBE_AGENT_OPS':
            if 'CLUSTER_AGENT_VERSION' in wms_response or 'NODE_AGENT_VERSION' in wms_response:
                update_agent_version(wms_response)
            if 'UPGRADE_CLUSTER_AGENT' in wms_response:
                ClusterAgentUtil.upgrade_cluster_agent()
            if 'UPGRADE_NODE_AGENT' in wms_response and os.path.exists(KubeGlobal.NODE_AGENT_UPGRADE_LOCK_FILE):
                os.remove(KubeGlobal.NODE_AGENT_UPGRADE_LOCK_FILE)
            if 'SETTINGS' in wms_response:
                update_settings(json.loads(wms_response['SETTINGS']))
            if '1MIN' in wms_response:
                update_settings(json.loads(wms_response['1MIN']), '1MIN')
            if 'SERVER_TERMINATION' in wms_response and wms_response['SERVER_TERMINATION'] == 'true':
                remove_server_from_configmap(wms_response)
            if 'STOP_METRICS_AGENT' in wms_response:
                deactivate_metrics()
        elif req_type == 'KUBE_YAML_CONFIG':
            if 'SUCCESS_JSON' in wms_response and wms_response['SUCCESS_JSON']:
                filter_failed_yaml_resources(json.loads(wms_response['SUCCESS_JSON']))
            if 'ONDEMAND_YAML_REQUEST' in wms_response and wms_response['ONDEMAND_YAML_REQUEST']:
                filter_failed_yaml_resources(json.loads(wms_response['ONDEMAND_YAML_REQUEST']), False)
                KubeUtil.execute_dctask_ondemand('yamlfetcher')
            if 'SUPPORTED_TYPES' in wms_response and wms_response['SUPPORTED_TYPES']:
                KubeGlobal.YAML_SUPPORTED_TYPES = wms_response['SUPPORTED_TYPES'].split(',')
        elif req_type == 'KUBE_ACTION_REQUEST' and KubeUtil.is_eligible_to_execute('resourcedependency_ondemand', time.time()):
            get_kube_action_servlet_response(wms_response['ACTIONTYPE'])
    except Exception:
        traceback.print_exc()
    finally:
        if 'FETCH_CONFIG_MAP_DATA' in wms_response:
            load_configmap_data()


def update_agent_version(wms_response):
    data = {
        'data': {}
    }
    if 'CLUSTER_AGENT_VERSION' in wms_response:
        data['data']['CLUSTER_AGENT_VERSION'] = wms_response['CLUSTER_AGENT_VERSION']

    if 'NODE_AGENT_VERSION' in wms_response:
        data['data']['NODE_AGENT_VERSION'] = wms_response['NODE_AGENT_VERSION']

    KubeUtil.update_s247_configmap(data)


def update_settings(settings_json, key_name='SETTINGS'):
    response = fetch_existing_cm_data()
    if response and key_name in response:
        existing_settings = json.loads(response[key_name])

        for key, value in settings_json.items():
            existing_settings[key] = value

        KubeUtil.update_s247_configmap({
            'data': {
                key_name: json.dumps(existing_settings)
            }
        })


def fetch_existing_cm_data():
    # fetching existing configmap values
    status, response = KubeUtil.curl_api_with_token(KubeGlobal.apiEndpoint + KubeGlobal.s247ConfigMapPath)
    if status == 200:
        return response['data']
    return None


def load_configmap_data():
    response = fetch_existing_cm_data()
    if response:
        KubeGlobal.CLUSTER_AGENT_STATS['cm_data'] = response


def remove_server_from_configmap(wms_response):
    KubeUtil.update_s247_configmap({
        'data': {
            wms_response['TERMINATED_NODE']: None
        }
    })

def filter_failed_yaml_resources(succeeded_resource, succeeded=True):
    from com.manageengine.monagent.kubernetes.Collector import YAMLFetcher
    YAMLFetcher.SUCCEEDED_RESOURCES = KubeUtil.MergeDataDictionaries(YAMLFetcher.SUCCEEDED_RESOURCES, succeeded_resource)
    if not succeeded:
        for res_type, resources in KubeGlobal.kubeIds.items():
            for res_name, res_config in resources.items():
                if res_config['id'] in succeeded_resource:
                    YAMLFetcher.SUCCEEDED_RESOURCES.pop(res_config['id'], None)

def get_kube_action_servlet_response(action_type):
    try:
        from com.manageengine.monagent.communication import CommunicationHandler
        from com.manageengine.monagent import AgentConstants

        str_url = KubeGlobal.KUBE_ACTION_SERVLET + urlencode({
            'bno': AgentConstants.AGENT_VERSION,
            'CUSTOMERID': AgentConstants.CUSTOMER_ID,
            'AGENTKEY': getattr(sys.modules['com.manageengine.monagent.util.AgentUtil'], 'AGENT_CONFIG').get('AGENT_INFO', 'agent_key'),
            'AGENTUNIQUEID': getattr(sys.modules['com.manageengine.monagent.util.AgentUtil'], 'AGENT_CONFIG').get('AGENT_INFO', 'agent_unique_id'),
            'ACTIONTYPE': action_type,
            'CLUSTERKEY': KubeGlobal.mid
        })

        requestInfo = CommunicationHandler.RequestInfo()
        requestInfo.set_loggerName(AgentLogger.KUBERNETES)
        requestInfo.set_method('GET')
        requestInfo.set_url(str_url)
        requestInfo.add_header("Content-Type", 'application/json')
        requestInfo.add_header("Accept", "text/plain")
        requestInfo.add_header("Connection", 'close')
        (isSuccess, int_errorCode, dict_responseHeaders, dict_responseData) = CommunicationHandler.sendRequest(requestInfo)
        AgentLogger.log(AgentLogger.KUBERNETES, 'KubeActionServlet -> Status code - {}, Response - {}\n'.format(int_errorCode, dict_responseData))

        if isSuccess and dict_responseData:
            response_json = json.loads(dict_responseData)
            if str(action_type) == '1':
                KubeGlobal.CLUSTER_POD_LIST = response_json.get("Pods", [])
                KubeUtil.execute_dctask_ondemand('resourcedependency')
    except Exception as e:
        AgentLogger.log(AgentLogger.KUBERNETES, 'Exception in KubeActionServlet processing !!! - {}'.format(e))
        traceback.print_exc()


def set_send_config(sendConfig):
    try:
        if KubeGlobal.sendConfig != sendConfig.lower():
            AgentLogger.log(AgentLogger.KUBERNETES, '******** setting send config to - {0} **********'.format(sendConfig))
            KubeGlobal.sendConfig = sendConfig.lower()
            KubeDCExecutor.create_dc_objs()
            KubeUtil.write_kubernetes_dc_config_to_file({KubeGlobal.sendConfigParam: KubeGlobal.sendConfig})
        else:
            AgentLogger.log(AgentLogger.KUBERNETES, "setSendConfig :: sendconfig already set to - {0}".format(sendConfig))
    except Exception as e:
        AgentLogger.log(AgentLogger.KUBERNETES, 'setSendConfig -> Exception -> {0}'.format(e))


def set_send_perf(sendPerf):
    try:
        if KubeGlobal.sendPerf != sendPerf.lower():
            AgentLogger.log(AgentLogger.KUBERNETES, '********** setting send perf to - {0} ***********'.format(sendPerf))
            KubeGlobal.sendPerf = sendPerf.lower()
            KubeUtil.write_kubernetes_dc_config_to_file({KubeGlobal.sendPerfParam: KubeGlobal.sendPerf})
        else:
            AgentLogger.log(AgentLogger.KUBERNETES, "setSendPerf :: sendPerf already set to - {0}".format(KubeGlobal.sendPerf))
    except Exception as e:
        AgentLogger.log(AgentLogger.KUBERNETES, 'setSendPerf -> Exception -> {0}'.format(e))


def set_config_dc_interval(interval):  # interval in mins
    try:
        AgentLogger.log(AgentLogger.KUBERNETES, 'settingconfig dc interval to - {0} mins'.format(interval))
        if KubeGlobal.sendConfigDataInterval != interval:
            KubeGlobal.sendConfigDataInterval = interval
            KubeUtil.write_kubernetes_dc_config_to_file({KubeGlobal.configDCIntervalParam: interval})
        else:
            AgentLogger.log(AgentLogger.KUBERNETES,'set_config_dc_interval :: sendConfigDataInterval already set to - {0}'.format(KubeGlobal.sendConfigDataInterval))
    except Exception as e:
        AgentLogger.log(AgentLogger.KUBERNETES, 'set_config_dc_interval -> Exception -> {0}'.format(e))


def set_child_write_count(count):
    try:
        AgentLogger.log(AgentLogger.KUBERNETES, 'set_child_write_count - {0}'.format(count))
        if KubeGlobal.childWriteCount != count:
            KubeGlobal.childWriteCount = count
            KubeUtil.write_kubernetes_dc_config_to_file({KubeGlobal.childWriteCountParam: count})
        else:
            AgentLogger.log(AgentLogger.KUBERNETES, 'set_child_write_count :: childWriteCount already set to - {0}'.format(KubeGlobal.childWriteCount))
    except Exception as e:
        AgentLogger.log(AgentLogger.KUBERNETES, 'set_child_write_count -> Exception -> {0}'.format(e))


def set_api_server_endpoint_url(apiEndpoint):
    try:
        AgentLogger.log(AgentLogger.KUBERNETES, 'set_api_server_endpoint_url - {0}'.format(apiEndpoint))
        if KubeGlobal.apiEndpoint != apiEndpoint:
            KubeGlobal.apiEndpoint = apiEndpoint
            KubeUtil.write_kubernetes_dc_config_to_file({KubeGlobal.apiEndpointParam: apiEndpoint})
        else:
            AgentLogger.log(AgentLogger.KUBERNETES,'set_api_server_endpoint_url :: apiEndpoint already set to - {0}'.format(KubeGlobal.apiEndpoint))
    except Exception as e:
        AgentLogger.log(AgentLogger.KUBERNETES, 'set_api_server_endpoint_url -> Exception -> {0}'.format(e))


def set_cluster_display_name(clusterDN):
    try:
        AgentLogger.log(AgentLogger.KUBERNETES, 'set_cluster_display_name - {0}'.format(clusterDN))
        if KubeGlobal.clusterDN != clusterDN:
            KubeGlobal.clusterDN = clusterDN
            KubeUtil.write_kubernetes_dc_config_to_file({KubeGlobal.clusterDNParam: clusterDN})
        else:
            AgentLogger.log(AgentLogger.KUBERNETES,'set_cluster_display_name :: clusterDN already set to - {0}'.format(KubeGlobal.clusterDN))
    except Exception as e:
        AgentLogger.log(AgentLogger.KUBERNETES, 'set_cluster_display_name -> Exception -> {0}'.format(e))


def set_kube_state_metrics_url(kubeStateMetricsUrl):
    try:
        AgentLogger.log(AgentLogger.KUBERNETES, 'set_kube_state_metrics_url - {0}'.format(kubeStateMetricsUrl))
        if KubeGlobal.kubeStateMetricsUrl != kubeStateMetricsUrl:
            KubeGlobal.kubeStateMetricsUrl = kubeStateMetricsUrl
            KubeUtil.write_kubernetes_dc_config_to_file({KubeGlobal.kubeStateMetricsParam: kubeStateMetricsUrl})
        else:
            AgentLogger.log(AgentLogger.KUBERNETES, 'set_kube_state_metrics_url :: kubeStateMetricsUrl already set to - {0}'.format(KubeGlobal.kubeStateMetricsUrl))
    except Exception as e:
        AgentLogger.log(AgentLogger.KUBERNETES, 'set_kube_state_metrics_url -> Exception -> {0}'.format(e))


def set_event_settings(value):
    try:
        AgentLogger.log(AgentLogger.KUBERNETES,'setting events settings to - {}'.format(value))
        if KubeGlobal.EVENTS_ENABLED != value.lower():
            KubeGlobal.EVENTS_ENABLED = value.lower()
            KubeUtil.write_kubernetes_dc_config_to_file({KubeGlobal.eventsEnabledParam: KubeGlobal.EVENTS_ENABLED})
    except Exception as e:
        AgentLogger.log(AgentLogger.KUBERNETES, "Exc -> setEventsSettings -> {}".format(e))


def change_kubernetes_perf_poll_interval(POLL_INTERVAL_ACTION_DICT):
    try:
        for res_type, value in POLL_INTERVAL_ACTION_DICT.items():
            KubeGlobal.KUBE_GLOBAL_SETTINGS[res_type] = value

        KubeUtil.write_kubernetes_dc_config_to_file(KubeGlobal.KUBE_GLOBAL_SETTINGS, 'poll_interval')
    except Exception as e:
        AgentLogger.log(AgentLogger.KUBERNETES, 'Exception -> change_kubernetes_perf_poll_interval {0}'.format(e))

def change_kubernetes_instant_resource_discovery(INSTANT_DISCOVERY_ACTION_DICT):
    try:
        for res_type, value in KubeGlobal.KUBE_INSTANT_DISCOVERY_SETTINGS.items():
            KubeGlobal.KUBE_INSTANT_DISCOVERY_SETTINGS[res_type] = INSTANT_DISCOVERY_ACTION_DICT.get(res_type, value)

        KubeUtil.write_kubernetes_dc_config_to_file(KubeGlobal.KUBE_INSTANT_DISCOVERY_SETTINGS, 'resource_discovery')
    except Exception as e:
        AgentLogger.log(AgentLogger.KUBERNETES, 'Exception -> change_kubernetes_perf_poll_interval {0}'.format(e))

@KubeUtil.exception_handler
def deactivate_metrics():
    from com.manageengine.monagent.util.MetricsUtil import stop_prometheus_monitoring
    stop_prometheus_monitoring()
