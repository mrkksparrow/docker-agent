#$Id$

import traceback

from com.manageengine.monagent.logger import AgentLogger
from com.manageengine.monagent.notify.AgentNotifier import ShutdownNotifier


def initialize():
    try:
        ShutdownNotifier()
    except Exception as e:
        AgentLogger.log([AgentLogger.STDERR], ' *************************** Exception while initialising notify module *************************** '+ repr(e))
        traceback.print_exc()

initialize()