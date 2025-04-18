'''
Created on 1-Feb-2017

@author: giri
'''
import abc

class MetricsInterface():
    
    __metaclass__ = abc.ABCMeta
    @abc.abstractmethod
    def construct(self):
        '''metric data constructor'''
        return
    
    @abc.abstractmethod
    def collect(self):
        '''metrics collector'''
        return
    
    
    
