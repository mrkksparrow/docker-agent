'''
Created on 19-April-2017
@author: giri
'''
import com
import threading
class ResultPool(object):
    
    def __init__(self):
        self.result = {}
        self.lock = threading.Lock()
        self.success_host = []
        self.failure_host = []
    
    def hold_result(self, hostname, status, message, print_status=True):
        with self.lock:
            self.result[hostname] = status
            if print_status is True and not hostname == 'error':
                if status.lower() == 'success' and "already installed" in message.lower() :
                    com.manageengine.monagent.remoteinstaller.Constant.PRINT_SSH_DATA.append("Host Name - {} | Status -  {} | Message - {}\n".format(hostname, status, message))
                    self.success_host.append(hostname)
                elif status.lower() == 'success':
                    com.manageengine.monagent.remoteinstaller.Constant.PRINT_SSH_DATA.append("Host Name - {} | Status -  {} \n".format(hostname, status))
                    self.success_host.append(hostname)
                elif status.lower() == 'failed':
                    self.result[hostname] = status + " | " + message
                    com.manageengine.monagent.remoteinstaller.Constant.PRINT_SSH_DATA.append("Host Name - {} | Status -  {} | Message - {}\n".format(hostname, status, message))
                    self.failure_host.append(hostname)
                    
            elif print_status is True and hostname == 'error':
                com.managengine.monagent.remoteinstaller.Constant.PRINT_SSH_DATA.append("Status -  {} | Message - {}\n".format(status, message))
                
    def del_host(self, hostname):
        with self.lock:
            if hostname in self.result:
                del self.result[hostname]

    
    def num_active(self):
        with self.lock:
            return len(self.result)
    
    def __str__(self):
        with self.lock:
            return str(self.active)
        
    def print_summary(self):
        com.manageengine.monagent.remoteinstaller.Constant.PRINT_SSH_DATA.append("Summary")
        com.manageengine.monagent.remoteinstaller.Constant.PRINT_SSH_DATA.append("-------------------------------------------------------------------------------------------\n")
        com.manageengine.monagent.remoteinstaller.Constant.PRINT_SSH_DATA.append("-------------------------------------------------------------")
        com.manageengine.monagent.remoteinstaller.Constant.PRINT_SSH_DATA.append("| Success Count                  |                   {}  |".format(str(len(self.success_host))))
        com.manageengine.monagent.remoteinstaller.Constant.PRINT_SSH_DATA.append("| Failure Count                  |                   {}  |".format(str(len(self.failure_host))))
        com.manageengine.monagent.remoteinstaller.Constant.PRINT_SSH_DATA.append("-------------------------------------------------------------\n")