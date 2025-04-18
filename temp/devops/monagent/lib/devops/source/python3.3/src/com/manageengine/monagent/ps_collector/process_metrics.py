'''
Created on 27-Dec-2016

@author: giri
'''
from .metrics_interface import IMetricsInterface
import psutil
from ps_transporter.transport import MetricTransporter


class ProcessMetrics(IMetricsInterface):
   
    __slots__ = ('proc_pattern_list', '_total')
    
    def __init__(self):
        try:
            self._total = psutil.virtual_memory().total
        except Exception as e:
            self._total = None
        self.proc_pattern_list = ['java', 'apache', 'mysql', 'cassandra']
    
    def _find_proc(self, proc_pattern):
        for proc in psutil.process_iter():
            cmdline = ' '.join(proc.cmdline())
            if cmdline and cmdline.find(proc_pattern) != -1:
                return proc, cmdline
        return None, None
    
    def construct(self, proc):
        value_dict = {}
        cpu = proc.cpu_times() if hasattr(proc, 'cpu_times') else None
        mem = proc.memory_info() if hasattr(proc, 'memory_info') else None
        io = proc.io_counters() if hasattr(proc, 'io_counters') else None
        value_dict['fds'] = proc.num_fds() if hasattr(proc, 'num_fds') else None
        value_dict['rss'] = mem.rss if hasattr(mem, 'rss') else None
        value_dict['vms'] = mem.vms if hasattr(mem, 'vms') else None
        value_dict['reads'] = io.read_count if hasattr(io, 'read_count') else None
        value_dict['writes'] = io.write_count if hasattr(io, 'write_count') else None
        value_dict['bytes_read'] = io.read_bytes if hasattr(io, 'read_bytes') else None
        value_dict['bytes_write'] = io.write_bytes if hasattr(io, 'write_bytes') else None
        value_dict['total'] = self._total
        value_dict['cpu_user'] = cpu.user if hasattr(cpu, 'user') else None
        value_dict['cpu_system'] = cpu.system if hasattr(cpu, 'system') else None
        return value_dict
        
    def collect(self):
        for proc_pattern in self.proc_pattern_list:
            proc, cmdline = self._find_proc(proc_pattern)
            if not proc is None:
                MetricTransporter().controller(self.construct(proc), cmdline+"_process_metrics")
    