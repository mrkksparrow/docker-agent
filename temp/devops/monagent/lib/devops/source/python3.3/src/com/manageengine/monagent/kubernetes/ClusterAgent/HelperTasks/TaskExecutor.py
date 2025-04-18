import time
import traceback
from abc import abstractmethod
from com.manageengine.monagent.kubernetes import KubeGlobal, KubeUtil
from com.manageengine.monagent.kubernetes.Logging import KubeLogger
from com.manageengine.monagent.kubernetes.ClusterAgent.ClusterAgentUtil import ReadOrWriteWithFileLock


"""
TaskExecutor is an Abstract class used for creating json that needs to be used for handling cluster agent requests
"""

class TaskExecutor:
    def __init__(self):
        self.task_name = self.__class__.__name__.lower()

    @abstractmethod
    def task_definition(self):
        """
        :returns dict contains {file_name : content, ...}
        """

    def execute(self, eligibility_check_needed=True):
        try:
            start_time = time.time()
            if eligibility_check_needed and not KubeUtil.is_eligible_to_execute(self.task_name, KubeGlobal.DC_START_TIME):
                return False

            for file_name, content in self.task_definition().items():
                with ReadOrWriteWithFileLock(KubeGlobal.PARSED_DATA_FOLDER_PATH + '/' + file_name, 'w') as write_obj:
                    write_obj.write_json(content)

            time_taken = time.time() - start_time
            KubeGlobal.CLUSTER_AGENT_STATS['helpertasks'][self.task_name] = time_taken
            KubeLogger.console_logger.info('Time taken for executing {} - {}'.format(self.task_name, time_taken))
        except Exception as e:
            KubeLogger.console_logger.warning('Exception -> {} -> {}'.format(self.task_name, e))

