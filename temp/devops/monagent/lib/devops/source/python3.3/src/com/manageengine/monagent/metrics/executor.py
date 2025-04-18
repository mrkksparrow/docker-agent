#$Id$
import traceback
import threading
import os

from com.manageengine.monagent.metrics import metrics_constants
from com.manageengine.monagent.metrics import metrics_util
from com.manageengine.monagent.metrics import metrics_logger
from com.manageengine.monagent.metrics import metrics_config_parser

from com.manageengine.monagent.metrics.statsd_executor import StatsDServer
from com.manageengine.monagent.metrics.prometheus_executor import PrometheusServer


def initialize():
    metrics_init = MetricsExecutor()
    metrics_init.start()
    metrics_constants.METRICS_THREAD_OBJ = metrics_init 


class MetricsExecutor(threading.Thread):
    def __init__(self):
        try:
            threading.Thread.__init__(self)
            self.instances_obj = {}
            self.suspended_instance = []
            self.deleted_instance = []
        except Exception as e:
            traceback.print_exc()
    
    def run(self):
        try:
            metrics_logger.log('=========== Metrics Executor invoked ===========\n')
            for mtype in metrics_constants.METRICS_TYPES:
                config=metrics_config_parser.get_config_data(os.path.join(metrics_constants.METRICS_WORKING_DIRECTORY,mtype,mtype+".cfg"))
                if metrics_util.is_app_enabled(mtype,config):
                    metrics_logger.log('METRIC ENABLED :: {}'.format(mtype))
                    if mtype == metrics_constants.METRICS_STATSD:
                        self.activate_statsd_monitor(config)
                    elif mtype == metrics_constants.METRICS_PROMETHEUS:
                        self.start_prometheus(config)
            metrics_logger.log('=========== instances for monitoring ======= {}'.format(self.instances_obj))
            metrics_logger.log('===========   suspended instances   ======= {}'.format(self.suspended_instance))
            metrics_logger.log('===========     deleted instances   ======= {}'.format(self.deleted_instance))
        except Exception as e:
            traceback.print_exc()
    
    def load_instances(self,obj_name,obj):
        self.instances_obj[obj_name] = obj

    def start_prometheus(self,config):
        try:
            for section in config:		    
                if section not in['PROMETHEUS','DEFAULT']:
                    if config.has_option(section, 'status'):
                        status = config.get(section, 'status')
                    else:
                        status = '0'
                    if status == '5':
                        self.suspended_instance.append(section)
                    elif status == '3':
                        self.deleted_instance.append(section)
                        metrics_constants.DELETED_INSTANCE.append(section)
                    else:
                        metrics_constants.PROMETHEUS_INSTANCES.append(section)
                        self.activate_prometheus_monitor(section,config)
        except Exception as e:
            metrics_logger.errlog('Exception in start_prometheus monitor {} :: {}'.format(section, e))
            traceback.print_exc()

    def activate_prometheus_monitor(self,section,config):
        try:
            prometheus_job_scheduler= PrometheusServer(section,config)
            prometheus_job_scheduler.start()
            self.load_instances(section,prometheus_job_scheduler)
        except Exception as e:
            metrics_logger.errlog('Exception in activating prometheus monitor {} :: {}'.format(section, e))
            traceback.print_exc()

    def activate_statsd_monitor(self,config):
        try:
            statsd_job_scheduler = StatsDServer(config)
            statsd_job_scheduler.start()
            self.load_instances(metrics_constants.METRICS_STATSD,statsd_job_scheduler)
        except Exception as e:
            metrics_logger.errlog('Exception in activating statsd monitor :: {}'.format(e))
            traceback.print_exc()
    
    def stop(self,instance_name):
        try:
            metrics_logger.log('=========== stop method invoked ======= ')
            if instance_name in self.instances_obj:
                self.instances_obj[instance_name].stop()
                self.instances_obj.pop(instance_name)
                metrics_logger.log('Instance stopped :: {}'.format(instance_name))
            else:
                metrics_logger.log('Instance not active :: {}'.format(instance_name))
        except Exception as e:
            metrics_logger.errlog('Exception in stopping monitor :: {}'.format(e))
            traceback.print_exc()
            
    def delete_metric(self,instance_name,delete_metrics):
        try:
            metrics_logger.log('=========== Metrics executor Delete Called ===========\n')
            if instance_name in self.instances_obj:
                self.instances_obj[instance_name].delete_metrics(delete_metrics[instance_name])
        except Exception as e:
            metrics_logger.errlog('Exception in deleting metrics :: {}'.format(e))
            traceback.print_exc()
