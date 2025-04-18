'''
Created on 09-Nov-2016
@author: giri
'''
from com.manageengine.monagent.remoteinstaller import singleinstance
class AgentStatus:
    def calculate_agent_status(self):
        self.agent_status = 0
        try:
            s = singleinstance.SingleInstance()
            del(s)
        except OSError as e:
            if e.errno == 13 or e.errno == 11:
                return 1
        return self.agent_status