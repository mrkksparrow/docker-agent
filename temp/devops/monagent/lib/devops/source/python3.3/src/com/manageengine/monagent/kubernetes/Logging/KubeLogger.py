import os
import traceback
import logging

Logger = None
LOG_DIR = None
KUBERNETES = 'KUBERNETES'
DA = 'DA'
APPS = 'APPS'

console_logger = logging.getLogger('K8s')
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
handler.setLevel(logging.INFO)
console_logger.addHandler(handler)
console_logger.setLevel(logging.INFO)


class KubeLogger:
    def __init__(self, is_cluster_agent):
        try:
            if is_cluster_agent:
                from com.manageengine.monagent.kubernetes.Logging import LoggerUtil
                self.common_logger = LoggerUtil
            else:
                from com.manageengine.monagent.logger import AgentLogger
                self.common_logger = AgentLogger
        except Exception as e:
                traceback.print_exc()

    def log(self, file_name, log_msg):
        try:
            self.common_logger.log(getattr(self.common_logger, file_name), log_msg)
        except Exception as e:
            traceback.print_exc()

    def debug(self, file_name, log_msg):
        try:
            self.common_logger.debug(getattr(self.common_logger, file_name), log_msg)
        except Exception as e:
            traceback.print_exc()


def initialize():
    global Logger
    Logger = KubeLogger(0 if os.environ.get("CLUSTER_AGENT") != "true" else 1)


def log(file_name, log_msg):
    global Logger
    Logger.log(file_name, log_msg)


def debug(file_name, log_msg):
    global Logger
    Logger.debug(file_name, log_msg)
