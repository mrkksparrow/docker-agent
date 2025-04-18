'''
@author: bharath.veerakumar

Created on Feb 20 2024
'''


import os
import traceback
from flask.blueprints import Blueprint
from com.manageengine.monagent.kubernetes import KubeGlobal
from com.manageengine.monagent.kubernetes.ClusterAgent import ClusterAgentUtil
from com.manageengine.monagent.kubernetes.Logging import KubeLogger

blp = Blueprint("ClusterAgentController", __name__)


@blp.route("/ca/health_check")
def cluster_agent_healthcheck():
    return "Cluster Agent Running Successfully", 200


@blp.route("/ca/liveness_check")
def cluster_agent_livenesscheck():
    return "Cluster Agent Running Successfully", 200


@blp.route("/ca/initiate_agent_upgrade")
def handle_upgrade():
    try:
        # if upgrade lock file exists and the last modified time is > 5 mins, then it is removed
        # After the removal, the main process will get exited for pod restart.
        if os.path.exists(KubeGlobal.CLUSTER_AGENT_UPGRADE_LOCK_FILE) and not ClusterAgentUtil.check_last_mtime(KubeGlobal.CLUSTER_AGENT_UPGRADE_LOCK_FILE, 300):
            os.remove(KubeGlobal.CLUSTER_AGENT_UPGRADE_LOCK_FILE)
            return "Successfully removed the upgrade flag file"
    except Exception as e:
        traceback.print_exc()
        KubeLogger.log(KubeLogger.KUBERNETES, "Exception -> initiate_agent_upgrade -> {}".format(e))
    return "Upgrade File not Found or not Eligible to proceed", 400


@blp.route("/ca/version")
def get_version():
    return KubeGlobal.CLUSTER_AGENT_VERSION
