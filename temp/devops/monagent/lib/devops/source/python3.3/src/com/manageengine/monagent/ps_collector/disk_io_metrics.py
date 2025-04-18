'''
Created on 27-Dec-2016

@author: giri
'''
from .metrics_interface import IMetricsInterface
import psutil
from ps_transporter.transport import MetricTransporter

class DiskIOMetrics(IMetricsInterface):
    
    __slots__ = ('disk_io_metrics', 'per_disk_io_metrics')
    
    def __init__(self):
        self.disk_io_metrics = psutil.disk_io_counters()
        self.per_disk_io_metrics = psutil.disk_io_counters(perdisk=True)
    def construct(self, metrics, name):
        value_dict = {}
       # value_dict['device_name'] = name
        value_dict['reads'] = metrics.read_count if hasattr(metrics, 'read_count') else None
        value_dict['writes'] = metrics.write_count if hasattr(metrics, 'write_count') else None
        value_dict['bytes_read'] = metrics.read_bytes if hasattr(metrics, 'read_bytes') else None
        value_dict['bytes_write'] = metrics.write_bytes if hasattr(metrics, 'write_bytes') else None
        value_dict['time_read'] = metrics.read_time if hasattr(metrics, 'read_time') else None
        value_dict['time_write'] = metrics.write_time if hasattr(metrics, 'write_time') else None
        value_dict['busy_time'] = metrics.busy_time if hasattr(metrics, 'busy_time') else None
        value_dict['read_merged_count'] = metrics.read_merged_count if hasattr(metrics, 'read_merged_count') else None
        value_dict['write_merged_count'] = metrics.write_merged_count if hasattr(metrics, 'write_merged_count') else None
        return value_dict
    
    def collect(self):
        new_value = []
        MetricTransporter().controller(self.construct(self.disk_io_metrics, 'all'), "all_disk_io_metrics")
        #for dev in self.per_disk_io_metrics:
         #   MetricTransporter().controller(self.construct(self.per_disk_io_metrics[dev], dev), dev+"_disk_io_metrics")
        
#d =DiskIOMetrics().collect()
