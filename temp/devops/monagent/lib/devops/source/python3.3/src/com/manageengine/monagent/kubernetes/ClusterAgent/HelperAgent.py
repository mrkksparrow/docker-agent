'''
@author: bharath.veerakumar

Created on Feb 20 2024
'''


import os
import sys
import time
import traceback

CLUSTER_AGENT_SRC = '/home/site24x7/monagent/lib/devops/source/python3.3/src'
CONF_FOLDER_PATH = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(CLUSTER_AGENT_SRC))))) + '/conf'
CLUSTER_AGENT_WORKING_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(CLUSTER_AGENT_SRC)))))
LOGS_FOLDER_PATH = CLUSTER_AGENT_WORKING_DIR + '/logs'

sys.path.append(CLUSTER_AGENT_SRC)

from com.manageengine.monagent.kubernetes.Logging import LoggerUtil, KubeLogger
LoggerUtil.initialize_cluster_agent_logging(CONF_FOLDER_PATH + '/logging.xml', LOGS_FOLDER_PATH)
KubeLogger.initialize()

from com.manageengine.monagent.kubernetes import KubeGlobal
from com.manageengine.monagent.kubernetes import KubeUtil
KubeGlobal.set_cluster_agent_constants(CLUSTER_AGENT_SRC)

from com.manageengine.monagent.kubernetes.ClusterAgent.HelperTasks.KSMProcessor import KSMProcessor
from com.manageengine.monagent.kubernetes.ClusterAgent.HelperTasks.ServiceRelationalDataProcessor import ServiceRelationDataProcessor
from com.manageengine.monagent.kubernetes.ClusterAgent.HelperTasks.KubeletDataPersistence import KubeletDataPersistence
from com.manageengine.monagent.kubernetes.ClusterAgent.ClusterAgentUtil import ReadOrWriteWithFileLock
from com.manageengine.monagent.kubernetes.SettingsHandler import Initializer

TASK_INTERVAL = int(os.environ.get("TASK_INTERVAL", 30))
HELPER_TASK_LIST = [KSMProcessor, ServiceRelationDataProcessor, KubeletDataPersistence]  # add the tasks class object which extends TaskExecutor as base class
DATACOLLECTOR_TASKS = list(filter(lambda dc_obj: dc_obj.is_pre_parsing_needed, KubeGlobal.CLUSTER_AGENT_DC_OBJS_LIST.values()))


def start_watcher_daemon():
    while True:
        try:
            KubeGlobal.DC_START_TIME = time.time()

            # DC Prerequisites
            if KubeUtil.is_eligible_to_execute("dcinit", KubeGlobal.DC_START_TIME):
                KubeUtil.get_bearer_token()
                KubeUtil.getKubeAPIServerEndPoint()
                KubeUtil.discover_ksm_url()
                Initializer.fetch_global_settings_from_configmap()
                Initializer.fetch_1min_settings_from_configmap()

            if not os.path.isfile(CONF_FOLDER_PATH + '/upgrade_lock_file.txt'):
                break

            execute_helper_tasks()
        except Exception as e:
            traceback.print_exc()
            KubeLogger.log(KubeLogger.KUBERNETES, "********** Exception -> Helper Agent Daemon function -> {} **********".format(e))
        time.sleep(TASK_INTERVAL)


@KubeUtil.func_exec_time
def execute_helper_tasks():
    for task in HELPER_TASK_LIST:
        task().execute()

    # writing the Helper Tasks stats
    with ReadOrWriteWithFileLock(KubeGlobal.HELPER_TASK_STATS_FILE, 'w') as write_obj:
        write_obj.write_json(KubeGlobal.CLUSTER_AGENT_STATS['helpertasks'])


if __name__ == "__main__":
    start_watcher_daemon()
