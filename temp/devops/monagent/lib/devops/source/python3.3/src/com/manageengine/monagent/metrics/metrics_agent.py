#$Id$
import sys
import os
import traceback
import time
from threading import Thread
import importlib

AGENT_SRC_CHECK = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(sys.argv[0])))))
splitted_paths = os.path.split(AGENT_SRC_CHECK)
if splitted_paths[1].lower() == "com":
    AGENT_SOURCE_DIR = os.path.dirname(AGENT_SRC_CHECK)
    sys.path.insert(0,AGENT_SOURCE_DIR)

from com.manageengine.monagent.metrics.daemon import Daemon
from com.manageengine.monagent.metrics import metrics_config_parser,metrics_constants,metrics_logger,metrics_util
from com.manageengine.monagent.metrics import uploader
from com.manageengine.monagent.metrics import executor

metrics_logger.initialize()

class MetricsDaemon(Daemon):
    def run(self):
        try:
            metrics_util.create_upload_directories()
            metrics_util.load_server_configurations(metrics_constants.SERVER_CONFIG_FILE)
            metrics_util.init_ssl_context()
            executor.initialize()
            uploader.initialize()
        except Exception as e:
            traceback.print_exc()

def run_server():
    try:
        action=sys.argv[1]
        metric_daemon = MetricsDaemon(metrics_constants.METRICS_DAEMON_PID_FILE)
        if action == 'start':
            metric_daemon.start()
        elif action == 'stop':
            metric_daemon.stop()
        elif action == 'status':
            metric_daemon.status()
        elif action == 'restart':
            metric_daemon.stop()
            metric_daemon.start()
        else:
            metrics_logger.warnlog('action {} not supported'.format(action))
    except IndexError as e:
        metrics_logger.errlog("Usage :For StatsD use start or stop command")
    except Exception as e:
        metrics_logger.errlog('Exception in  run server : {}'.format(e))
        traceback.print_exc()            
        
if __name__== "__main__":    
    run_server()

