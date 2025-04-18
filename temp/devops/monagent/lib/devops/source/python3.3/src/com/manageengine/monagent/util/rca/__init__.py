#$Id$

import traceback

from com.manageengine.monagent.logger import AgentLogger
from com.manageengine.monagent.util.rca.RcaHandler import RcaReportHandler


def initialize():
    try:
        RcaReportHandler()
    except Exception as e:
        AgentLogger.log([AgentLogger.STDERR], ' *************************** Exception while initialising util module *************************** '+ repr(e))
        traceback.print_exc()

initialize()