'''
Created on 27-Dec-2016

@author: giri
'''
from .metrics_interface import IMetricsInterface
import psutil, time
from ps_transporter.transport import MetricTransporter

class CpuVcpuMetrics(IMetricsInterface):
    __slots__ = ( 'cpu_times', 'vcpu_times', 'metric_times')
    
    def __init__(self):
        self.cpu_times = psutil.cpu_times()
        self.vcpu_times = psutil.cpu_times(percpu=True)
        
    def construct(self, metrics):
        value_dict = {}
        value_dict['user'] = metrics.user if hasattr(metrics, 'user') else None
        value_dict['system'] = metrics.system if hasattr(metrics, 'system') else None
        value_dict['nice'] = metrics.nice if hasattr(metrics, 'nice') else None
        value_dict['idle'] = metrics.idle if hasattr(metrics, 'idle') else None
        value_dict['iowait'] = metrics.iowait if hasattr(metrics, 'iowait') else None
        value_dict['irq'] = metrics.irq if hasattr(metrics, 'irq') else None
        value_dict['softirq'] = metrics.softirq if hasattr(metrics, 'softirq') else None
        value_dict['steal'] = metrics.steal if hasattr(metrics, 'steal') else None
        value_dict['guest'] = metrics.guest if hasattr(metrics, 'guest') else None
        value_dict['guest_nice'] = metrics.guest_nice if hasattr(metrics, 'guest_nice') else None
        return value_dict
        
    def collect(self):
        MetricTransporter().controller(self.construct(self.cpu_times), "system_cpu_metrics")
        for index in range(IMetricsInterface.cpu_count()):
            MetricTransporter().controller(self.construct(self.vcpu_times[index]), "core_"+str(index)+"_cpu_metrics")


