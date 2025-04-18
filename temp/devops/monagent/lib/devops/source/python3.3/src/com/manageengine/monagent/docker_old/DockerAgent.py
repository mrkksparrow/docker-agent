#$Id$
#updateAgentConfig dataconsolidator
import json
import os
import socket
import traceback
import com

import time
from six.moves.urllib.parse import urlencode
from copy import deepcopy
from com.manageengine.monagent import AgentConstants
from com.manageengine.monagent.logger import AgentLogger
from com.manageengine.monagent.util import AgentUtil
from com.manageengine.monagent.util.AgentUtil import FileUtil, AGENT_CONFIG
from com.manageengine.monagent.communication import CommunicationHandler
from com.manageengine.monagent.communication import BasicClientHandler
from com.manageengine.monagent.docker_old import DockUtils
from com.manageengine.monagent.docker_old.RemoteApi import DockerRemoteAPI
from com.manageengine.monagent.docker_old.CgroupData import CgroupDataCollection

DOCKER_CONF = {"SockPath":None}
LAST_COLLECT_TIME = None
DATA_COLLECTION_TIME_DIFF = 300
UNKNOWN_ERROR = 999
PREVIOUS_DATA = {}


class DockerDataCollector(DockerRemoteAPI) :#, CgroupDataCollection):

    def __init__(self, user_sock_path = None):
        self.running = DockUtils.isDockerRunning()
        if self.running or user_sock_path:
            self.sock_path = self._getRunningSocket(user_sock_path, DockUtils.runningSocket())
            if self.sock_path :
                self.running = True
                DockerRemoteAPI.__init__(self,  self.sock_path)
        
                
    def _saveDockerData(self, tag, dict_dataToSave, logger):
        '''Save docker data into the file'''
        
        try:
            str_fileName = FileUtil.getUniqueFileName(AgentUtil.AGENT_CONFIG.get('AGENT_INFO', 'agent_key'), tag)
            str_filePath = AgentConstants.AGENT_DATA_DIR + '/' + str_fileName
            fileObj = AgentUtil.FileObject()
            fileObj.set_fileName(str_fileName)
            fileObj.set_filePath(str_filePath)
            fileObj.set_data(dict_dataToSave)
            fileObj.set_dataType('json')
            fileObj.set_mode('wb')
            fileObj.set_dataEncoding('UTF-16LE')
            fileObj.set_logging(False)
            fileObj.set_loggerName(logger)            
            bool_toReturn, str_filePath = FileUtil.saveData(fileObj)
            if bool_toReturn:
                AgentLogger.log(AgentLogger.COLLECTOR, 'DOCKER_LOG : ' + '{0} , file name : {1} ,saved to : {2} '.format(tag, str_fileName , str_filePath))
            # self.setZipAndUploadInfo([str_fileName])
        except Exception as e:
            AgentLogger.log([AgentLogger.UDP, AgentLogger.STDERR], ' *************************** Exception while saving syslog stats *************************** ' + repr(e))

        
    def _getRunningSocket(self, user_sock_path, sock_path):
        ''' This function will try to find the docker running socket Path
        
        if success save path in the docker_conf.txt and return the same  
        or  return None if unable to find'''
               
        try :
            global DOCKER_CONF
            if user_sock_path != None :  
                user_sock_path = self._parseSocketPath(user_sock_path)  # Check if socket path is coming from server
                if user_sock_path and self._testConnection(user_sock_path) :  # Test connection on specified socket
                    DOCKER_CONF["SockPath"] = user_sock_path 
                    AgentUtil.writeDataToFile(AgentConstants.AGENT_DOCKER_CONF_FILE, DOCKER_CONF)  # Save socket path for the further use                   
                    return user_sock_path
                
            if os.path.isfile(AgentConstants.AGENT_DOCKER_CONF_FILE) :
                bool_status, dict_data = AgentUtil.loadDataFromFile(AgentConstants.AGENT_DOCKER_CONF_FILE)  # Retrieve data from file 
                if bool_status and dict_data and "SockPath" in dict_data:                   
                    if self._testConnection(dict_data["SockPath"]):
                        return dict_data["SockPath"]                                         
                
            if sock_path :
                sock_path = self._parseSocketPath(sock_path)
                if sock_path and self._testConnection(sock_path):
                    DOCKER_CONF["SockPath"] = sock_path
                    AgentUtil.writeDataToFile(AgentConstants.AGENT_DOCKER_CONF_FILE, DOCKER_CONF)
                    return sock_path
                    
        except Exception as e:
            AgentLogger.log(AgentLogger.COLLECTOR, "DOCKER_LOG: " +  "Exception occurred in socket path initialization : {0}".format(e))
        return None
        
    def _testConnection(self, sock_path):
        '''Function take Unix socket path in the format: //sock/path.sock
        
        and true/false on the basis to availability of socket'''
        
        retVal = False
        sock = None
        try:
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)  # Creating socket for Unix family
            err = sock.connect_ex(sock_path)                          
            if err == 0 :
                retVal = True
        except OSError as oe:
            AgentLogger.log(AgentLogger.COLLECTOR, "DOCKER_LOG: " +  "Error in connection Testing :{0}".format(oe))
        finally:
            if sock:
                sock.close()
        return retVal
    
    def _parseSocketPath(self, sock_path):
        ''' Change socket path in appropriate format'''
        
        try :
            if not sock_path :
                return None 
            if not sock_path.startswith('unix:'):
                AgentLogger.log(AgentLogger.COLLECTOR, "DOCKER_LOG: " +  "Error in socket Path format")
                return None
            else:
                return "//{0}".format(sock_path[5:].lstrip("/"))
        except LookupError as le:
            AgentLogger.log(AgentLogger.COLLECTOR, "DOCKER_LOG: " +  "Error in socket parsing : {0}".format(le))

    def _updateContConfData(self, container, tempContainer):
     
        try :
            tempContainer["Id"] = self._checkFieldReturnValue(["Id"], container)
            tempContainer["Binds"] = self._checkFieldReturnValue(["HostConfig", "Binds"], container)
            tempContainer["Cpuset"] = self._checkFieldReturnValue(["Config", "Cpuset"], container)
            tempContainer["CpuShares"] = self._checkFieldReturnValue(["Config", "CpuShares"], container)
            #tempContainer["Created"] = self._checkFieldReturnValue(["Created"], container)
            tempContainer["Driver"] = self._checkFieldReturnValue(["Driver"], container)
            tempContainer["ExposedPorts"] = self._checkFieldReturnValue(["Config", "ExposedPorts"], container)
            #tempContainer["Gateway"] = self._checkFieldReturnValue(["NetworkSettings", "Gateway"], container)
            tempContainer["ImageId"] = self._checkFieldReturnValue(["Image"], container)
            tempContainer["ImageName"] = self._checkFieldReturnValue(["Config", "Image"], container)[:99]
            tempContainer["IPAddress"] = self._checkFieldReturnValue(["NetworkSettings", "IPAddress"], container)
            tempContainer["Memory"] = self._checkFieldReturnValue(["Config", "Memory"], container)
            tempContainer["MemorySwap"] = self._checkFieldReturnValue(["Config", "MemorySwap"], container)
            strName = self._checkFieldReturnValue(["Name"], container)
            if strName.startswith('/'):
                tempContainer["Name"] = strName[1:]
            elif strName:
                tempContainer["Name"] = strName
            else:
                tempContainer["Name"] = ''
            tempContainer["Path"] = self._checkFieldReturnValue(["Path"], container)
            tempContainer["Ports"] = self._checkFieldReturnValue(["NetworkSettings", "Ports"], container)
            tempContainer["PortBindings"] = self._checkFieldReturnValue(["HostConfig", "PortBindings"], container)
            tempContainer["Running"] = 1 if self._checkFieldReturnValue(["State", "Running"], container) else 0
            tempContainer["Volumes"] = self._checkFieldReturnValue(["Volumes"], container)
            tempContainer["VolumesRW"] = self._checkFieldReturnValue(["VolumesRW"], container)
            name = tempContainer['Name']
            if len(name)>96 :
                tempContainer["Name"] = (name[:96] + '..') if len(name) > 96 else name
            if tempContainer["CpuShares"]==None:
                tempContainer["CpuShares"] = self._checkFieldReturnValue(["HostConfig", "CpuShares"], container)
            if tempContainer["Memory"]==None:
                tempContainer["Memory"] = self._checkFieldReturnValue(["HostConfig", "Memory"], container)
            if tempContainer["MemorySwap"]==None:
                tempContainer["MemorySwap"] = self._checkFieldReturnValue(["HostConfig", "MemorySwap"], container)
            if tempContainer["Cpuset"]==None:
                tempContainer["Cpuset"] = self._checkFieldReturnValue(["HostConfig", "CpusetCpus"], container)
        except Exception as e:
            AgentLogger.log(AgentLogger.COLLECTOR, "DOCKER_LOG: " +  "Error in updating Conf Data: {0}".format(e)) 
            
    def _checkFieldReturnValue(self, field, data):
        ''' Retrive the deep field form dict'''
        
        for f in field :
            if data and f in data :
                data = data[f]
            else :
                return None
        return data
    
    def updatePreviousData(self, cont_id, key, data):
        global PREVIOUS_DATA
        try :
            if cont_id not in PREVIOUS_DATA :
                PREVIOUS_DATA[cont_id] = {}
            
            PREVIOUS_DATA[cont_id][key] = data
            PREVIOUS_DATA[cont_id]["flag"] = True
        except Exception as e:
            AgentLogger.log(AgentLogger.COLLECTOR, "DOCKER_LOG: " +  "Error in updating PREVIOUS_DATA Reason : {0} : Previous Data :{1}".format(e, repr(PREVIOUS_DATA)))
    
    def makeFalse(self):
        global PREVIOUS_DATA
        try :
            for key in PREVIOUS_DATA :
                PREVIOUS_DATA[key]["flag"] = False
        except Exception as e:
            AgentLogger.log(AgentLogger.COLLECTOR, "DOCKER_LOG: Error in make False to previous data Reason : {0}, Data : {1}".format(e, repr(PREVIOUS_DATA)))
    
    def deleteOldData(self):
        global PREVIOUS_DATA
        previous_data = deepcopy(PREVIOUS_DATA)
        try :
            for key in previous_data :
                if not previous_data[key]['flag'] : 
                    del PREVIOUS_DATA[key]

        except IndexError as ie : 
            AgentLogger.log(AgentLogger.COLLECTOR, "DOCKER_LOG: " +  "Error in deleting old PREVIOUS_DATA Reason : {0} : Previous Data :{1}".format(ie, repr(PREVIOUS_DATA)))
    
    def getPreviousData(self, cont_id, key):
        global PREVIOUS_DATA
        try :
            if cont_id in PREVIOUS_DATA :
                if key in PREVIOUS_DATA[cont_id]:
                    return PREVIOUS_DATA[cont_id][key]
        except Exception as e :
            AgentLogger.log(AgentLogger.COLLECTOR, "DOCKER_LOG: Error in getting prevdata Reason : {0} for cont_id :{1}, key : {2} in Prev Data :{3}".format(e, cont_id, key, repr(PREVIOUS_DATA)))
        return 0   
            
    def addPerformanceData(self, cont_id, temp_conf):

        try :
            if DockUtils.compare_version(self.getApiVersion(), '1.17') > 0 :
                contPerfData = CgroupDataCollection().getContPerfData(cont_id)
            else :
                contPerfData = self.statsContainer(cont_id)
            #AgentLogger.log(AgentLogger.COLLECTOR, "container performance data : {0}".format(contPerfData))
            
            if contPerfData and "blkio_stats" in contPerfData:
                DockUtils.updateBlkioStats(contPerfData["blkio_stats"])
                temp_conf["BlkioPerf"] = contPerfData["blkio_stats"]
                
            if contPerfData and "cpu_stats" in contPerfData:
                contPerfData["cpu_stats"]["cpu_percent"] = str(
                    DockUtils.calcuateCpuPercent(
                        self.getPreviousData(cont_id, "total_usage"), 
                        self.getPreviousData(cont_id, "system_cpu_usage"), 
                        contPerfData["cpu_stats"]
                    )
                )
                
                self.updatePreviousData(cont_id, "total_usage", contPerfData["cpu_stats"]["cpu_usage"]["total_usage"])
                self.updatePreviousData(cont_id, "system_cpu_usage", contPerfData["cpu_stats"]["system_cpu_usage"])
                temp_conf["CpuPerf"] = contPerfData["cpu_stats"]
                
            if contPerfData and "memory_stats" in contPerfData:
                DockUtils.updateMemoryStats(contPerfData["memory_stats"])
                contPerfData["memory_stats"]["memory_percent"] = str(DockUtils.calculateMemoryPercentage(contPerfData["memory_stats"]))
                temp_conf["MemoryPerf"] = contPerfData["memory_stats"]
                
            if contPerfData and "network" in contPerfData:
                DockUtils.updateNetworkStats(contPerfData["network"])
                temp_conf["NetworkPerf"] = contPerfData["network"]
            
            if contPerfData and "networks" in contPerfData:
                #AgentLogger.log(AgentLogger.COLLECTOR, "inside networks : {0}".format(contPerfData["networks"]))
                networks=DockUtils.updateLatestNetworkStats(contPerfData["networks"])
                temp_conf["NetworkPerf"] = networks
        except Exception as e:
            AgentLogger.log(AgentLogger.COLLECTOR, "DOCKER_LOG: " +  "Exception in performance data collection : {0}".format(e))
            
    def _getContainersData(self):
        '''Update container specific data'''
        flag = False
        dictData = {}
        listNetPerf = ['rx_bytes','tx_bytes','traffic']
        listCpuPerf = ['cpu_percent']
        listMemoryPerf = ['active_anon','inactive_anon','active_file','inactive_file','cache','pgpgin','pgpgout','rss','unevictable']
        try:   
            containers = self.containers(all_cont=True) # Get List for containers
            if containers == None :
                AgentLogger.log(AgentLogger.COLLECTOR, "DOCKER_LOG: " +  "Error in Containers Data Collection")
                return 
            self.makeFalse()
            dict_Site247Id = DockUtils.getSite24X7IdDict("Containers");
            
            if dict_Site247Id is None:
                len_id = 0
            else :
                len_id = len(dict_Site247Id)
            count = 0
            allowed_cont = DockUtils.getAllowedContainerSize()
            for cont in containers : # iterate through container list
                if count < allowed_cont :
                    tempCont = {}
                    if "Id" not in cont : # If id is not available return go for the next containers
                        continue
                    container = self.inspectContainer(cont["Id"])
                    if "State" in container :
                        if "Running" in container["State"]:
                            flag = container["State"]["Running"]
                        else:
                            continue
                    else :
                        continue
                    if dict_Site247Id is None:
                        if not flag :
                            continue
                    else :
                        if cont["Id"] not in dict_Site247Id :
                            if not flag or count + len_id > allowed_cont :
                                continue        
                        else : 
                            len_id = len_id - 1
                    if "Created" in cont : # if Creation time is available the copy it to final dictionary
                        tempCont["Created"] = cont["Created"] * 1000
                    DockUtils.addSite24X7Ids(cont["Id"], tempCont, dict_Site247Id)
                    self._updateContConfData(container, tempCont)   # update tempCont for configuration data
                    tempCont['portBind'] = ''
                    self.joinData(tempCont['Ports'], "Ports", tempCont)
                    del tempCont['Ports']
                    self.joinData(tempCont['ExposedPorts'], "Exposed Ports", tempCont)
                    del tempCont['ExposedPorts'] 
                    if tempCont['PortBindings']:
                        listKey = list(tempCont['PortBindings'].keys())
                        stringList = []
                        for i in listKey:
                            string = str(i) + "-" + str(tempCont['PortBindings'][i])
                            string = string.replace("{","(")
                            string = string.replace("}",")")
                            stringList.append(string)
                        myString = ",".join(stringList )
                        tempCont['portBind'] = tempCont['portBind'] + "Bindings : "+myString+";"
                    else:
                        tempCont['portBind'] = tempCont['portBind'] + "Bindings : -"+";"
                    del tempCont['PortBindings']
                    if tempCont['Volumes']:
                        stringList = []
                        for key in tempCont['Volumes']:
                            string = "Vol - " + key + ",Mapping - " + tempCont['Volumes'][key] + ",R/W - " + str(tempCont['VolumesRW'][key])
                            stringList.append(string)
                        myString = ";".join(stringList)
                        tempCont['volumeBind'] = myString
                    else:
                        tempCont['volumeBind'] = '-'
                    del tempCont['Volumes']
                    del tempCont['VolumesRW']
                    del tempCont['Binds']
                    
                    if flag:
                        self.addPerformanceData(cont["Id"], tempCont) # Update tempCont for performance specific data
                        if 'NetworkPerf' in tempCont:
                            self.parseData(tempCont, listNetPerf, tempCont['NetworkPerf'])
                            del tempCont['NetworkPerf']
                        if 'CpuPerf' in tempCont:
                            self.parseData(tempCont, listCpuPerf, tempCont['CpuPerf'])
                            del tempCont['CpuPerf']
                        if 'MemoryPerf' in tempCont:
                            if 'stats' in tempCont['MemoryPerf']:
                                self.parseData(tempCont, listMemoryPerf, tempCont['MemoryPerf']['stats'])
                            del tempCont['MemoryPerf']
                        if 'BlkioPerf' in tempCont:
                            self.calIO(tempCont['BlkioPerf'], tempCont)
                            del tempCont['BlkioPerf']
                    dictData.setdefault(tempCont["Id"],tempCont)
                    count = count + 1
            self.checkDeleted(dict_Site247Id,dictData)
            self.deleteOldData()
        except Exception as e:
            AgentLogger.log([AgentLogger.COLLECTOR,AgentLogger.STDERR], "DOCKER_LOG: " +  "Exception in containers Update : "+repr(e))
            traceback.print_exc()    
        return dictData
    
    def checkDeleted(self,temp_site24X7Id,data):
        if temp_site24X7Id:
            for id in temp_site24X7Id:
                if id not in data:
                    data[id]={}
                    data[id]['cid'] = temp_site24X7Id[id]
                    data[id]['deleted'] = True
    
            
    def joinData(self,data,string,tempCont):
        if data:
            listKey = list(data.keys())
            myString = ",".join(listKey)
            tempCont['portBind'] = tempCont['portBind'] + string + " : "+ myString+";"
        else:
            tempCont['portBind'] = tempCont['portBind'] + string + " : -"+";"
        
    def parseData(self,dataCopy,listNode,dataNode):
        for i in listNode:
            dataCopy[i] = dataNode[i]
    
    def calIO(self,perfIO,dataCopy):
        readSum, writeSum, syncSum, asyncSum, totalSum = 0.0, 0.0, 0.0, 0.0, 0.0
        for each_io,value in perfIO.items():
            if each_io != 'io_queue_recursive':
                for each_op in perfIO[each_io]:
                    if each_op['op'] == 'Read':
                        readSum = readSum + float(each_op['value'])
                    elif each_op['op'] == 'Write':
                        writeSum = writeSum + float(each_op['value'])
                    elif each_op['op'] == 'Total':
                        totalSum = totalSum + float(each_op['value'])
                    '''elif each_op['op'] == 'Sync':
                        syncSum = syncSum + float(each_op['value'])
                    elif each_op['op'] == 'Async':
                        asyncSum = asyncSum + float(each_op['value'])'''
                    
        dataCopy['IORead'] = readSum
        dataCopy['IOWrite'] = writeSum
        dataCopy['IOTotal'] = totalSum
        #dataCopy['IOSync'] = syncSum
        #dataCopy['IOAsync'] = asyncSum
 
    def _getImagesData(self): 
        dict_imageData = {}
        try:
            temp_list = self.images()
            count = 0
            dict_Site247Id = DockUtils.getSite24X7IdDict("Images");
            if dict_Site247Id is None:
                len_id = 0
            else :
                len_id = len(dict_Site247Id)
                
            allowed_image = DockUtils.getAllowedContainerSize()
            
            for dict_image in temp_list :
                if count < allowed_image :
                    if dict_Site247Id :
                        if dict_image["Id"] not in dict_Site247Id :
                            if count + len_id > allowed_image :
                                continue 
                        else :
                            len_id = len_id -1
                    DockUtils.addSite24X7Ids(dict_image["Id"], dict_image, dict_Site247Id)
                    if 'Labels' in dict_image:
                        del dict_image['Labels']
                    if 'RepoDigests' in dict_image:
                        del dict_image['RepoDigests']
                    dict_image['RepoTags'] = ','.join(dict_image['RepoTags'])
                    dict_imageData.setdefault(dict_image['Id'],dict_image)
                    count = count + 1
                else :
                    break
            self.checkDeleted(dict_Site247Id,dict_imageData)
        except Exception as e:
            AgentLogger.log(AgentLogger.COLLECTOR, "DOCKER_LOG: " +  "Exception in getting image data : {0}".format(e))
        return dict_imageData
            

    def _getEventsData(self):
        ''' Get the all the newly available events'''
        
        dataObj = None
        try:
            global LAST_COLLECT_TIME
            global DATA_COLLECTION_TIME_DIFF
            current_time = int(time.time())

            dataObj = self.events(LAST_COLLECT_TIME or current_time - DATA_COLLECTION_TIME_DIFF, current_time) 
            if not dataObj:
                return []
            LAST_COLLECT_TIME = current_time
        except Exception as e :
            AgentLogger.log(AgentLogger.COLLECTOR, "DOCKER_LOG: " +  "Exception in updating events: {0}".format(e))
            traceback.print_exc()
        return dataObj
    def _parse_event_data(self, eventsDataList, containerData, imageData):
        try:
            i = 0
            for event in eventsDataList:
                
                if 'time' in event:
                    event['time'] = event['time'] * 1000   
                if 'id' in event:
                    eventId = event['id']
                    if eventId in containerData:
                        if 'Name' in containerData[eventId]:
                            event['Name'] = containerData[eventId]['Name']
                    elif eventId in imageData:
                        if 'RepoTags' in imageData[eventId]:
                            event['Name'] = imageData[eventId]['RepoTags']
                    else:
                        event['name'] = "None"
                event['ct'] = int(AgentUtil.getTimeInMillis()) + i
                i += 1
        except Exception as e:
            AgentLogger.log(AgentLogger.COLLECTOR, "DOCKER_LOG: " +  "Exception in parsing events data: {0}".format(e))
            traceback.print_exc()
        return eventsDataList;
    def getDockerData(self):
        dictDockerData = {}
        try :
            dictDockerData["Containers"] = self._getContainersData()
            dictDockerData["Images"] = self._getImagesData()
            dictDockerData["Events"] = self._parse_event_data(self._getEventsData(), dictDockerData["Containers"],dictDockerData["Images"]) 
            dictDockerData["ct"] = int(AgentUtil.getTimeInMillis())
            str_hostname = socket.gethostname()
            if str_hostname == 'localhost':
                str_hostname = AgentUtil.AGENT_CONFIG.get('AGENT_INFO', 'agent_ip_address')
            dictDockerData["HostName"] =  str_hostname
            dictDockerData["DOCKER"] = self.version_info()
            dictDockerData['mid'] = AgentUtil.AGENT_CONFIG.get('APPS_INFO', 'docker_key')
            AgentLogger.debug(AgentLogger.COLLECTOR, "DOCKER_LOG: " + json.dumps(dictDockerData))
        except Exception as e:
            AgentLogger.log([AgentLogger.COLLECTOR,AgentLogger.STDERR], "DOCKER_LOG: " +  "Exception in docker data collection "+ repr(e))
            traceback.print_exc()
        return dictDockerData
    
    def collectDockerData(self):
        '''Dump docker data in to the file'''
        dictDockerData = None
        try :
            if not self.running or not self.sock_path:
                AgentLogger.log(AgentLogger.COLLECTOR, "DOCKER_LOG: " +  "Docker is not running or Unable to find socket")
                return
            dictDockerData = self.getDockerData()
            AgentLogger.debug(AgentLogger.COLLECTOR, "DOCKER_LOG: " + "Docker Data collected   :  " + json.dumps(dictDockerData))
        except Exception as e:
            AgentLogger.log(AgentLogger.COLLECTOR, "DOCKER_LOG: " + "Exception in docker Dumping {0} : ".format(e))
        return dictDockerData


def startContainer(cont_id):
    global UNKNOWN_ERROR
    dictDataToSend = {}
    strResult = None
    try :
        ddc = DockerDataCollector()
        resp = ddc.startContainer(cont_id)
        if resp == None  :
            AgentLogger.log(AgentLogger.COLLECTOR, "DOCKER_LOG: " + "Unknown Error occurred during starting container {0} : ".format(cont_id))
            strResult = "Unknown Error occurred"
            rspCode = 100
        elif resp.status == 204 :
            AgentLogger.log(AgentLogger.COLLECTOR, "DOCKER_LOG: " + "Container started Successfully: {0} : ".format(cont_id))
            strResult = "Container started Successfully"
            rspCode = 101
        elif resp.status == 304 :
            AgentLogger.log(AgentLogger.COLLECTOR, "DOCKER_LOG: " + "Container already running : {0} : ".format(cont_id))
            strResult = "Container already running"
            rspCode = 102
        elif resp.status == 404 :
            AgentLogger.log(AgentLogger.COLLECTOR, "DOCKER_LOG: " + "Container does not exist :{0} : ".format(cont_id))
            strResult = "Container does not exist"
            rspCode = 103
        elif resp.status == 500 :
            AgentLogger.log(AgentLogger.COLLECTOR, "DOCKER_LOG: " + "Server Error : {0} : ".format(cont_id))
            strResult = "Docker server error"
            rspCode = 104
        else :
            AgentLogger.log(AgentLogger.COLLECTOR, "DOCKER_LOG: " + "Unknown status in starting container: {0} : ".format(cont_id))
            strResult = "Unknown status error"
            rspCode = 109
        dictDataToSend['MONKEY'] = cont_id
        dictDataToSend['RESULT'] = rspCode
        #BasicClientHandler.uploadData(dictDataToSend,'DOCKER_INSTANT_NOTIFIER')
        #return resp.status
        
    except Exception as e :
        AgentLogger.log(AgentLogger.COLLECTOR, "DOCKER_LOG: " + "Exception Occurred during Starting Container :{0} ".format(cont_id))
        traceback.print_exc()
    #return 0

def stopContainer(cont_id):
    global UNKNOWN_ERROR
    dictDataToSend = {}
    strResult = None
    try :
        ddc = DockerDataCollector()
        resp = ddc.stopContainer(cont_id)
        if resp == None  :
            AgentLogger.log(AgentLogger.COLLECTOR, "DOCKER_LOG: " + "Unknown Error occurred during stopping container {0} : ".format(cont_id))
            strResult = "Unknown Error occurred"
            rspCode = 900
        elif resp.status == 204 :
            AgentLogger.log(AgentLogger.COLLECTOR, "DOCKER_LOG: " + "Container stopped Successfully: {0} : ".format(cont_id))
            strResult = "Container started Successfully"
            rspCode = 901
        elif resp.status == 304 :
            AgentLogger.log(AgentLogger.COLLECTOR, "DOCKER_LOG: " + "Container already stopped : {0} : ".format(cont_id))
            strResult = "Container already running"
            rspCode = 902
        elif resp.status == 404 :
            AgentLogger.log(AgentLogger.COLLECTOR, "DOCKER_LOG: " + "Container does not exist :{0} : ".format(cont_id))
            strResult = "Container does not exist"
            rspCode = 903
        elif resp.status == 500 :
            AgentLogger.log(AgentLogger.COLLECTOR, "DOCKER_LOG: " + "Server Error : {0} : ".format(cont_id))
            strResult = "Docker server error"
            rspCode = 904
        else :
            AgentLogger.log(AgentLogger.COLLECTOR, "DOCKER_LOG: " + "Unknown status : stopping container: {0} : ".format(cont_id))
            strResult = "Unknown status error"
            rspCode = 909
        dictDataToSend['MONKEY'] = cont_id
        dictDataToSend['RESULT'] = rspCode
        #BasicClientHandler.uploadData(dictDataToSend,'DOCKER_INSTANT_NOTIFIER')
        #return resp.status
    except Exception as e :
        AgentLogger.log(AgentLogger.COLLECTOR, "DOCKER_LOG: " + "Exception Occurred During Stopping Container :{0} ".format(cont_id))
        traceback.print_exc()
    #return 0

def sendDockerDataToServer(dictRegData):
    dict_requestParameters = {}
    str_url = None
    dock_key = 'None'
    try:
        '''zipAndUploadInfo = FileZipAndUploadInfo()
        zipAndUploadInfo.filesToZip = None'''
        dict_requestParameters['agentKey'] = AgentUtil.AGENT_CONFIG.get('AGENT_INFO', 'agent_key')
        dict_requestParameters['CUSTOMERID'] = AgentConstants.CUSTOMER_ID
        #dict_requestParameters['productVersion'] = AgentUtil.AGENT_CONFIG.get('AGENT_INFO', 'agent_version')
        dict_requestParameters['docker'] = 'true'
        dict_requestParameters['bno'] = AgentConstants.AGENT_VERSION
        dict_requestParameters['REDISCOVER'] = "TRUE"
        if 'Os' and 'Arch' in dictRegData:
            dict_requestParameters['OsArch'] = dictRegData['Os'] + "-" +dictRegData['Arch']
        else:
            dict_requestParameters['OsArch'] = "None"
        if 'Version' in dictRegData:
            dict_requestParameters['Version'] = dictRegData['Version']
        else:
            dict_requestParameters['Version'] = "None"
        '''zipAndUploadInfo.setUploadMethod(AgentConstants.HTTP_GET)
        zipAndUploadInfo.uploadRequestParameters = dict_requestParameters'''
        str_servlet = AgentConstants.APPLICATION_DISCOVERY_SERVLET
        if not dict_requestParameters == None:
            str_requestParameters = urlencode(dict_requestParameters)
            str_url = str_servlet + str_requestParameters
        requestInfo = CommunicationHandler.RequestInfo()
        requestInfo.set_loggerName(AgentLogger.STDOUT)
        requestInfo.set_method(AgentConstants.HTTP_GET)
        requestInfo.set_url(str_url)
        #requestInfo.set_data(str_dataToSend)
        requestInfo.set_dataType('application/json')
        requestInfo.add_header("Content-Type", 'application/json')
        requestInfo.add_header("Accept", "text/plain")
        requestInfo.add_header("Connection", 'close')
        AgentLogger.log(AgentLogger.STDOUT, "=========================== STARTING DOCKER REGISTRATION ========================")
        (bool_isSuccess, errorCode, dict_responseHeaders, dict_responseData) = CommunicationHandler.sendRequest(requestInfo)
        if dict_responseHeaders and 'dockerkey' in dict_responseHeaders:
            dock_key = dict_responseHeaders['dockerkey']
        #CommunicationHandler.handleResponseHeaders(dict_responseHeaders, dict_responseData, 'FILE UPLOADER')
        if bool_isSuccess:
            AgentLogger.log(AgentLogger.STDOUT, " Server accepted data ")
        #zipAndUploadInfo.uploadData = json.dumps(dictDataToSend)
        #AgentBuffer.getBuffer(AgentConstants.FILES_TO_UPLOAD_BUFFER).add(zipAndUploadInfo)
    except Exception as e:
        AgentLogger.log(AgentLogger.STDOUT, " Exception while sending data {0}".format(e) )
        traceback.print_exc()
    return dock_key
    
def deleteMonitoring():
    try:
        AgentLogger.log(AgentLogger.STDOUT, "=============== Deleting/Suspending Docker Monitoring =====================")
        AgentConstants.AGENT_DOCKER_ENABLED = 0
        DockUtils.updateSite24X7Ids("{}")
        AgentUtil.AGENT_CONFIG.set('APPS_INFO','docker_enabled',0)
        AgentUtil.persistAgentInfo()
    except Exception as e:
        AgentLogger.log(AgentLogger.STDOUT, " Exception while activating docker " )
        traceback.print_exc()
def suspendMonitoring():
    try:
        AgentLogger.log(AgentLogger.STDOUT, "=============== Deleting/Suspending Docker Monitoring =====================")
        AgentConstants.AGENT_DOCKER_ENABLED = 0
        AgentUtil.AGENT_CONFIG.set('APPS_INFO','docker_enabled',0)
        AgentUtil.persistAgentInfo()
    except Exception as e:
        AgentLogger.log(AgentLogger.STDOUT, " Exception while activating docker " )
        traceback.print_exc()
    
def activateDocker():
    try:
        AgentLogger.log(AgentLogger.STDOUT, "=============== Activating Docker Monitoring =====================")
        AgentUtil.AGENT_CONFIG.set('APPS_INFO', 'docker_enabled',1)
        AgentUtil.persistAgentInfo()
        AgentConstants.AGENT_DOCKER_ENABLED = 1
    except Exception as e:
        AgentLogger.log(AgentLogger.STDOUT, " Exception while activating docker " )
        traceback.print_exc()

def rediscoverDocker():
    try:
        AgentLogger.log(AgentLogger.STDOUT, "=============== Rediscovering Docker Monitoring =====================")
        strRediscover = True
        AgentUtil.AGENT_CONFIG.set('APPS_INFO', 'docker_key', AgentConstants.DEFAULT_DOCKER_KEY)
        AgentUtil.AGENT_CONFIG.set('APPS_INFO', 'docker_enabled',1)
        AgentConstants.AGENT_DOCKER_ENABLED = 1
        AgentUtil.persistAgentInfo()
        initializeDocker()
    except Exception as e:
        AgentLogger.log(AgentLogger.STDOUT, " Exception while rediscovering docker " )
        traceback.print_exc()

def initializeDocker():
    dockerStatus = "Installed"
    try :        
        currKey = AgentUtil.AGENT_CONFIG.get('APPS_INFO', 'docker_key')
        
        if currKey == AgentConstants.DEFAULT_DOCKER_KEY:
            AgentLogger.log(AgentLogger.STDOUT, " Registration required for docker as dock_key is in default value")
            regClient = DockerDataCollector()
            if not regClient.running or not regClient.sock_path:
                dockerStatus = "False"
                AgentConstants.AGENT_DOCKER_INSTALLED = 0
                AgentLogger.log(AgentLogger.STDOUT, "Application Check - DOCKER not Found  \n")
                return
            regData = regClient.version_info()
            if regData:
                dock_key = sendDockerDataToServer(regData)
                if dock_key != AgentConstants.DEFAULT_DOCKER_KEY and dock_key != 'None':
                    AgentUtil.AGENT_CONFIG.set('APPS_INFO', 'docker_key',str(dock_key))
                    AgentLogger.log(AgentLogger.MAIN, "Docker key received from server : " + str(dock_key)+"\n")
                    AgentUtil.persistAgentInfo()
                elif dock_key == 'None':
                    AgentLogger.log([AgentLogger.MAIN,AgentLogger.CRITICAL], "DOCKER KEY not returned from server \n")
                    dockerStatus = "NoKey"
            else:
                dockerStatus = "False"
                AgentConstants.AGENT_DOCKER_INSTALLED = 0
                AgentLogger.log(AgentLogger.STDOUT, "============= DOCKER Application not  Found ================ \n")
        else:
            AgentLogger.log(AgentLogger.STDOUT, " Docker Monitor Registered with key -- {0} ".format(currKey))
    except Exception as e:
        dockerStatus = "Error"
        AgentConstants.AGENT_DOCKER_INSTALLED = 0
        AgentLogger.log(AgentLogger.STDOUT, "DOCKER_LOG: Error in registering Docker Client")
        traceback.print_exc()
    finally:
        AgentLogger.log(AgentLogger.STDOUT, "DOCKER Installed : " + str(AgentConstants.AGENT_DOCKER_INSTALLED))
        AgentLogger.log(AgentLogger.STDOUT, "DOCKER Enabled : " + str(AgentConstants.AGENT_DOCKER_ENABLED))
        AgentLogger.log(AgentLogger.STDOUT, "DOCKER Status : " + str(dockerStatus))
