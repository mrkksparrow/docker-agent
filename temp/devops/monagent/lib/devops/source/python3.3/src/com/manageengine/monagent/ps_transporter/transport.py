'''
Created on 28-Dec-2016

@author: giri
'''
from ps_collector.metrics_interface import IMetricsInterface
from . import metric_handler

class Singleton(type):
    _instances = {}
    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]

class MetricTransporter(object, metaclass=Singleton):

    def __init__(self):
        self.last_curr_dict ={}
        self.result_dict = {}
    
    def controller(self, value_dict, metric_name):
        last_key = 'last_'+metric_name
        curr_key = 'curr_'+metric_name
        if not last_key in self.last_curr_dict:
            self.last_curr_dict[last_key] = value_dict
        elif not curr_key in self.last_curr_dict:
            self.last_curr_dict[curr_key] = value_dict
            self.value_calculator(last_key, curr_key, metric_name)
            
    def value_calculator(self, last_key, curr_key, metric_name):
        x = self.last_curr_dict[last_key]
        y = self.last_curr_dict[curr_key]
        
        if 'cpu_metrics' in metric_name:
            result_key = metric_name.split('_cpu_metrics')[0]
            total_cpu=0; total_idle_time= 0
            self.result_dict[result_key] = { k: y[k] - x[k] if not x[k] is None and not y[k] is None else None for k in x }
            
            total_cpu = MetricTransporter.list_dict_helper(self.result_dict[result_key], metric_handler.TOTAL_CPU)
            total_idle_time = MetricTransporter.list_dict_helper(self.result_dict[result_key], metric_handler.TOTAL_IDLE)
            
            if 'system' in metric_name:
                fraction = 1/total_cpu * 100 if not total_cpu == 0 else 0
            else:
                fraction = IMetricsInterface.cpu_count()/total_cpu * 100 if not total_cpu == 0 else 0
            usage = (total_cpu-total_idle_time) * fraction
            self.result_dict[result_key] = {k: round(self.result_dict[result_key][k]*fraction, 2) for k in self.result_dict[result_key]}
            self.result_dict[result_key]['idle'] = round(100.0 - usage, 2)
            self.result_dict[result_key]['usage'] = round(usage, 2)
            self.result_dict[result_key]['total_cpus'] = IMetricsInterface.cpu_count()
        
        if 'disk_io_metrics' in metric_name:  
            result_key = metric_name.split('_disk_io_metrics')[0]      
            self.result_dict[result_key] = {k: y[k] - x[k] if not x[k] is None and not y[k] is None else None for k in x}
        
        if 'memory_metrics' in metric_name:
            result_key = metric_name
            total = y['total']
            if not total == 0:
                self.result_dict[result_key] = {k: round(y[k]/total *100, 2) if not x[k] is None and not y[k] is None and not k == 'total' else None for k in x}
            else:
                self.result_dict[result_key] = {k: 0 if not x[k] is None and not y[k] is None and not k == 'total' else None for k in x}
            self.result_dict[result_key]['total'] = total
        
        if 'swap_memory' in metric_name:
            result_key = metric_name
            total = y['total']
            self.result_dict[result_key] = {}
            if not total == 0 and not total is None:
                for k in x:
                    if k in metric_handler.SUB_SWAP_MEM:
                        self.result_dict[result_key][k] = (y[k] - x[k])/ total *100 if not y[k] is None and not x[k] is None else None
                    elif k in metric_handler.SWAP_MEM:
                        self.result_dict[result_key][k] = y[k]/total * 100 if not y[k] is None else None
                    else:
                        self.result_dict[result_key][k] = total
            else:
                for k in x:
                    if not y[k] is None:
                        self.result_dict[result_key][k] = 0                        
        
        if 'process_metrics' in metric_name:
            result_key = metric_name
            self.result_dict[result_key] = {}
            for k in x:
                if k in metric_handler.PROC_CPU_METRICS:
                    self.result_dict[result_key][k] = round(((y[k] - x[k])/metric_handler.INTERVAL *100),2) if not y[k] is None and not x[k] is None else None
                if k in metric_handler.PROC_MEM_METRICS:
                    self.result_dict[result_key][k] = y[k] - x[k] if not y[k] is None and not x[k] is None else None
                if k in metric_handler.PROC_METRICS:
                    self.result_dict[result_key][k] = y[k]
            print(self.result_dict)
   
    @staticmethod
    def list_dict_helper(dict_value, list_value):
        calc_value = 0
        for key in list_value:
            if not dict_value[key] is None:
                calc_value += dict_value[key]
        return calc_value
    