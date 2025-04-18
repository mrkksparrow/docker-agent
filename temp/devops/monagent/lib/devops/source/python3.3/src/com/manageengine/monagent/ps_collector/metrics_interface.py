'''
Created on 27-Dec-2016

@author: giri
'''
import abc, psutil

class IMetricsInterface(metaclass = abc.ABCMeta):

    @abc.abstractmethod
    def construct(self):
        '''metric data constructor'''
        return
    
    @abc.abstractmethod
    def collect(self):
        '''metrics collector'''
        return
    
    @staticmethod
    def cpu_count():
        try:
            return psutil.NUM_CPUS
        except AttributeError:
            return psutil.cpu_count()