#$Id$
import traceback

from com.manageengine.monagent import AgentConstants
from com.manageengine.monagent.logger import AgentLogger
import com.manageengine.monagent.communication.UdpHandler
import com.manageengine.monagent.communication.BasicClientHandler
from com.manageengine.monagent.communication.UdpHandler import SysLogParser, SysLogCollector, UdpServer
from com.manageengine.monagent.communication.BasicClientHandler import PortHandler,URLHandler, FileHandler, NTPHandler

def initialize():
    try:
        UdpHandler.SysLogUtil = SysLogParser()
        BasicClientHandler.PortUtil = PortHandler()
        BasicClientHandler.URLUtil = URLHandler()
        BasicClientHandler.NTPUtil = NTPHandler()
        if AgentConstants.OS_NAME in AgentConstants.FILE_MON_SUPPORTED:
            BasicClientHandler.FileMonUtil = FileHandler()
        UdpHandler.SysLogStatsUtil = SysLogCollector()
        UdpHandler.UDP_SERVER = UdpServer(AgentConstants.UDP_SERVER_IP, AgentConstants.UDP_PORT)
        UdpHandler.UDP_SERVER.start()
    except Exception as e:
        AgentLogger.log([AgentLogger.STDERR], ' *************************** Exception while initialising communication module *************************** '+ repr(e))
        traceback.print_exc()

#initialize()
