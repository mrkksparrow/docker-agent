#$Id$

import traceback

from com.manageengine.monagent.logger import AgentLogger
from com.manageengine.monagent.network.AgentPingHandler import PingHandler


def initialize():
    try:
        PingHandler()
    except Exception as e:
        AgentLogger.log([AgentLogger.STDERR], ' *************************** Exception while initialising network module *************************** '+ repr(e))
        traceback.print_exc()

initialize()