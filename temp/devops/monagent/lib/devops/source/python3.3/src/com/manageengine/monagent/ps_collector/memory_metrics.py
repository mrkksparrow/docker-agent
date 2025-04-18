'''
Created on 27-Dec-2016

@author: giri
'''
from .metrics_interface import IMetricsInterface
import psutil, sys
from ps_transporter.transport import MetricTransporter

class MemoryMetrics(IMetricsInterface):
    
    __slots__ = ('mem_metrics')
    
    def __init__(self):
        self.mem_metrics = psutil.virtual_memory()
        
    def construct(self):
        value_dict = {}
        value_dict['total'] = self.mem_metrics.total if hasattr(self.mem_metrics, "total") else None
        value_dict['available'] = self.mem_metrics.available if hasattr(self.mem_metrics, "available") else None
        value_dict['used'] = self.mem_metrics.used if hasattr(self.mem_metrics, "used") else None
        value_dict['free'] = self.mem_metrics.free if hasattr(self.mem_metrics, "free") else None
        value_dict['active'] = self.mem_metrics.active if hasattr(self.mem_metrics, "active") else None
        value_dict['inactive'] = self.mem_metrics.inactive if hasattr(self.mem_metrics, "inactive") else None
        value_dict['buffers'] = self.mem_metrics.buffers if hasattr(self.mem_metrics, "buffers") else None
        value_dict['cached'] = self.mem_metrics.cached if hasattr(self.mem_metrics, "cached") else None
        value_dict['shared'] = self.mem_metrics.shared if hasattr(self.mem_metrics, "shared") else None
        value_dict['wired'] = self.mem_metrics.wired if hasattr(self.mem_metrics, "wired") else None    
        return value_dict
    
    def collect(self):
        MetricTransporter().controller(self.construct(), "memory_metrics")
        