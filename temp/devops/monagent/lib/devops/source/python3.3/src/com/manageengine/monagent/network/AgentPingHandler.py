#$Id$
import traceback, time, json, threading
import os, sys, socket, copy
import struct, select, signal, collections 
from datetime import datetime
from six.moves.urllib.parse import urlencode
from com.manageengine.monagent import AgentConstants
from com.manageengine.monagent.logger import AgentLogger
from com.manageengine.monagent.util import AgentUtil
from com.manageengine.monagent.util.AgentUtil import FileUtil
from com.manageengine.monagent.scheduler import AgentScheduler
from com.manageengine.monagent.communication import CommunicationHandler
from com.manageengine.monagent.util.DesignUtils import Singleton, synchronized

PingUtil = None
ICMPUtil = None

class PingStats:
    def __init__(self,hostName):
        self.hostName = hostName
        self.hostIp   = "0.0.0.0"
        self.delay = 0
        self.seqNumber = 0
        self.pktsSent = 0
        self.pktsRcvd = 0
        self.minTime  = 999999999
        self.maxTime  = 0
        self.totTime  = 0
        self.avgTime = 0
        self.fracLoss = 1.0
        self.status = AgentConstants.PING_SUCCESS
        self.error = None
        
    def __str__(self):
        pingStats = ''
        pingStats += 'hostIp : ' + repr(self.hostIp)
        pingStats += 'delay : ' + repr(self.delay)
        pingStats += 'seqNumber : ' + repr(self.seqNumber)
        pingStats += 'pktsSent : ' + repr(self.pktsSent)
        pingStats += 'pktsRcvd : ' + repr(self.pktsRcvd)
        pingStats += 'minTime : ' + repr(self.minTime)
        pingStats += 'maxTime : ' + repr(self.maxTime)
        pingStats += 'totTime : ' + repr(self.totTime)
        pingStats += 'avgTime : ' + repr(self.avgTime)
        pingStats += 'fracLoss : ' + repr(self.fracLoss)
        pingStats += 'status : ' + repr(self.status)
        pingStats += 'error : ' + repr(self.error)
        return pingStats
    
    def __eq__(self, other): 
        return self is other
    
    def __hash__(self): 
        return hash(id(self))
    
class PingInfo:
    def __init__(self, hostName, hostIp=None,uniqueId=None):
        self.hostName = hostName
        self.hostIp = hostIp
        self.timeout = AgentConstants.ICMP_REQUEST_TIMEOUT
        self.count = 1
        self.dataBytes = 64
        self.pathFinder = False
        self.uniqueId = uniqueId
        self.lastPingStatus = AgentConstants.PING_SUCCESS
        self.isNotified = False
        self.pingStats = None
    
    def __str__(self):
        pingInfo = ''
        pingInfo += 'hostName : ' + repr(self.hostName)
        pingInfo += ' ,hostIp : ' + repr(self.hostIp)
        pingInfo += ' ,timeout : ' + repr(self.timeout)
        pingInfo += ' ,count : ' + repr(self.count)
        pingInfo += ' ,dataBytes : ' + repr(self.dataBytes)
        pingInfo += ' ,pathFinder : ' + repr(self.pathFinder)        
        pingInfo += ' ,uniqueId : ' + repr(self.uniqueId)
        pingInfo += ' ,lastPingStatus : ' + repr(self.lastPingStatus)
        pingInfo += ' ,isNotified : ' + repr(self.isNotified)
        return pingInfo
    
    def __repr__(self):
        return self.hostName
    
    def __eq__(self, other): 
        return self is other
    
    def __hash__(self): 
        return hash(id(self))
    
    def reset(self):
        self.pingStats = None
    
class ICMPRequest:
    __packetId = AgentConstants.MIN_ICMP_PACKET_ID
    __counterLock = threading.Lock()
    
    def __init__(self):
        self.pid = self.getPacketId()
        self.sock = None
        self.sentTime = None
        self.__initializeSocket()
        
    def __initializeSocket(self):
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.getprotobyname("icmp"))
        except socket.error as e:
            AgentLogger.log(AgentLogger.PING,"**************************** Exception while creating socket for ICMP. (socket error: '%s') ****************************" % e.args[1])
            raise
        
    def getPacketId(self):
        with ICMPRequest.__counterLock:
            if ICMPRequest.__packetId > AgentConstants.MAX_ICMP_PACKET_ID:
                ICMPRequest.__packetId = AgentConstants.MIN_ICMP_PACKET_ID
                ICMPRequest.__packetId+=1
            else:
                ICMPRequest.__packetId+=1
            return ICMPRequest.__packetId & 0xFFFF
        
    def close(self):
        if self.sock:
            self.sock.close()
            
class ICMPResponse:
    def __init__(self):
        self.recvTime = None
        self.dataSize = 0
        self.iphSrcIp = 0
        self.icmpSeqNumber = 0
        self.iphTTL = 0
        
    def __str__(self):
        icmpResp = ''
        icmpResp += 'recvTime : ' + repr(self.recvTime)
        icmpResp += 'dataSize : ' + repr(self.dataSize)
        icmpResp += 'iphSrcIp : ' + repr(self.iphSrcIp)
        icmpResp += 'icmpSeqNumber : ' + repr(self.icmpSeqNumber)
        icmpResp += 'iphTTL : ' + repr(self.iphTTL)
        return icmpResp
    
    def __eq__(self, other): 
        return self is other
    
    def __hash__(self): 
        return hash(id(self))
    
class ICMPHandler(Singleton):
    def __init__(self):
        global ICMPUtil
        ICMPUtil = self

    def checksum(self, stringValue):
        sum = 0
        count = 0
        strLength = 0
        lowByte = 0
        highByte = 0
        toReturn = 0
        try:
            strLength = (int(len(stringValue)/2))*2
            while count < strLength:
                if (sys.byteorder == "little"):
                    lowByte = stringValue[count]
                    highByte = stringValue[count + 1]
                else:
                    lowByte = stringValue[count + 1]
                    highByte = stringValue[count]
                sum = sum + (highByte * 256 + lowByte)
                count += 2
            if strLength < len(stringValue): 
                lowByte = stringValue[len(stringValue)-1]
                sum += lowByte
            sum &= 0xffffffff
            sum = (sum >> 16) + (sum & 0xffff)    
            sum += (sum >> 16)                
            toReturn = ~sum & 0xffff
            toReturn = socket.htons(toReturn)
        except Exception as e:
            AgentLogger.log(AgentLogger.PING,'******************************** Exception while calculating checksum for ICMP ********************************')
            traceback.print_exc()
        return toReturn

    def sendAndReceive(self, pingStats, pingInfo):
        delay = None
        icmpReq = None
        icmpResp = None
        try:
            AgentLogger.log(AgentLogger.PING,"PEER SEND AND RECEIVE : "+str(pingInfo.hostName)+"  with last ping status :"+str(pingInfo.lastPingStatus))
            icmpReq = ICMPRequest()
            if self.sendPacket(icmpReq, pingInfo, pingStats):
                pingStats.pktsSent += 1
                icmpResp = self.receivePacket(icmpReq, pingInfo, pingStats)
            if icmpResp and icmpResp.recvTime:
                delay = (icmpResp.recvTime-icmpReq.sentTime)*1000
                AgentLogger.log(AgentLogger.PING,'%d bytes from %s: icmp_seq=%d ttl=%d time=%d ms' % (icmpResp.dataSize, socket.inet_ntoa(struct.pack('!I', icmpResp.iphSrcIp)), icmpResp.icmpSeqNumber, icmpResp.iphTTL, delay))
                pingStats.pktsRcvd += 1
                pingStats.totTime += delay
                if pingStats.minTime > delay:
                    pingStats.minTime = delay
                if pingStats.maxTime < delay:
                    pingStats.maxTime = delay
            else:
                AgentLogger.log(AgentLogger.PING,'64 bytes from %s sent. But None received' %(pingStats))
        except Exception as e:
            AgentLogger.log(AgentLogger.PING,'*********************************** Exception while sending and receiving packet ***************************************')
            traceback.print_exc()
        finally:
            pingStats.seqNumber += 1
            icmpReq.close()
            icmpReq = None
            icmpResp = None
    
    def sendPacket(self, icmpReq, pingInfo, pingStats):
        bool_isSuccess = True
        myChecksum = 0
        padBytes = []
        startVal = 0x42
        data = None
        try:
            header = struct.pack("!BBHHH", AgentConstants.ICMP_ECHO, 0, myChecksum, icmpReq.pid, pingStats.seqNumber)      
            for i in range(startVal, startVal + (pingInfo.dataBytes-8)):
                padBytes += [(i & 0xff)]  
            data = bytearray(padBytes)
            myChecksum = self.checksum(header + data)
            header = struct.pack("!BBHHH", AgentConstants.ICMP_ECHO, 0, myChecksum, icmpReq.pid, pingStats.seqNumber)
            packet = header + data
            icmpReq.sentTime = time.time()
            try:
                icmpReq.sock.sendto(packet, (pingInfo.hostIp, 1))
            except socket.error as e:
                AgentLogger.log(AgentLogger.PING,'**************************** Exception while sending packet via socket (%s) ****************************' % (e.args[1]))
                bool_isSuccess = False
                pingStats.status = AgentConstants.PING_FAILURE
                pingStats.error = AgentConstants.PING_UNABLE_TO_SEND_PACKET
        except Exception as e:
            AgentLogger.log(AgentLogger.PING,'********************************** Exception while sending packet for '+str(pingInfo)+' **********************************')
            traceback.print_exc()
            bool_isSuccess = False
            pingStats.status = AgentConstants.PING_FAILURE
            pingStats.error = AgentConstants.PING_UNABLE_TO_SEND_PACKET
        return bool_isSuccess
        
    def receivePacket(self, icmpReq, pingInfo, pingStats):
        timeToWait = None
        icmpResp = None
        try:
            timeToWait = pingInfo.timeout/1000
            icmpResp = ICMPResponse()
            r, w, e = select.select([icmpReq.sock], [], [], timeToWait)
            if r:
                recvTime = time.time()
                recPacket, addr = icmpReq.sock.recvfrom(AgentConstants.ICMP_MAX_RECV)
                ipHeader = recPacket[:20]
                iphVersion, iphTypeOfSvc, iphLength, \
                iphID, iphFlags, iphTTL, iphProtocol, \
                iphChecksum, iphSrcIp, iphDestIP = struct.unpack("!BBHHHBBHII", ipHeader)
                icmpHeader = recPacket[20:28]
                icmpType, icmpCode, icmpChecksum, \
                icmpPacketID, icmpSeqNumber = struct.unpack("!BBHHH", icmpHeader)
                if icmpPacketID == icmpReq.pid:
                    icmpResp.dataSize = (len(recPacket) - 28) + 8
                    icmpResp.recvTime = recvTime
                    icmpResp.iphSrcIp = iphSrcIp
                    icmpResp.icmpSeqNumber = icmpSeqNumber
                    icmpResp.iphTTL = iphTTL
                else:
                    AgentLogger.log(AgentLogger.PING,'ICMP request packet Id does not match response packet Id')
                    pingStats.status = AgentConstants.PING_FAILURE
                    pingStats.error = AgentConstants.PING_PACKET_MISMATCH
                    AgentLogger.log(AgentLogger.PING,'Request received from address --> {0}'.format(addr))
            else:
                pingStats.status = AgentConstants.PING_FAILURE
                pingStats.error = AgentConstants.PING_REQUEST_TIME_OUT
                AgentLogger.debug(AgentLogger.PING,'Ping request time out. Packet not received.')
        except Exception as e:
            AgentLogger.log(AgentLogger.PING,'********************************** Exception while receiving packet for '+str(pingInfo)+' **********************************')
            pingStats.status = AgentConstants.PING_FAILURE
            pingStats.error = AgentConstants.PING_UNABLE_TO_RECEIVE_PACKET
            traceback.print_exc()
        return icmpResp
    
    def printStats(self, pingStats):
        AgentLogger.debug(AgentLogger.PING,'================================= Ping statistics for %s =================================' % (pingStats.hostIp))
        if pingStats.pktsSent > 0:
            pingStats.fracLoss = (pingStats.pktsSent - pingStats.pktsRcvd)/pingStats.pktsSent
        AgentLogger.debug(AgentLogger.PING,"%d packets transmitted, %d packets received, %0.1f%% packet loss" % (pingStats.pktsSent, pingStats.pktsRcvd, 100.0 * pingStats.fracLoss))
        if pingStats.pktsRcvd > 0:
            AgentLogger.debug(AgentLogger.PING,'round-trip (ms)  min/avg/max = %d/%0.1f/%d' % (pingStats.minTime, pingStats.totTime/pingStats.pktsRcvd, pingStats.maxTime))
        
    def getHostIp(self, hostName):
        hostIp = None
        try:
            hostIp = socket.gethostbyname(hostName)
        except socket.gaierror as e:
            AgentLogger.log(AgentLogger.PING,'Resolving IP from Host Name -- Unknown host : %s (%s)' % (hostName, e.args[1]))
        return hostIp
    
    def ping(self, pingInfo):
        pingStats = None
        hostIp = None
        try:  
            AgentLogger.log(AgentLogger.PING,"Pinging Device "+str(pingInfo.hostName)+" IP :"+str(pingInfo.hostIp))
            pingStats = PingStats(pingInfo.hostName)
            hostIp = self.getHostIp(pingInfo.hostName)
            if hostIp:
                pingInfo.hostIp = hostIp
                AgentLogger.log(AgentLogger.PING,'Final IP --->  {0}'.format(pingInfo.hostIp))
            if pingInfo.hostIp:
                pingStats.hostIp = pingInfo.hostIp
                for i in range(pingInfo.count):
                    self.sendAndReceive(pingStats, pingInfo)
                    #self.executePingCommand(pingStats,pingInfo)
            else:
                pingStats.status = AgentConstants.PING_FAILURE
                pingStats.error = AgentConstants.PING_UNKNOWN_HOST
#             self.printStats(pingStats)
            return pingStats
        except Exception as e:
            AgentLogger.log(AgentLogger.PING,'********************************** Exception while pinging : '+str(pingInfo)+' **********************************')
            traceback.print_exc()

class PingHandler(Singleton):
    def __init__(self):
        global PingUtil
        PingUtil = self
        ICMPHandler()
        self.__list_pingInfos = None
        self.lastLogTime = 0
                
    def getPingInfoList(self):
        return self.__list_pingInfos
        
    def __loadPingInfoList(self):
        try:
            AgentLogger.debug(AgentLogger.PING,'=============== LOADING PING MONITOR INFO FROM CONFIGURATION FILE ===============')
            fileObj = AgentUtil.FileObject()
            fileObj.set_filePath(AgentConstants.AGENT_MONITORS_PING_FILE)
            fileObj.set_dataType('json')
            fileObj.set_mode('rb')
            fileObj.set_dataEncoding('UTF-8')
            fileObj.set_loggerName(AgentLogger.PING)
            fileObj.set_logging(False)
            bool_toReturn, dict_pingInfoFromFile = FileUtil.readData(fileObj)
            AgentLogger.debug(AgentLogger.PING,"Dictionary from file "+str(dict_pingInfoFromFile))
            if not bool_toReturn:
                AgentLogger.debug(AgentLogger.PING,'*************** Exception while reading from file '+AgentConstants.AGENT_MONITORS_PING_FILE+' ***************')
                traceback.print_exc()
            self.__list_pingInfos = self.__toPingInfoList(dict_pingInfoFromFile['PingMonitors'])
        except Exception as e:
            AgentLogger.log(AgentLogger.PING,'*************** Exception while loading ping information from configuration file ***************')
            traceback.print_exc()
    
    @synchronized        
    def handlePeerRequest(self,dict_pingInfoFromServer,requestType):
        scheduleInfo = None
        try:
            AgentLogger.log(AgentLogger.PING,'================================= HANDLE PEER REQUEST : '+repr(requestType)+' ========================================')
            if requestType == AgentConstants.PEER_SCHEDULE:
                self.__list_pingInfos = self.__toPingInfoList(dict_pingInfoFromServer)
                self.scheduleForPing(requestType, copy.deepcopy(self.__list_pingInfos))
            else:
                self.scheduleForPing(requestType, self.__toPingInfoList(dict_pingInfoFromServer))
        except Exception as e:
            AgentLogger.log(AgentLogger.PING,'****************************** Exception while executing handlePeerRequest ******************************')
            traceback.print_exc()

    def addPingInfoAndScehdule(self,newPingInfo):
        self.__list_pingInfos.append(newPingInfo)        
        self.scheduleForPing([newPingInfo])
        
    def updatePingInfoAndSchedule(self,pingInfoFromServer,pingInfoExisting):
        pingInfoExisting.setPingPacketTransferCount(pingInfoFromServer.getPingPacketTransferCount())
        pingInfoExisting.setPingTimeout(pingInfoFromServer.getPingTimeout())
        pingInfoExisting.setPingRepeatInterval(pingInfoFromServer.getPingRepeatInterval())
        schedulePingInfo = AgentScheduler.ScheduleInfo()
        schedulePingInfo.setSchedulerName('PingScheduler')
        schedulePingInfo.setTaskName(pingInfoExisting.getHostIpAddress())
        AgentScheduler.deleteSchedule(schedulePingInfo)
        self.scheduleForPing([pingInfoExisting])
        
    def deletePingInfo(self):
        raise NotImplementedError
    
    def __toPingInfoList(self,list_pingInfos):
        list_PingInfos = None
        try:
            list_PingInfos = []
            if list_pingInfos:
                for key,each_peer in enumerate(list_pingInfos):
                    #AgentLogger.log(AgentLogger.PING,"Individual Peer Info: "+str(each_peer))
                    if each_peer['ipaddress']:
                        pingInfoObj = PingInfo(hostName=each_peer['hostname'], hostIp=each_peer['ipaddress'], uniqueId=each_peer['agentuid'])
                        list_PingInfos.append(pingInfoObj)
        except Exception as e:
            AgentLogger.log(AgentLogger.PING,'******************** Exception while converting ping dictionary to ping object ********************')
            traceback.print_exc()
        return list_PingInfos
            
    def __pingInfoToDictionary(self,list_toDictpingInfo):
        dictToReturn = None  
        try:
            dictToReturn['PingMonitors'] = {}
            for pingObject in list_toDictpingInfo:
                tempDict = {}
                tempDict['PacketTransferCount'] = pingObject.getPingPacketTransferCount()
                tempDict['PingTimeout'] = pingObject.getPingTimeout()
                tempDict['PingRepeatInterval'] = pingObject.getPingRepeatInterval()                
                dictToReturn['PingMonitors'][pingObject.getHostIpAddress()] = tempDict
            AgentLogger.debug(AgentLogger.PING,'Ping Info Dictionary: '+str(dictToReturn))            
        except Exception as e:
            AgentLogger.log(AgentLogger.PING,'******************** Exception while converting ping object list to dictionary ********************')
            traceback.print_exc()
        return dictToReturn
            
    def persistPingInfoToFile(self,dict_pingInfoToSave):
        bool_toReturn = True
        str_filePath = None
        AgentLogger.log(AgentLogger.PING,'============== PERSISTING PING MONITOR INFO INTO '+str(AgentConstants.AGENT_MONITORS_PING_FILE).upper()+' ===============')
        try:
            fileObj = AgentUtil.FileObject()
            fileObj.set_filePath(AgentConstants.AGENT_MONITORS_PING_FILE)
            fileObj.set_data(dict_pingInfoToSave)
            fileObj.set_dataType('json')
            fileObj.set_mode('wb')
            fileObj.set_dataEncoding('UTF-8')
            fileObj.set_logging(False)
            fileObj.set_loggerName(AgentLogger.PING)
            bool_toReturn, str_filePath = FileUtil.saveData(fileObj)
        except Exception as e:
            AgentLogger.log([AgentLogger.PING,AgentLogger.STDERR],'********************************** Exception while saving ping monitor information in configuration file ****************************************')
            traceback.print_exc()
            bool_toReturn = False
        return bool_toReturn,str_filePath
    
    @synchronized
    def pingExecutor(self,tupleArgs):
        requestType = None
        listOfPingInfos = None
        try:
            AgentLogger.log(AgentLogger.PING,"Ping executor :"+str(tupleArgs))
            requestType = tupleArgs[0]
            listOfPingInfos = tupleArgs[1]
            for pingInfo in listOfPingInfos:
                pingStats = ICMPUtil.ping(pingInfo)
                pingInfo.pingStats = pingStats
                AgentLogger.log(AgentLogger.PING,"Ping result for %s is %s"%(pingStats.hostName,pingStats.status))
                if pingStats.status == AgentConstants.PING_SUCCESS and pingInfo.lastPingStatus == AgentConstants.PING_FAILURE:
                    pingStats = ICMPUtil.ping(pingInfo)
                    pingInfo.pingStats = pingStats
                if pingStats.status == AgentConstants.PING_FAILURE and pingStats.error == AgentConstants.PING_PACKET_MISMATCH:
                    self.packetMismatchRetry(pingStats,pingInfo)
                elif pingStats.status == AgentConstants.PING_FAILURE and not pingStats.error == AgentConstants.PING_PACKET_MISMATCH:
                    pingStats = ICMPUtil.ping(pingInfo)
                    pingInfo.pingStats = pingStats
                    if pingStats.error==AgentConstants.PING_PACKET_MISMATCH:
                        self.packetMismatchRetry(pingStats,pingInfo)
                AgentLogger.log(AgentLogger.PING,'==========================================================================================')
        except Exception as e:
            AgentLogger.log(AgentLogger.PING,'********************************** Exception while executing ping executor *************************************')
            traceback.print_exc()
        return (requestType,listOfPingInfos)
    
    def executePingCommand(self,pingStats, pingInfo):
        dictToReturn={}
        exitCode=-1
        try:
            executorObj = AgentUtil.Executor()
            executorObj.setLogger(AgentLogger.PING)
            executorObj.setTimeout(1)
            command = AgentConstants.PING_COMMAND+ ' '+ pingInfo.hostIp
            if  command is not None:
                AgentLogger.log(AgentLogger.PING, 'ping command to be executed ---> ' + repr(command))
                executorObj.setCommand(command)
                executorObj.executeCommand()
                dictToReturn['result'] = executorObj.isSuccess()
                AgentLogger.log(AgentLogger.PING, 'command execution result ---> ' + repr(dictToReturn['result']))
                exitCode = executorObj.getReturnCode()
                AgentLogger.log(AgentLogger.PING, 'ping output ---> ' + repr(exitCode))
        except Exception as e:
            AgentLogger.log(AgentLogger.PING,'*********************************** Exception while executing ping ***************************************')
            traceback.print_exc()
        return exitCode

    def packetMismatchRetry(self,pingStats,pingInfo):
        packetMismatch_retry=0
        try:
            while packetMismatch_retry<2:
                 AgentLogger.log(AgentLogger.PING,"ICMP Ping Retry :"+str(packetMismatch_retry))
                 packetMismatch_retry+=1
                 pingStats = ICMPUtil.ping(pingInfo)
                 pingInfo.pingStats = pingStats
                 if not pingStats.error==AgentConstants.PING_PACKET_MISMATCH:
                    break
                 if packetMismatch_retry == 2 and pingStats.error == AgentConstants.PING_PACKET_MISMATCH:
                     returnCode = self.executePingCommand(pingStats,pingInfo)
                     AgentLogger.log(AgentLogger.PING,"Ping Command Return Code --->  :"+str(returnCode))
                     if returnCode == 0:
                         pingStats.status=AgentConstants.PING_SUCCESS
                         pingStats.error=None
            AgentLogger.log(AgentLogger.PING,"After Retries --->  :"+str(pingStats))
        except Exception as e:
            AgentLogger.log(AgentLogger.PING,'********************************** Exception while executing ping executor *************************************')
            traceback.print_exc()
            
    def scheduleForPing(self, requestType, listOfPingInfos=None):
        scheduleInfo = None
        list_hostNameToPing = None
        try:
            AgentLogger.log(AgentLogger.PING,"Ping Request Type :"+str(requestType))
            list_hostNameToPing = []
            scheduleInfo = AgentScheduler.ScheduleInfo()
            scheduleInfo.setSchedulerName('AgentScheduler')            
            if requestType == AgentConstants.PEER_VALIDATE:
                scheduleInfo.setIsPeriodic(False)
                scheduleInfo.setTaskName(AgentConstants.PEER_VALIDATE)
#                 scheduleInfo.setCallbackArgs((requestType,listOfPingInfos))
                taskArgs = (requestType,listOfPingInfos)
            elif requestType == AgentConstants.PEER_SCHEDULE:
                scheduleInfo.setIsPeriodic(True)
                scheduleInfo.setTaskName(AgentConstants.PEER_SCHEDULE)                
#                 scheduleInfo.setCallbackArgs(requestType)                
                scheduleInfo.setInterval(5)
                for each_peer in listOfPingInfos:
                    list_hostNameToPing.append(each_peer.hostName)
                AgentLogger.debug(AgentLogger.PING,"List of Host-name to Ping:"+str(list_hostNameToPing))
                taskArgs = (requestType, listOfPingInfos)           
            task = self.pingExecutor
            scheduleInfo.setTaskArgs(taskArgs)                                                       
            scheduleInfo.setCallback(self.pingCallback)        
            scheduleInfo.setTime(time.time())
            scheduleInfo.setTask(task)
            scheduleInfo.setLogger(AgentLogger.PING)
            AgentScheduler.schedule(scheduleInfo)
        except Exception as e:
            AgentLogger.log(AgentLogger.PING,'******************** Exception while scheduling pinginfos ********************'+str(e))
            traceback.print_exc()
            
    def checkForPeerNotification(self, tupleArgs):
        bool_skipPeerNotification = True
        bool_pingFailedFlag = False 
        requestType,listOfPingInfos = tupleArgs
        pingResultsForLogging =  {}
        for pingInfo in listOfPingInfos:
#             AgentLogger.log(AgentLogger.PING,'list of ping infos : '+repr(pingInfo))
#             AgentLogger.log(AgentLogger.PING,'ping status : '+repr(pingInfo.pingStats.status))
#             AgentLogger.log(AgentLogger.PING,'ping error : '+repr(pingInfo.pingStats.error))
            pingResultsForLogging[pingInfo.hostName] = (pingInfo.pingStats.status, pingInfo.pingStats.error)
            if pingInfo.pingStats.status == AgentConstants.PING_SUCCESS:
                bool_skipPeerNotification = False
            if pingInfo.pingStats.status != pingInfo.lastPingStatus:
                bool_pingFailedFlag = True
        if bool_pingFailedFlag:
            AgentLogger.log(AgentLogger.PING,'PING CALLBACK : Request type : '+repr(requestType)+' Ping results : '+repr(pingResultsForLogging))                
        elif self.lastLogTime == 0:
                self.lastLogTime = AgentUtil.getCurrentTimeInMillis()
                AgentLogger.log(AgentLogger.PING,'PING CALLBACK : Request type : '+repr(requestType)+' Ping results : '+repr(pingResultsForLogging))                 
        elif ((AgentUtil.getCurrentTimeInMillis() - self.lastLogTime ) > AgentConstants.PING_LOG_INTERVAL):
                self.lastLogTime = AgentUtil.getCurrentTimeInMillis()
                AgentLogger.log(AgentLogger.PING,'PING CALLBACK : Request type : '+repr(requestType)+' Ping results : '+repr(pingResultsForLogging))
        return bool_skipPeerNotification
            
    def pingCallback(self, tupleArgs):
        dict_pingInfoStatus = None
        bool_skipPeerNotification = True
        list_pingInfos = None
        try:
            bool_skipPeerNotification = self.checkForPeerNotification(tupleArgs)
            requestType, list_pingInfos = tupleArgs
            if requestType == AgentConstants.PEER_VALIDATE:
                dict_pingInfoStatus = {}
                for pingObject in list_pingInfos:
                    if pingObject.pingStats.status == AgentConstants.PING_SUCCESS:
                        dict_pingInfoStatus[pingObject.uniqueId] = 'true'
                    else: 
                        dict_pingInfoStatus[pingObject.uniqueId] = 'false'
                self.postPeerValidateResult(dict_pingInfoStatus,list_pingInfos)
            elif requestType == AgentConstants.PEER_SCHEDULE:
                if not bool_skipPeerNotification:
                    for pingObject in list_pingInfos:
                        if pingObject.lastPingStatus == AgentConstants.PING_SUCCESS and pingObject.pingStats.status == AgentConstants.PING_FAILURE:
                            self.notfiyPeerStatus(AgentConstants.PEER_DOWN_NOTIFY, pingObject)
                        elif pingObject.lastPingStatus == AgentConstants.PING_FAILURE and pingObject.pingStats.status == AgentConstants.PING_SUCCESS:
                            self.notfiyPeerStatus(AgentConstants.PEER_UP_NOTIFY, pingObject)
                else:
                    # if all the ping's are failure this block gets executed.
                    # When network is not reachable by agent skipping peer notification
                    if CommunicationHandler.checkNetworkStatus(AgentLogger.PING):
                        AgentLogger.log(AgentLogger.PING,'PING CALLBACK : Network available - Notify Peer')
                        for pingObject in list_pingInfos:
                            if pingObject.lastPingStatus == AgentConstants.PING_SUCCESS and pingObject.pingStats.status == AgentConstants.PING_FAILURE:
                                self.notfiyPeerStatus(AgentConstants.PEER_DOWN_NOTIFY, pingObject)
                            elif pingObject.lastPingStatus == AgentConstants.PING_FAILURE and pingObject.pingStats.status == AgentConstants.PING_SUCCESS:
                                self.notfiyPeerStatus(AgentConstants.PEER_UP_NOTIFY, pingObject)
                    else:
                        AgentLogger.log(AgentLogger.PING,'PING CALLBACK : Skipping peer notification -  network unavailable')
        except Exception as e:
            AgentLogger.log(AgentLogger.PING,'******************************* Exception while executing pingCallback *******************************')
            traceback.print_exc()
        finally:
            self.resetPingInfos(list_pingInfos)
            
    def resetPingInfos(self, list_pingInfos):
        try:
            for pingInfo in list_pingInfos:
                pingInfo.lastPingStatus = pingInfo.pingStats.status
                pingInfo.reset()
        except Exception as e:
            AgentLogger.log(AgentLogger.PING,'******************************* Exception while resetting pinginfos *******************************')
            
    def postPeerValidateResult(self, dict_pingInfoStatus,listOfPingInfos):
        try:
            AgentLogger.log(AgentLogger.PING, '================================= POST PEER_VALIDATE RESULT =================================')
            AgentLogger.log(AgentLogger.PING,str(AgentConstants.PEER_CHECK_RESULT)+' : '+repr(dict_pingInfoStatus) + 'LIST_PING_INFOS : '+repr(listOfPingInfos))
            if not all(val=='true' for val in dict_pingInfoStatus.values()):
                self.sendOrReceivePeerList(AgentConstants.PEER_CHECK_RESULT, dict_pingInfoStatus)
            elif all(val=='true' for val in dict_pingInfoStatus.values()):
                self.scheduleForPing(AgentConstants.PEER_SCHEDULE, listOfPingInfos)
        except Exception as e:
            AgentLogger.log(AgentLogger.PING,'******************************* Exception while postPeerValidateResult *******************************')
            traceback.print_exc()

    def getPeerCheck(self):
        AgentLogger.log(AgentLogger.PING, '================================= GET PEER CHECK =================================')
        self.sendOrReceivePeerList(AgentConstants.GET_PEER_CHECK)
                    
    def sendOrReceivePeerList(self, action, dict_pingInfoStatus = None):
        bool_isSuccess = True
        try:
            str_url = None
            str_servlet = AgentConstants.PEER_HANDLER_SERVLET
            dict_requestParameters      =   {
            'action'   :    action,
            'agentKey'  :   AgentUtil.AGENT_CONFIG.get('AGENT_INFO', 'agent_key'),
            'bno' : AgentConstants.AGENT_VERSION,
            'custID'    :   AgentConstants.CUSTOMER_ID
            }
            if not dict_requestParameters == None:
                str_requestParameters = urlencode(dict_requestParameters)
                str_url = str_servlet + str_requestParameters
            requestInfo = CommunicationHandler.RequestInfo()
            requestInfo.set_loggerName(AgentLogger.PING)
            requestInfo.set_method(AgentConstants.HTTP_POST)
            requestInfo.set_url(str_url)
            str_jsonData = json.dumps(dict_pingInfoStatus)#python dictionary to json string
            requestInfo.set_data(str_jsonData)                
            requestInfo.add_header("Content-Type", 'application/json')
            requestInfo.add_header("Accept", "text/plain")
            requestInfo.add_header("Connection", 'close')
            bool_toReturn, int_errorCode, dict_responseHeaders, dict_responseData = CommunicationHandler.sendRequest(requestInfo)
            AgentLogger.log(AgentLogger.PING,"Response headers : "+str(dict_responseHeaders))
            if dict_responseData:
                CommunicationHandler.handleResponseHeaders(dict_responseHeaders, dict_responseData,'PING_HANDLER')
            elif bool_toReturn:
                self.deletePeerSchedule(AgentConstants.PEER_SCHEDULE)
        except Exception as e:
            AgentLogger.log(AgentLogger.STDERR, ' *************************** Exception while sending or receiving peer list *************************** '+ repr(e))
            traceback.print_exc()
            bool_isSuccess = False
        return bool_isSuccess
    
    def notfiyPeerStatus(self,action, pingInfo):
        bool_isSuccess = True
        AgentLogger.log(AgentLogger.PING, '================================= NOTIFYING PEER STATUS =================================')
        AgentLogger.log(AgentLogger.PING,repr(pingInfo)+' : '+str(action))
        try:
            str_url = None
            str_servlet = AgentConstants.PEER_HANDLER_SERVLET
            if (action == AgentConstants.PEER_UP_NOTIFY) or (action == AgentConstants.PEER_DOWN_NOTIFY):
                dict_requestParameters = {
                                            'action'   :    action,
                                            'agentKey'  :   AgentUtil.AGENT_CONFIG.get('AGENT_INFO', 'agent_key'),
                                            'bno' : AgentConstants.AGENT_VERSION,
                                            'custID'    :   AgentConstants.CUSTOMER_ID,
                                            'peeruid'   :   pingInfo.uniqueId
                                         }
            if not dict_requestParameters == None:
                str_requestParameters = urlencode(dict_requestParameters)
                str_url = str_servlet + str_requestParameters
            requestInfo = CommunicationHandler.RequestInfo()
            requestInfo.set_loggerName(AgentLogger.PING)
            requestInfo.set_method(AgentConstants.HTTP_POST)
            requestInfo.set_url(str_url)
            requestInfo.set_timeout(5)
            requestInfo.add_header("Accept", "text/plain")
            requestInfo.add_header("Connection", 'close')
            bool_toReturn, int_errorCode, dict_responseHeaders, dict_responseData = CommunicationHandler.sendRequest(requestInfo)
        except Exception as e:
            AgentLogger.log(AgentLogger.STDERR, ' *************************** Exception while notifying peer status *************************** '+ repr(e))
            traceback.print_exc()
            bool_isSuccess = False
        return bool_isSuccess
    
    def deletePeerSchedule(self,requestType):
        AgentLogger.log(AgentLogger.PING,"Deleting schedule of request type: "+str(requestType))
        scheduleInfo = AgentScheduler.ScheduleInfo()
        scheduleInfo.setSchedulerName('AgentScheduler')
        scheduleInfo.setTaskName(requestType)
        AgentScheduler.deleteSchedule(scheduleInfo)
        
