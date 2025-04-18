'''
@author: bharath.veerakumar

Created on Feb 20 2024
'''


import time
import os
import sys
from flask import Flask
from flask import request

if os.environ.get("CLUSTER_AGENT") != "true":
    sys.stdout.write("\n***** CLUSTER_AGENT env is not set *****\n")
    sys.exit()

CLUSTER_AGENT_SRC = '/home/site24x7/monagent/lib/devops/source/python3.3/src'
CONF_FOLDER_PATH = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(CLUSTER_AGENT_SRC))))) + '/conf'
CLUSTER_AGENT_WORKING_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(CLUSTER_AGENT_SRC)))))
LOGS_FOLDER_PATH = CLUSTER_AGENT_WORKING_DIR + '/logs'
PARSED_DATA_FOLDER_PATH = CLUSTER_AGENT_WORKING_DIR + '/parsed_data'
DETAILS_LOGS_FOLDER_PATH = LOGS_FOLDER_PATH + '/details'

if not os.path.exists(CONF_FOLDER_PATH):
    os.makedirs(CONF_FOLDER_PATH)

if not os.path.isfile(CONF_FOLDER_PATH + '/upgrade_lock_file.txt'):
    with open(CONF_FOLDER_PATH + '/upgrade_lock_file.txt', 'w') as fp:
        pass

if not os.path.exists(DETAILS_LOGS_FOLDER_PATH):
    os.makedirs(DETAILS_LOGS_FOLDER_PATH)

if not os.path.exists(PARSED_DATA_FOLDER_PATH):
    os.makedirs(PARSED_DATA_FOLDER_PATH)

sys.path.append(CLUSTER_AGENT_SRC)

from com.manageengine.monagent.kubernetes.Logging import LoggerUtil, KubeLogger
LoggerUtil.initialize_cluster_agent_logging(CONF_FOLDER_PATH + '/logging.xml', LOGS_FOLDER_PATH)
KubeLogger.initialize()
KubeLogger.log(KubeLogger.KUBERNETES, '********* Starting Cluster Agent *********')

from com.manageengine.monagent.kubernetes import KubeGlobal
KubeGlobal.set_cluster_agent_constants(CLUSTER_AGENT_SRC)

from com.manageengine.monagent.kubernetes import KubeUtil
from com.manageengine.monagent.kubernetes.SettingsHandler import Initializer

app = Flask(__name__)


@app.before_request
def pre_requisites():
    if "/ca/health_check" not in request.url:
        # DC Prerequisites
        if KubeUtil.is_eligible_to_execute("dcinit", time.time()):
            KubeUtil.get_bearer_token()
            KubeUtil.getKubeAPIServerEndPoint()
            KubeUtil.discover_ksm_url()
            Initializer.fetch_global_settings_from_configmap()
            Initializer.fetch_1min_settings_from_configmap()
            Initializer.find_s247_configmap_namespace()

        # Checking remote ip with the site24x7-agent pod (Node Agent) IP
        if KubeUtil.is_eligible_to_execute("skip_podip_check"):
            status, resp = KubeUtil.curl_api_with_token(KubeGlobal.apiEndpoint + '/api/v1/pods?fieldSelector=status.podIP={}&labelSelector=app%3Dsite24x7-agent'.format(request.remote_addr))
            if status == 200:
                if len(resp.get('items', [])) == 0 or 'site24x7-agent' not in resp['items'][0]['metadata']['name']:
                    return "Success", 200


@KubeUtil.exception_handler
def register_blueprints():
    global app
    from com.manageengine.monagent.kubernetes.ClusterAgent.Controller import ClusterAgentController, DataParsingController
    app.register_blueprint(ClusterAgentController.blp)
    app.register_blueprint(DataParsingController.blp)


register_blueprints()
