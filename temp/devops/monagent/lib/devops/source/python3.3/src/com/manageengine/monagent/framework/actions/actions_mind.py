'''
Created on 02-July-2017

@author: giri
'''
import abc
class Actions():
    __metaclass__ = abc.ABCMeta
    @abc.abstractmethod
    def work(self):
        return
    
    @abc.abstractmethod
    def load(self):
        return
    
    @abc.abstractmethod
    def update_result(self):
        return
    
    @property
    def timeout(self):
        try:
            _timeout = 60
            if "@timeout" in self.metric_contents:
                if type(self.metric_contents["@timeout"]) is int:
                    _timeout = self.metric_contents["@timeout"]
                elif type(self.metric_contents["@timeout"]) is str:
                    _timeout = int(self.metric_contents["@timeout"])
        except Exception as e:
            print(e)
        finally:
            return _timeout
    
    @property
    def metrics_id(self):
        try:
            _metrics_id = None
            if "@id" in self.metric_contents:
                if type(self.metric_contents["@id"]) is str:
                    _metrics_id = self.metric_contents["@id"]                
        except Exception as e:
            print(e)
        finally:
            return _metrics_id
        
    @property
    def metric_list(self):
        try:
            _metric_list = []
            if "Metric" in self.metric_contents:
                if type(self.metric_contents["Metric"]) is list:
                    _metric_list = self.metric_contents["Metric"]                  
                else:
                    _metric_list = [self.metric_contents["Metric"]]
        except Exception as e:
            print(e)
        finally:
            return _metric_list
    
    @property
    def storevalue(self):
        try:
            _storevalue = False
            if "@storevalue" in self.metric_contents:
                if type(self.metric_contents["@storevalue"]) is str:
                    if self.metric_contents["@storevalue"].lower() == "true":
                        _storevalue = True                        
                else:
                    _storevalue = self.metric_contents["@storevalue"]
        except Exception as e:
            print(e)
        finally:
            return _storevalue
    
    @property
    def is_iter(self):
        _is_iter = False
        if "@iter" in self.metric_contents:
            _is_iter = True
        return _is_iter