'''
Created on 27-Oct-2017

@author: giri
'''
import traceback, os
from datetime import datetime
import time

from com.manageengine.monagent import AgentConstants
from com.manageengine.monagent.logger import AgentLogger
from com.manageengine.monagent.util import AgentUtil
from com.manageengine.monagent.communication import CommunicationHandler
from com.manageengine.monagent.util import AgentArchiver
from com.manageengine.monagent.util import DesignUtils
from com.manageengine.monagent.util.AgentUtil import FileUtil

UPGRADE = False


def initialize():
    AgentLogger.log(AgentLogger.STDOUT, '================================= UPGRADER INITIALIZED =================================')

    AgentConstants.UPGRADE_FILE_URL_NAME = AgentConstants.UPGRADE_FILE = os.path.join(AgentConstants.AGENT_UPGRADE_DIR, AgentConstants.UPGRADE_FILE_NAME)
    AgentConstants.AGENT_UPGRADE_URL = '//' + AgentConstants.AGENT_UPGRADE_CONTEXT + '//' + AgentConstants.UPGRADE_FILE_NAME
    
    AgentLogger.log(AgentLogger.STDOUT, 'Agent Upgrade Url : '+str(AgentConstants.AGENT_UPGRADE_URL))
    AgentLogger.log(AgentLogger.STDOUT, 'UPGRADE_FILE : '+str(AgentConstants.UPGRADE_FILE))
    
    isMonAgentUpgraded()
    return True

def isMonAgentUpgraded():
    try:
        if os.path.exists(AgentConstants.MON_AGENT_UPGRADED_FLAG_FILE):
            AgentLogger.log(AgentLogger.MAIN,'================================= MON_AGENT_UPGRADED_FLAG_FILE is present, hence assigning MON_AGENT_UPGRADED = True =================================')
            AgentConstants.MON_AGENT_UPGRADED = True
        else:
            AgentLogger.log(AgentLogger.STDOUT,'================================= MON_AGENT_UPGRADED_FLAG_FILE is not present, hence this is not a start after upgrade =================================')
    except Exception as e:
        AgentLogger.log([AgentLogger.MAIN, AgentLogger.STDERR],' ************************* Exception while setting MON_AGENT_UPGRADED variable ************************* ')
        traceback.print_exc()
    finally:
        FileUtil.deleteFile(AgentConstants.MON_AGENT_UPGRADED_FLAG_FILE)
   
def handleUpgrade(var_obj=None, custom = False):    
    global UPGRADE
    try:        
        UPGRADE = True   
        watchdogUpgrader = AgentVenvUpgrader()
        watchdogUpgrader.setUpgradeProps(var_obj)
        watchdogUpgrader.setUpgradeFile(AgentConstants.UPGRADE_FILE)
        if custom == True:
            AgentLogger.log(AgentLogger.MAIN,'UPGRADE : Inside patch upgrade ')
            watchdogUpgrader.upgrade(custom = True)
        else:
            AgentLogger.log(AgentLogger.MAIN,'UPGRADE : Inside normal upgrade ')
            watchdogUpgrader.upgrade()
#            if watchdogUpgrader.isUpgradeSuccess():
#                AgentLogger.log(AgentLogger.MAIN, ' -------------------------------- Terminating Monitoring Agent for upgrade ------------------------------------ ')
#                AgentUtil.TerminateAgent()      
    except Exception as e:
        AgentLogger.log(AgentLogger.MAIN, ' *************************** Exception While Handling Upgrade *************************** '+ repr(e))
        traceback.print_exc()