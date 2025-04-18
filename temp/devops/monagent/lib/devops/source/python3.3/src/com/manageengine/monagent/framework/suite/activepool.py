'''
Created on 10-JUly-2017
@author: giri
'''
import threading

class ActivePool(object):
    def __init__(self):
        self.active={}
        self.lock=threading.Lock()
        
    def make_active(self, app_name, monitor_name, thread_object):
        with self.lock:
            if not app_name in self.active:
                self.active[app_name] = {}
            self.active[app_name][monitor_name] = thread_object
    
    def make_inactive(self, app_name, monitor_name):
        with self.lock:
            if not app_name in self.active:
                pass
            else:
                if monitor_name in self.active[app_name]:
                    del self.active[app_name][monitor_name]
                
    def num_active(self):
        with self.lock:
            return len(self.active)
    def __str__(self):
        with self.lock:
            return str(self.active)

class RegisteredAppsActivePool(object):
    def __init__(self):
        self.active_apps = {}
        self.lock = threading.Lock()
    
    def make_active(self, mid, thread_object):
        with self.lock:
            if not mid in self.active_apps:
                self.active_apps[mid] = [thread_object]
            else:
                self.active_apps[mid].append(thread_object)
                
    def make_inactive(self, mid, thread_object):
        with self.lock:
            if mid in self.active_apps:
                del self.active_apps[mid]
                
    def num_active(self):
        with self.lock:
            return len(self.active_apps)
    
    def __str__(self):
        with self.lock:
            return str(self.active_apps)