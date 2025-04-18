'''
Created on 27-Dec-2016

@author: giri
'''
from .metrics_interface import IMetricsInterface
import psutil, sys
from ps_transporter.transport import MetricTransporter

class SwapMemoryMetrics(IMetricsInterface):
    
    __slots__ = ('swap_mem_metrics')
    
    def __init__(self):
        self.swap_mem_metrics = psutil.swap_memory()
        
    def construct(self):
        value_dict = {}
        value_dict['total'] = self.swap_mem_metrics.total if hasattr(self.swap_mem_metrics, "total") else None
        value_dict['used'] = self.swap_mem_metrics.used if hasattr(self.swap_mem_metrics, "used") else None
        value_dict['free'] = self.swap_mem_metrics.free if hasattr(self.swap_mem_metrics, "free") else None
        value_dict['sin'] = self.swap_mem_metrics.sin if hasattr(self.swap_mem_metrics, "sin") else None
        value_dict['sout'] = self.swap_mem_metrics.sout if hasattr(self.swap_mem_metrics, "sout") else None
        return value_dict
    
    def collect(self):
        MetricTransporter().controller(self.construct(), "swap_memory")
        
        
