#$Id$
import sys
from com.manageengine.monagent.logger import AgentLogger
from com.manageengine.monagent import module_object_holder

import traceback

try:
    from com.manageengine.monagent.plugins import PluginUtils
    module_object_holder.plugins_util = PluginUtils
    from com.manageengine.monagent.plugins.PluginMonitoring import PluginHandler
    module_object_holder.plugins_obj = PluginHandler()
except ImportError:
    AgentLogger.log(AgentLogger.MAIN,"Plugin module not found")
    traceback.print_exc()
        
try:
    from com.manageengine.monagent.automation import ScriptExecutor
    module_object_holder.script_obj = ScriptExecutor
except ImportError:
    AgentLogger.log(AgentLogger.MAIN,"Command / Script Execution module not found")
    traceback.print_exc()
    

AgentLogger.debug(AgentLogger.MAIN,"plugin obj :: {}".format(module_object_holder.plugins_obj))
AgentLogger.debug(AgentLogger.MAIN,"script obj :: {}".format(module_object_holder.script_obj))
AgentLogger.debug(AgentLogger.MAIN,"plugin util obj :: {}".format(module_object_holder.plugins_util))