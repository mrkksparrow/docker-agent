#$Id$
import traceback
from com.manageengine.monagent import AgentConstants
from com.manageengine.monagent.logger import AgentLogger
from com.manageengine.monagent.actions.ScriptMonitoring import ScriptHandler
from com.manageengine.monagent.actions.NFSMonitoring import NFSHandler

def initialize():
    try:
        #ScriptHandler.ScriptUtil = scriptHandler()
        ScriptMonitoring.ScriptUtil = ScriptHandler()
    except Exception as e:
        AgentLogger.log([AgentLogger.STDERR], ' *************************** Exception while initialising actions module *************************** '+ repr(e))
        traceback.print_exc()