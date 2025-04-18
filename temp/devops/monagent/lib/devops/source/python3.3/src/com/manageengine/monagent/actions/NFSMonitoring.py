#$Id$
import json
import os
import time
import traceback
import threading
from six.moves.urllib.parse import urlencode
from com.manageengine.monagent import AgentConstants
#from com.manageengine.monagent.communication import CommunicationHandler
from com.manageengine.monagent.logger import AgentLogger
from com.manageengine.monagent.util import AgentBuffer
from com.manageengine.monagent.util import AgentUtil
from com.manageengine.monagent.util import DesignUtils
from com.manageengine.monagent.util.AgentUtil import FileUtil, FileZipAndUploadInfo, Executor

NFSUtil = None

class NFS():
    def __init__(self):
        self.id = None
        self.path = None
        self.timeout = AgentConstants.DEFAULT_SCRIPT_TIMEOUT
        self.dused_dict = None
        self.dfree_dict = None
        self.duper_dict = None
        self.dfper_dict = None
        
    def setNFSDetails(self,dictDetails):
        try:
            self.id = dictDetails['id']
            self.path = dictDetails['nfspath'].rstrip('/')
            self.dused_dict = dictDetails.get('dused', None)
            self.dfree_dict = dictDetails.get('dfree', None)
            self.duper_dict = dictDetails.get('duper', None)
            self.dfper_dict = dictDetails.get('dfper', None)
            self.timeout = dictDetails.get('timeout', AgentConstants.DEFAULT_SCRIPT_TIMEOUT)
        except Exception as e:
            AgentLogger.log([AgentLogger.CHECKS,AgentLogger.STDERR],' *************************** Exception while setting NFS monitor details *************************** '+ repr(e))
            traceback.print_exc()
    
    def executeScript(self):
        dictToReturn = {}
        status = False
        try:
            executorObj = AgentUtil.Executor()
            executorObj.setLogger(AgentLogger.CHECKS)
            executorObj.setTimeout(self.timeout)
            command = AgentConstants.AGENT_NFS_MONITORING_SCRIPT + " " + self.path
            AgentLogger.log(AgentLogger.CHECKS,'NFS Command is '+repr(command))
            executorObj.setCommand(command)
            executorObj.executeCommand()
            status = executorObj.isSuccess()
            retVal = executorObj.getReturnCode()
            dictToReturn['output'] = executorObj.getStdOut().strip()
            dictToReturn['error'] = AgentUtil.getModifiedString(executorObj.getStdErr(),100,100)
        except Exception as e:
            AgentLogger.log([AgentLogger.CHECKS,AgentLogger.STDERR],'*************************** Exception while NFS monitor execution *************************** '+ repr(e))
            traceback.print_exc()
        finally:
            AgentLogger.log(AgentLogger.CHECKS,'NFS script output '+repr(dictToReturn))
            return status, dictToReturn
    
    def parseStatsFile(self,filename):
        ms_dict = dict()
        key = ''
    
        #f = file(filename)
        f = open(filename)
        for line in f.readlines():
        #print line
            words = line.split()
            if len(words) == 0:
                continue
            if words[0] == 'device':
                key = words[4]
                new = [ line.strip() ]
            elif 'nfs' in words or 'nfs4' in words:
                key = words[3]
                new = [ line.strip() ]
            else:
                new += [ line.strip() ]
            ms_dict[key] = new
        f.close
        return ms_dict
    
    def nfs_usage_threshold(self, df_out):
        status = True
        msg = ''
        failed_attr_list = []
        try:
            df_list = df_out.split()
            dused = int(df_list[2])
            dfree = int(df_list[3])
            dtotal = dused + dfree
            duper = (dused / dtotal) * 100
            dfper = (dfree / dtotal) * 100
            # Negating the eval to DOWN when the condition fails
            if self.dused_dict:
                status = not eval("{} {} {}".format(dused, self.dused_dict['con'], self.dused_dict['val']))
                if not status: failed_attr_list.append({'name':'dused', 'val': dused,'th': self.dused_dict['val']})
                #if not status: msg = "Disk utilisation usage {} than {}".format(self.dused_dict['con'], self.dused_dict['val'])
            if self.dfree_dict:
                status = not eval("{} {} {}".format(dfree, self.dfree_dict['con'], self.dfree_dict['val']))
                if not status: failed_attr_list.append({'name':'dfree', 'val': dfree,'th': self.dfree_dict['val']})
                #if not status: msg = "Disk utilisation is {} than {}".format(self.dfree_dict['con'], self.dfree_dict['val'])
            if self.duper_dict:
                status = not eval("{} {} {}".format(duper, self.duper_dict['con'], self.duper_dict['val']))
                if not status: failed_attr_list.append({'name':'duper', 'val': duper,'th': self.duper_dict['val']})
                #if not status: msg = "Disk utilisation is {} than {}%".format(self.duper_dict['con'], self.duper_dict['val'])
            if self.dfper_dict:
                status = not eval("{} {} {}".format(dfper, self.dfper_dict['con'], self.dfper_dict['val']))
                if not status: failed_attr_list.append({'name':'dfper', 'val': dfper,'th': self.dfper_dict['val']})
                #if not status: msg = "Disk utilisation is {} than {}%".format(self.dfper_dict['con'], self.dfper_dict['val'])
            AgentLogger.log(AgentLogger.CHECKS, "NFS usage threshold -> status: {} | msg: {} ".format(repr(status), msg))
        except Exception as e:
            AgentLogger.log([AgentLogger.CHECKS,AgentLogger.STDERR],' *************************** Exception in checking nfs usage threshold *************************** '+ repr(e))
            traceback.print_exc()
        finally:
            return status, failed_attr_list, msg


    def nfsDC(self):#to be called from script handler
        nfs_data = {}
        msg = 0
        try:
            status, script_output = self.executeScript()
            AgentLogger.log(AgentLogger.CHECKS, "NFS script raw output: {}".format(script_output))
            if status and script_output:
                nfs_out, df_out = script_output['output'].split("|")
                if nfs_out == '-1':
                    msg = "No Mounting"
                    nfs_status = "0"
                else:
                    nfs_data['output'] = nfs_out
                    rpc_status = bool(int(nfs_out.split("%%")[1]))
                    usage_status, failed_attr_list, msg = self.nfs_usage_threshold(df_out)
                    nfs_status = str(int(usage_status and rpc_status))
            else:
                nfs_status = "0"
                msg = "NFS data collection error"

            nfs_data['status'] = nfs_status
            if 'error' in script_output: ' | '.join([msg, script_output['error']])
            if msg: nfs_data['msg'] = msg 
            if failed_attr_list: nfs_data['failed_attr'] = failed_attr_list
            # io_list=[]
            # read = 0.0
            # write = 0.0
            # try:
            #     if os.path.exists(AgentConstants.NFS_IO_FILE):
            #         fileDt=self.parseStatsFile(AgentConstants.NFS_IO_FILE)
            #         if self.path in fileDt:
            #             json_arr=fileDt[self.path]
            #             for data in json_arr:
            #                 if 'bytes:' in data:
            #                     ele=data
            #                     io_list=ele.split(' ')
            #                     break
            #         if not io_list==[]:
            #             firstEntry = io_list[0];
            #             tempList = firstEntry.split(':')
            #             io_list.pop(0)
            #             io_list.insert(0,(str(tempList[1]).strip()))
            #             read=float(io_list[0])+float(io_list[2])+float(io_list[4])+float(io_list[6])
            #             write=float(io_list[1])+float(io_list[3])+float(io_list[5])+float(io_list[7])
            # except Exception as e1:
            #         AgentLogger.log(AgentLogger.CHECKS,'[ Exception While Manipulating IO Read / Write ] '+repr(e1))
            #         traceback.print_exc()
        except Exception as e:
            AgentLogger.log([AgentLogger.CHECKS,AgentLogger.STDERR],'**********Exception in NFS Monitoring********** '+repr(e))
            traceback.print_exc()
        finally:
            AgentLogger.log(AgentLogger.CHECKS,'NFS final data '+repr(nfs_data))
            return nfs_data
    
    def parseData(self,dataToParse):
        listLineData = []
        parsedData = {}
        try:
            listLineData = dataToParse.split('\n')
            for eachLine in listLineData:
                temp = []
                temp = eachLine.split('%%')
                if len(temp) > 1:
                    parsedData[temp[0]] = int(temp[1])
        except Exception as e:
            AgentLogger.log([AgentLogger.CHECKS,AgentLogger.STDERR],'********Exception while parsing NFS DC*****'+repr(e))
            traceback.print_exc()
        finally:
            AgentLogger.log(AgentLogger.CHECKS,'only parsed data '+repr(parsedData))
            return parsedData

class NFSHandler(DesignUtils.Singleton):
    _nfs = {}
    _lock = threading.Lock()
    
    def __init__(self):
        self._loadCustomNFS()
    
    def _loadCustomNFS(self):
        try:
            fileObj = AgentUtil.FileObject()
            fileObj.set_filePath(AgentConstants.AGENT_CUSTOM_MONITORS_GROUP_FILE)
            fileObj.set_dataType('json')
            fileObj.set_mode('rb')
            fileObj.set_dataEncoding('UTF-8')
            fileObj.set_loggerName(AgentLogger.CHECKS)
            fileObj.set_logging(False)
            bool_toReturn, dict_monitorsInfo = FileUtil.readData(fileObj)
            with self._lock:
                for each_nfs in dict_monitorsInfo['MonitorGroup']['ChecksMonitoring']['NFSMonitoring']:
                    nfs = NFS()
                    nfs.setNFSDetails(each_nfs)
                    self.__class__._nfs[each_nfs['id']] = nfs
        except Exception as e:
            AgentLogger.log([AgentLogger.CHECKS,AgentLogger.STDERR], ' *************************** Exception while loading custom nfs for NFS monitoring  *************************** '+ repr(e))
            traceback.print_exc()
            
    def deleteAllNFS(self):
        try:
            for each_nfs in self.__class__._nfs:
                nfs = self.__class__._nfs[each_nfs]
                AgentLogger.log(AgentLogger.CHECKS,'Deleting NFS check with NFS id : '+repr(nfs.id))
            self.__class__._nfs.clear()
        except Exception as e:
            AgentLogger.log([AgentLogger.CHECKS,AgentLogger.STDERR], ' CheckError | *************************** Exception while deleting NFS checks *************************** '+ repr(e))
            traceback.print_exc()
    
    def reloadNFS(self):
        with self._lock:
            self.deleteAllNFS()
        self._loadCustomNFS()
    
    def checkNFSDC(self):
        dictDataToSend = {}
        try:
            with self._lock:
                for nfsId, nfs in self.__class__._nfs.items():
                    tempDict = {}
                    AgentLogger.log(AgentLogger.CHECKS,'Start DC for NFS id:'+repr(nfsId))
                    tempDict = nfs.nfsDC()
                    dictDataToSend.setdefault(nfsId,tempDict)
        except Exception as e:
            AgentLogger.log([AgentLogger.CHECKS,AgentLogger.STDERR],'************* Exception while DC of NFS****'+repr(e))
            traceback.print_exc()
        finally:
            return dictDataToSend
