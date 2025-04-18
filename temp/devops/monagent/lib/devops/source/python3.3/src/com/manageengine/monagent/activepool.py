'''
Created on 02-July-2017

@author: giri
'''

import threading

class ActivePool(object):
    def __init__(self):
        super(ActivePool, self).__init__()
        self.active = {}
        self.lock = threading.Lock()
        
    def make_active(self, monitor_name, thread_object):
        with self.lock:
            self.active[monitor_name] = thread_object
            
    def make_inactive(self, monitor_name):
        with self.lock:
            self.active.pop(monitor_name, None)
                
    def num_active(self):
        with self.lock:
            return len(self.active)
    def __str__(self):
        with self.lock:
            return str(self.active)