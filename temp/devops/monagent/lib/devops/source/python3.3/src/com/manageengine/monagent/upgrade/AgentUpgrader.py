# $Id$
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
from com.manageengine.monagent.actions import AgentAction
import subprocess
import shutil
UPGRADE = False

def initialize():
    AgentLogger.log(AgentLogger.STDOUT, '================================= UPGRADER INITIALIZED =================================')
    AgentLogger.debug(AgentLogger.STDOUT, 'AGENT_UPGRADE_CONTEXT : '+str(AgentConstants.AGENT_UPGRADE_CONTEXT))
    AgentLogger.debug(AgentLogger.STDOUT, 'UPGRADE_FILE_NAME : '+str(AgentConstants.UPGRADE_FILE_NAME))
    AgentLogger.debug(AgentLogger.STDOUT, 'AGENT_UPGRADE_FILE_NAME : '+str(AgentConstants.AGENT_UPGRADE_FILE_NAME))
    AgentLogger.debug(AgentLogger.STDOUT, 'WATCHDOG_UPGRADE_FILE_NAME : '+str(AgentConstants.WATCHDOG_UPGRADE_FILE_NAME))    
    
    AgentConstants.UPGRADE_FILE = AgentConstants.AGENT_UPGRADE_DIR + '/'+ AgentConstants.UPGRADE_FILE_NAME
    AgentConstants.AGENT_UPGRADE_FILE = AgentConstants.AGENT_UPGRADE_DIR + '/'+ AgentConstants.AGENT_UPGRADE_FILE_NAME
    AgentConstants.WATCHDOG_UPGRADE_FILE = AgentConstants.AGENT_UPGRADE_DIR +'/'+ AgentConstants.WATCHDOG_UPGRADE_FILE_NAME
    AgentConstants.AGENT_UPGRADE_SAGENT_URL = '//' + AgentConstants.AGENT_UPGRADE_CONTEXT + '//' + AgentConstants.UPGRADE_FILE_URL_NAME
    AgentConstants.AGENT_UPGRADE_URL = '/' + AgentConstants.STATIC_UPGRADE_CONTEXT + '/' + AgentConstants.UPGRADE_FILE_URL_NAME
    
    AgentLogger.log(AgentLogger.STDOUT,'Agent Upgrade sagent URL :'+str(AgentConstants.AGENT_UPGRADE_SAGENT_URL))
    AgentLogger.log(AgentLogger.STDOUT, 'Agent Upgrade Url : '+str(AgentConstants.AGENT_UPGRADE_URL))
    AgentLogger.log(AgentLogger.STDOUT, 'UPGRADE_FILE : '+str(AgentConstants.UPGRADE_FILE))
    AgentLogger.log(AgentLogger.STDOUT, 'AGENT_UPGRADE_FILE : '+str(AgentConstants.AGENT_UPGRADE_FILE))
    AgentLogger.log(AgentLogger.STDOUT, 'WATCHDOG_UPGRADE_FILE : '+str(AgentConstants.WATCHDOG_UPGRADE_FILE))
    
    isMonAgentUpgraded()
    remove_old_entries()
    return True

def patchUpgrader():
    pass

def remove_old_entries():
    try:
        if os.path.isdir(AgentConstants.AGENT_BACKUP_DIR):
            shutil.rmtree(AgentConstants.AGENT_BACKUP_DIR)
        if os.path.isdir(AgentConstants.AGENT_UPGRADE_DIR):
            shutil.rmtree(AgentConstants.AGENT_UPGRADE_DIR)
        if not os.path.isdir(AgentConstants.AGENT_UPGRADE_DIR):
            os.mkdir(AgentConstants.AGENT_UPGRADE_DIR)
        if not os.path.isdir(AgentConstants.AGENT_BACKUP_DIR):
            os.mkdir(AgentConstants.AGENT_BACKUP_DIR)
    except Exception as e:
        AgentLogger.log(AgentLogger.STDERR,' ************************* Exception in remove_old_entries AgentUpgrader ************************* ')
        traceback.print_exc()

def handle_venv_upgrade(custom=False,upgrade_props=None):
    global UPGRADE
    if os.path.exists(AgentConstants.UPGRADE_DISABLE_FLAG_FILE):
        AgentLogger.log(AgentLogger.MAIN, "Upgrade disabled since upgrade disable file exists")
        AgentAction.ackAgentUpgradeStatus("Agent upgrade has been manually disabled during installation")
        return
    hash_val = None
    retry = True
    AgentAction.ackAgentUpgradeStatus(AgentConstants.UPGRADE_ACK_MSG,"ACK_UPGRADE")
    AgentConstants.BOOL_AGENT_UPGRADE = True
    AgentConstants.WATCHDOG_UPGRADE_MSG = ""
    devops_tar_file = os.path.join(AgentConstants.AGENT_UPGRADE_DIR, "devops.tar.gz")
    _download_status, _upgrade_status = False, True
    ack_dict={'action':'Source Agent Upgrade','msg':'checksum mismatch'}
    download_url = AgentConstants.AGENT_UPGRADE_URL
    try:
        UPGRADE = True
        if 'checksum' in upgrade_props:
            hash_val = upgrade_props['checksum'][AgentConstants.UPGRADE_FILE_NAME]
        if 'timeout' in upgrade_props and int(upgrade_props['timeout']) > 60:
            AgentConstants.WATCHDOG_UPGRADE_WAIT_TIME = int(upgrade_props['timeout'])
        if 'url' in upgrade_props:
            download_url = upgrade_props['url']
            download_url = download_url + "/" + AgentConstants.UPGRADE_FILE_NAME
            retry = False
            AgentLogger.log(AgentLogger.MAIN,'download url :: {}'.format(download_url))
        if custom:
            _download_status = CommunicationHandler.downloadCustomFile(AgentConstants.PLUS_DOWNLOAD_SERVLET, AgentConstants.UPGRADE_FILE, logger=AgentLogger.MAIN,checksum=hash_val,ack=ack_dict)
        else:
            _download_status = CommunicationHandler.downloadFile(download_url,AgentConstants.UPGRADE_FILE,logger=AgentLogger.MAIN,checksum=hash_val,host=AgentConstants.STATIC_SERVER_HOST,ack=ack_dict)
            if retry and not _download_status:
                AgentLogger.log(AgentLogger.MAIN,"PRE UPGRADE : Upgrade failure in Static Server | retrying via sagent : {0}".format(AgentConstants.AGENT_UPGRADE_SAGENT_URL))
                _download_status = CommunicationHandler.downloadFile(AgentConstants.AGENT_UPGRADE_SAGENT_URL, AgentConstants.UPGRADE_FILE, logger=AgentLogger.MAIN,checksum=hash_val,ack=ack_dict)
        if _download_status:
            AgentLogger.log(AgentLogger.MAIN, "File Successfully downloaded |  {}".format(AgentConstants.UPGRADE_FILE))
            AgentConstants.WATCHDOG_UPGRADE_MSG = AgentConstants.WATCHDOG_UPGRADE_MSG + "dltar-1|"
                    
            if WatchdogUpgrader.backup_handler():  
                tar_handle = AgentArchiver.getArchiver(AgentArchiver.TAR)
                tar_handle.setFile(AgentConstants.UPGRADE_FILE)
                tar_handle.setPath(AgentConstants.AGENT_UPGRADE_DIR)
                tar_handle.setMode('r:gz')
                tar_handle.decompress()
                tar_handle.close()
                AgentConstants.WATCHDOG_UPGRADE_MSG = AgentConstants.WATCHDOG_UPGRADE_MSG + "hutar-1|"
                
                tar_handle = AgentArchiver.getArchiver(AgentArchiver.TAR)
                tar_handle.setFile(devops_tar_file)
                tar_handle.setPath(AgentConstants.AGENT_UPGRADE_DIR)
                tar_handle.setMode('r:gz')
                tar_handle.decompress()
                tar_handle.close()
                AgentConstants.WATCHDOG_UPGRADE_MSG = AgentConstants.WATCHDOG_UPGRADE_MSG + "dvtar-1|"
                new_upgrade_bin_filepath = os.path.join(AgentConstants.AGENT_UPGRADE_DIR, "hybrid_monagent_upgrade")
                AgentUtil.check_module_settings()
                AgentLogger.log(AgentLogger.MAIN, 'UPGRADE : Copy from {} to {}'.format(new_upgrade_bin_filepath, AgentConstants.AGENT_VENV_UPGRADER_BIN))
                shutil.copy(new_upgrade_bin_filepath, AgentConstants.AGENT_VENV_UPGRADER_BIN)
                is_success, str_output = AgentUtil.executeCommand(AgentConstants.AGENT_WATCHDOG_STOP_COMMAND, AgentLogger.MAIN, 5)
                if AgentConstants.AGENT_WATCHDOG_SERVICE_STOPPED_MESSAGE in str_output:
                    AgentLogger.log(AgentLogger.MAIN, "UPGRADE : watchdog stopped successfully for upgrade")
                    AgentConstants.WATCHDOG_UPGRADE_MSG = AgentConstants.WATCHDOG_UPGRADE_MSG + "wdstp-1|"
                else:
                    AgentLogger.log(AgentLogger.MAIN, "UPGRADE : failed to stop watchdog for upgrade")
                    AgentConstants.WATCHDOG_UPGRADE_MSG = AgentConstants.WATCHDOG_UPGRADE_MSG + "wdstp-0|"
                try:
                    os.chmod(AgentConstants.AGENT_VENV_UPGRADER_BIN, 0o755)
                except Exception as e:
                    pass
                with open(AgentConstants.AGENT_UPGRADE_FLAG_FILE, "w") as fp:
                    fp.write("hybridagent")
                subprocess.Popen(AgentConstants.AGENT_VENV_UPGRADER_BIN+" &", shell=True, env={"COLUMNS":"500", "MON_AGENT_HOME":"{}".format(AgentConstants.AGENT_WORKING_DIR), "PYTHON_VENV_BIN_PATH":"{}".format(AgentConstants.AGENT_VENV_BIN_PYTHON)})
                
                _status, _msg = WatchdogUpgrader.get_upgrade_status()
                if _msg == "retry":
                    _status, _msg = WatchdogUpgrader.get_upgrade_status()
                if _status:
                    AgentLogger.log(AgentLogger.MAIN, "UPGRADE : success upgrade | msg:{}".format(_msg))
                    AgentConstants.WATCHDOG_UPGRADE_MSG = AgentConstants.WATCHDOG_UPGRADE_MSG + "wdupg-1|"
                else:
                    if os.path.isfile(AgentConstants.AGENT_UPGRADE_FLAG_FILE):    os.remove(AgentConstants.AGENT_UPGRADE_FLAG_FILE)
                    AgentLogger.log(AgentLogger.MAIN, "UPGRADE : failed upgrade | msg {}".format(_msg))
                    AgentConstants.WATCHDOG_UPGRADE_MSG = AgentConstants.WATCHDOG_UPGRADE_MSG + "wdupg-0|"
            else:
                UPGRADE = False
                _upgrade_status = False
                AgentLogger.log(AgentLogger.MAIN, 'UPGRADE :  Backup failed hence quitting')
        else:
            AgentLogger.log(AgentLogger.MAIN, "Upgrade Failure ::| {}".format(AgentConstants.UPGRADE_FILE))
            AgentConstants.WATCHDOG_UPGRADE_MSG = AgentConstants.WATCHDOG_UPGRADE_MSG + "dltar-0|"
            UPGRADE = False
            _upgrade_status = False
    except Exception as e:
        UPGRADE = False
        _upgrade_status = False
        AgentConstants.WATCHDOG_UPGRADE_MSG = AgentConstants.WATCHDOG_UPGRADE_MSG + "hdupg-2|"
        AgentLogger.log(AgentLogger.MAIN, "Error while upgrading Hybrid Agent | Reason : {} ".format(e))
        traceback.print_exc()
    finally:
        AgentConstants.BOOL_AGENT_UPGRADE = False

def isMonAgentUpgraded():
    try:
        if os.path.exists(AgentConstants.MON_AGENT_UPGRADED_FLAG_FILE):
            #add main log here
            AgentLogger.log(AgentLogger.STDOUT,'================================= MON_AGENT_UPGRADED_FLAG_FILE is present, hence assigning MON_AGENT_UPGRADED = True =================================')
            AgentConstants.MON_AGENT_UPGRADED = True
            #delete file here only
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
        if os.path.exists(AgentConstants.UPGRADE_DISABLE_FLAG_FILE):
            AgentLogger.log(AgentLogger.MAIN, "Upgrade disabled since upgrade disable file exists")
            AgentAction.ackAgentUpgradeStatus("Agent upgrade has been manually disabled during installation")
            return
        UPGRADE = True   
        watchdogUpgrader = WatchdogUpgrader()
        watchdogUpgrader.setLogger(AgentLogger)
        watchdogUpgrader.setUpgradeProps(var_obj)
        watchdogUpgrader.setUpgradeFile(AgentConstants.UPGRADE_FILE)
        if custom == True:
            AgentLogger.log(AgentLogger.MAIN,'UPGRADE : Inside patch upgrade ')
            watchdogUpgrader.upgrade(custom = True)
        else:
            AgentLogger.log(AgentLogger.MAIN,'UPGRADE : Inside normal upgrade ')
            watchdogUpgrader.upgrade()
    except Exception as e:
        AgentLogger.log(AgentLogger.MAIN, ' *************************** Exception While Handling Upgrade *************************** '+ repr(e))
        traceback.print_exc()
        
def downloadPatch(destination,untarDir):
    try:
        bool_toReturn = True
        bool_downloadStatus = CommunicationHandler.downloadCustomFile(AgentConstants.PLUS_DOWNLOAD_SERVLET, destination, AgentLogger.MAIN)
        if bool_downloadStatus:
            AgentLogger.log(AgentLogger.MAIN,'File downloaded successfully.')
            tarHandle = AgentArchiver.getArchiver(AgentArchiver.TAR)
            tarHandle.setFile(destination)
            tarHandle.setPath(untarDir)
            tarHandle.setMode('r:gz')
            tarHandle.decompress()
            tarHandle.close()
            AgentLogger.log(AgentLogger.MAIN,'Tar extracted successfully.')
    except Exception as e:
        AgentLogger.log(AgentLogger.MAIN,'Exception occurred while downloading and extracting the file.')
        traceback.print_exc()
        bool_toReturn = False
    finally:
        return bool_toReturn

def updatefilesfrompatch():
    try:
        bool_toReturn=downloadPatch(AgentConstants.UPGRADE_FILE,AgentConstants.AGENT_WORKING_DIR)
        if bool_toReturn:
            AgentLogger.log(AgentLogger.MAIN,'Creating Restart Flag.')
            AgentUtil.RestartAgent()
            str_uninstallTime = 'Restart : '+repr(datetime.fromtimestamp(time.time()).strftime("%Y-%m-%d %H:%M:%S"))
            file_obj = open(AgentConstants.AGENT_WATCHDOG_SILENT_RESTART_FLAG_FILE,'w')
            file_obj.write(str_uninstallTime)
            if not file_obj == None:
                file_obj.close()
            isSuccess, str_output = AgentUtil.executeCommand(AgentConstants.AGENT_WATCHDOG_STATUS_COMMAND, AgentLogger.MAIN, 5)
            AgentLogger.log(AgentLogger.MAIN,'WATCHDOG STATUS : '+str(isSuccess) +' : ' +str(str_output))
            if AgentConstants.AGENT_WATCHDOG_SERVICE_DOWN_MESSAGE in str_output:
                isBoolSuccess, str_out = AgentUtil.executeCommand(AgentConstants.AGENT_WATCHDOG_START_COMMAND, AgentLogger.MAIN, 5)
                AgentLogger.log(AgentLogger.MAIN,'STARTING WATCHDOG : '+str(isBoolSuccess) +' : ' +str(str_out))
                if AgentConstants.AGENT_WATCHDOG_SERVICE_STARTED_MESSAGE in str_out:
                    AgentLogger.log(AgentLogger.MAIN,'Watchdog started successfully.')
            else:
                isSuccess, str_output = AgentUtil.executeCommand(AgentConstants.AGENT_WATCHDOG_STOP_COMMAND, AgentLogger.MAIN, 5)
                AgentLogger.log(AgentLogger.MAIN,'STOPPING WATCHDOG : '+str(isSuccess) +' : ' +str(str_output))
                if AgentConstants.AGENT_WATCHDOG_SERVICE_STOPPED_MESSAGE in str_output:
                    isBoolSuccess, str_out = AgentUtil.executeCommand(AgentConstants.AGENT_WATCHDOG_START_COMMAND, AgentLogger.MAIN, 5)
                    AgentLogger.log(AgentLogger.MAIN,'STARTING WATCHDOG : '+str(isBoolSuccess) +' : ' +str(str_out))
                    if AgentConstants.AGENT_WATCHDOG_SERVICE_STARTED_MESSAGE in str_out:
                        AgentLogger.log(AgentLogger.MAIN,'Watchdog started successfully.')
        else:
            AgentLogger.log(AgentLogger.MAIN,'Upgrade File download failed.')
    except Exception as e:
        AgentLogger.log(AgentLogger.MAIN,'Exception occurred while updating the patch.')
        traceback.print_exc()


class Upgrader(DesignUtils.Singleton):
    def __init__(self):
        self.bool_isSuccess = False
        self.bool_inProgress = False
        self.str_upgradeFile = None
        self.logger = None
        self.dict_upgradeProps = None
    def setIsUpgradeSuccess(self, bool_isSuccess):
        self.bool_isSuccess = bool_isSuccess
    def isUpgradeSuccess(self):
        return self.bool_isSuccess
    def initiateUpgrade(self):
        return self.bool_initiateUpgrade
    def setUpgradeFile(self, str_upgradeFile):
        self.str_upgradeFile = str_upgradeFile
    def getUpgradeFile(self):
        return self.str_upgradeFile
    def setUpgradeProps(self, dict_upgradeProps):
        self.dict_upgradeProps = dict_upgradeProps
    def getUpgradeProps(self):
        return self.dict_upgradeProps
    def setLogger(self, logger):
        self.logger = logger
    def getLogger(self):
        return self.logger
    def log(self, str_message):
        if self.logger:
            self.logger.log(AgentLogger.MAIN, str_message)
    def setIsUpgradeInProgress(self, bool_inProgress):
        self.bool_inProgress = bool_inProgress
    def isUpgradeInProgress(self):
        return self.bool_inProgress
    def upgrade(self):
        raise NotImplementedError
    def preUpgrade(self):
        raise NotImplementedError
    def postUpgrade(self):
        raise NotImplementedError
    def upgradeAction(self):
        raise NotImplementedError

class WatchdogUpgrader(Upgrader):
    def __init__(self):
        super(WatchdogUpgrader, self).__init__()
    # Check whether agent needs upgrade with parameters from server.
    def initiateUpgrade(self):
        bool_isSuccess = True
        try: 
            if self.isUpgradeInProgress():
                self.log('INITIATE UPGRADE : =========================== UPGRADE ALREADY INITIATED ============================')
                AgentConstants.WATCHDOG_UPGRADE_MSG = AgentConstants.WATCHDOG_UPGRADE_MSG + "init-0|"
                AgentConstants.UPGRADE_USER_MESSAGE = "init-0"
                return False
            self.setIsUpgradeInProgress(True)
            self.log('INITIATE UPGRADE : =========================== UPGRADE INITIATED ============================')
            bool_isSuccess = True
            AgentConstants.WATCHDOG_UPGRADE_MSG = AgentConstants.WATCHDOG_UPGRADE_MSG + "init-1|"
        except Exception as e:
            self.setIsUpgradeInProgress(False)
            self.setIsUpgradeSuccess(False)
            bool_isSuccess = False
            AgentConstants.WATCHDOG_UPGRADE_MSG = AgentConstants.WATCHDOG_UPGRADE_MSG + "init-2|"
            self.log('INITIATE UPGRADE : *********************** Exception while trying to initiate upgrade *****************************')
            traceback.print_exc()
        return bool_isSuccess    
    # Step 1 : Download upgrade file
    # Step 2 : Stop watchdog service if it is running by any chance.
    def preUpgrade(self, custom=False):
        bool_isSuccess = True
        bool_downloadStatus = True
        hash_val = None
        download_url = AgentConstants.AGENT_UPGRADE_URL
        ack_dict={'action':'Agent Upgrade','msg':'checksum mismatch'}
        retry = True
        try:
            AgentLogger.log(AgentLogger.MAIN,'agent upgrade props :: {}'.format(self.dict_upgradeProps))
            if 'checksum' in self.dict_upgradeProps:
                hash_val = self.dict_upgradeProps['checksum'][AgentConstants.UPGRADE_FILE_URL_NAME]
            if 'timeout' in self.dict_upgradeProps and int(self.dict_upgradeProps['timeout']) > 60:
                AgentConstants.WATCHDOG_UPGRADE_WAIT_TIME = int(self.dict_upgradeProps['timeout'])
            if 'url' in self.dict_upgradeProps:
                download_url = self.dict_upgradeProps['url']
                download_url = download_url + "/" + AgentConstants.UPGRADE_FILE_URL_NAME
                retry = False
                AgentLogger.log(AgentLogger.MAIN,'download url :: {}'.format(download_url))
            AgentLogger.log(AgentLogger.MAIN,'expected hash from server :: {}'.format(hash_val))
            if custom == True:            
                bool_downloadStatus = CommunicationHandler.downloadCustomFile(AgentConstants.PLUS_DOWNLOAD_SERVLET, self.getUpgradeFile(), logger=AgentLogger.MAIN,checksum=hash_val,ack=ack_dict)    
            else:
                bool_downloadStatus = CommunicationHandler.downloadFile(download_url,self.getUpgradeFile(),logger=AgentLogger.MAIN,host=AgentConstants.STATIC_SERVER_HOST,checksum=hash_val,ack=ack_dict)
                if retry and not bool_downloadStatus:
                    self.log('PRE UPGRADE : Upgrade failure in Static Server | retrying via sagent : {0}'.format(AgentConstants.AGENT_UPGRADE_SAGENT_URL))
                    bool_downloadStatus = CommunicationHandler.downloadFile(AgentConstants.AGENT_UPGRADE_SAGENT_URL, self.getUpgradeFile(), logger=AgentLogger.MAIN,checksum=hash_val,ack=ack_dict)
            if bool_downloadStatus:
                self.log('PRE UPGRADE : Successfully downloaded the file to the path : '+str(self.getUpgradeFile()))
                AgentConstants.WATCHDOG_UPGRADE_MSG = AgentConstants.WATCHDOG_UPGRADE_MSG + "dowld-1|"
                isSuccess, str_output = AgentUtil.executeCommand(AgentConstants.AGENT_WATCHDOG_STATUS_COMMAND, AgentLogger.MAIN, 5)
                if AgentConstants.AGENT_WATCHDOG_SERVICE_DOWN_MESSAGE in str_output:
                    self.log('PRE UPGRADE : Monitoring Agent Watchdog Service is down. Can proceed watchdog upgrade')
                    AgentConstants.WATCHDOG_UPGRADE_MSG = AgentConstants.WATCHDOG_UPGRADE_MSG + "wdastp-1|"
                else:
                    isSuccess, str_output = AgentUtil.executeCommand(AgentConstants.AGENT_WATCHDOG_STOP_COMMAND, AgentLogger.MAIN, 5)
                    if AgentConstants.AGENT_WATCHDOG_SERVICE_STOPPED_MESSAGE in str_output:
                        self.log('PRE UPGRADE : Monitoring Agent Watchdog Service stopped successfully for upgrade')
                        AgentConstants.WATCHDOG_UPGRADE_MSG = AgentConstants.WATCHDOG_UPGRADE_MSG + "wdstp-1|"
                    else:
                        self.setIsUpgradeInProgress(False)
                        self.setIsUpgradeSuccess(False)
                        bool_isSuccess = False
                        AgentConstants.UPGRADE_USER_MESSAGE = "wdstp-0"
                        AgentConstants.WATCHDOG_UPGRADE_MSG = AgentConstants.WATCHDOG_UPGRADE_MSG + "wdstp-0|"
                        self.log('PRE UPGRADE : *************************** Failed to stop Monitoring Agent Watchdog Service before upgrade ***************************')            
            else:                
                self.setIsUpgradeInProgress(False)
                self.setIsUpgradeSuccess(False)
                bool_isSuccess = False
                AgentConstants.UPGRADE_USER_MESSAGE = "dowld-0"
                AgentConstants.WATCHDOG_UPGRADE_MSG = AgentConstants.WATCHDOG_UPGRADE_MSG + "dowld-0|"
                self.log('PRE UPGRADE : *********************** Upgrade Failure :: '+repr(self.getUpgradeFile())+'*****************************')
        except Exception as e:
            self.setIsUpgradeInProgress(False)
            self.setIsUpgradeSuccess(False)
            bool_isSuccess = False
            AgentConstants.WATCHDOG_UPGRADE_MSG = AgentConstants.WATCHDOG_UPGRADE_MSG + "preupg-2|"
            self.log('PRE UPGRADE : *********************** Exception while downloading the Upgrade file '+repr(self.getUpgradeFile())+' from the url : '+repr(download_url)+' *****************************')
            traceback.print_exc()
        return bool_isSuccess
    # Step 1 : Extract upgrade file that contains watchdogUpgrade.tar and agentUpgrade.tar
    # Step 2 : Extract watchdogUpgrade.tar 
    
    @staticmethod
    def backup_helper(src_path, dest_path, delete=True):
        _backup_status = False
        try:
            if os.path.exists(dest_path) and delete is True:
                shutil.rmtree(dest_path)
            shutil.copytree(src_path, dest_path)
            _backup_status = True
        except Exception as e:
            AgentLogger.log(AgentLogger.MAIN, "Exception in backup_helper | src_path {} | dest_path {}| Reason {}".format(src_path, dest_path, e))
        finally:
            return _backup_status
    
    @staticmethod
    def backup_handler():
        _backup_handler_status = False
        try:
            WatchdogUpgrader.backup_helper(AgentConstants.AGENT_LIB_DIR, AgentConstants.AGENT_BACKUP_DIR_LIB)
            WatchdogUpgrader.backup_helper(AgentConstants.AGENT_CONF_DIR, AgentConstants.AGENT_BACKUP_DIR_CONF)
            WatchdogUpgrader.backup_helper(AgentConstants.AGENT_SCRIPTS_DIR, AgentConstants.AGENT_BACKUP_DIR_SCRIPTS)
            WatchdogUpgrader.backup_helper(AgentConstants.AGENT_BIN_DIR, AgentConstants.AGENT_BACKUP_DIR_BIN)
            _backup_handler_status = True
            AgentConstants.WATCHDOG_UPGRADE_MSG = AgentConstants.WATCHDOG_UPGRADE_MSG + "wdbkp-1|"
        except Exception as e:
            AgentConstants.WATCHDOG_UPGRADE_MSG = AgentConstants.WATCHDOG_UPGRADE_MSG + "wdbkp-2|"
            AgentLogger.log(AgentLogger.MAIN, "Exception in backup_handler | Reason {}".format(e))
        finally:
            return _backup_handler_status

               
    def upgradeAction(self):    
        bool_isSuccess = True    
        try:
            if WatchdogUpgrader.backup_handler():
                self.log("UPGRADE : backup successful")
                # Extract upgrade tar
                self.log('UPGRADE : Extracting upgrade tar file : '+repr(self.getUpgradeFile()))
                tarHandle = AgentArchiver.getArchiver(AgentArchiver.TAR)
                tarHandle.setFile(self.getUpgradeFile())
                tarHandle.setPath(AgentConstants.AGENT_UPGRADE_DIR)
                tarHandle.setMode('r:gz')
                tarHandle.decompress()
                tarHandle.close()
                self.log('UPGRADE : Tar Extraction Successful')
                AgentConstants.WATCHDOG_UPGRADE_MSG = AgentConstants.WATCHDOG_UPGRADE_MSG + "lnxtar-1|"
                # Extract watchdog tar
                self.log('UPGRADE : Extracting upgrade tar file : '+repr(AgentConstants.WATCHDOG_UPGRADE_FILE))
                tarHandle = AgentArchiver.getArchiver(AgentArchiver.TAR)
                tarHandle.setFile(AgentConstants.WATCHDOG_UPGRADE_FILE)
                tarHandle.setPath(AgentConstants.AGENT_UPGRADE_DIR)
                tarHandle.setMode('r:gz')
                tarHandle.decompress()
                tarHandle.close()    
                self.log('UPGRADE : Tar Extraction Successful')
                AgentConstants.WATCHDOG_UPGRADE_MSG = AgentConstants.WATCHDOG_UPGRADE_MSG + "wdtar-1|"
                AgentUtil.check_module_settings()
                new_upgrade_bin_filepath = os.path.join(AgentConstants.AGENT_UPGRADE_DIR, "bin", "monagentupgrade")
                self.log('UPGRADE : Copy from {} to {}'.format(new_upgrade_bin_filepath, AgentConstants.AGENT_UPGRADER_BIN))
                shutil.copy(new_upgrade_bin_filepath, AgentConstants.AGENT_UPGRADER_BIN)
                self.log("UPGRADE : Monitoring agent upgrader started ")
                try:
                    os.chmod(AgentConstants.AGENT_UPGRADER_BIN, 0o755)
                except Exception as e:
                    pass
                subprocess.Popen(AgentConstants.AGENT_UPGRADER_BIN+" &", shell=True)
                AgentConstants.WATCHDOG_UPGRADE_MSG = AgentConstants.WATCHDOG_UPGRADE_MSG + "mgupg-1|"
            else:
                AgentLogger.log(AgentLogger.MAIN, "UPGRADE : Backup failed |  Hence stopped")
                self.setIsUpgradeInProgress(False)
                self.setIsUpgradeSuccess(False)            
                bool_isSuccess = False
        except Exception as e:     
            self.log('UPGRADE : ********************** Exception while extracting Tar file *************************')
            AgentConstants.WATCHDOG_UPGRADE_MSG = AgentConstants.WATCHDOG_UPGRADE_MSG + "upgac-2|"
            traceback.print_exc()
            self.setIsUpgradeInProgress(False)
            self.setIsUpgradeSuccess(False)            
            bool_isSuccess = False
        return bool_isSuccess
    # Step 1 : Create upgrade flag file
    # Step 2 : Start watchdog service   
    @staticmethod
    def get_upgrade_status():
        time.sleep(AgentConstants.WATCHDOG_UPGRADE_WAIT_TIME) # get configurable time from server side
        _status = True
        _msg = ""
        if os.path.isfile(AgentConstants.MON_AGENT_UPGRADE_NOTIFIER_FILE):
            with open(AgentConstants.MON_AGENT_UPGRADE_NOTIFIER_FILE, "r") as fp:
                _msg = fp.read()
        else:
            _status, _msg = False, "retry"
        if "FAILURE" in _msg:
            _status = False
        return _status, _msg  
            
    def postUpgrade(self):
        bool_isSuccess = True    
        try:
            def createTempUpgradeFile():
                bool_toReturn = True
                file_obj = None
                try:
                    self.log("UPGRADE : {} is created".format(AgentConstants.AGENT_UPGRADE_FLAG_FILE))
                    file_obj = open(AgentConstants.AGENT_UPGRADE_FLAG_FILE,'w')
                    file_obj.write(AgentConstants.AGENT_UPGRADE_FILE_NAME)
                except:
                    AgentLogger.log(AgentLogger.MAIN,' ************************* Exception while creating Upgrade Flag File : '+AgentConstants.AGENT_UPGRADE_FLAG_FILE+' ************************* ')
                    AgentConstants.WATCHDOG_UPGRADE_MSG = AgentConstants.WATCHDOG_UPGRADE_MSG + "tmpuf-2|"
                    traceback.print_exc()
                    bool_toReturn = False
                finally:        
                    if not file_obj == None:
                        file_obj.close()
                return bool_toReturn
            #self.log('command is -- '+repr(str_watchdogStartCommand))
            if createTempUpgradeFile():
                self.setIsUpgradeInProgress(False)
                self.setIsUpgradeSuccess(True)
                _status, _msg = WatchdogUpgrader.get_upgrade_status()
                if _msg == "retry":
                    _status, _msg = WatchdogUpgrader.get_upgrade_status()
                    if _status:
                        self.log("UPGRADE : success upgrade | msg:{}".format(_msg))
                        AgentConstants.WATCHDOG_UPGRADE_MSG = AgentConstants.WATCHDOG_UPGRADE_MSG + "wdupg-1|"
                    else:
                        if os.path.isfile(AgentConstants.AGENT_UPGRADE_FLAG_FILE) : os.remove(AgentConstants.AGENT_UPGRADE_FLAG_FILE)
                        self.setIsUpgradeInProgress(False)
                        self.setIsUpgradeSuccess(False)
                        self.log("UPGRADE : failed upgrade | msg: {}".format(_msg))
                        AgentConstants.WATCHDOG_UPGRADE_MSG = AgentConstants.WATCHDOG_UPGRADE_MSG + "wdupg-0|{}|".format(_msg)
                        bool_isSuccess = False
            else:
                self.setIsUpgradeInProgress(False)
                self.setIsUpgradeSuccess(False)
                bool_isSuccess = False
        except Exception as e:
            self.log('POST UPGRADE : ********************** Exception while starting watchdog service  *************************')
            AgentConstants.WATCHDOG_UPGRADE_MSG = AgentConstants.WATCHDOG_UPGRADE_MSG + "pstup-2|"
            traceback.print_exc()
            self.setIsUpgradeInProgress(False)
            self.setIsUpgradeSuccess(False)            
            bool_isSuccess = False
        return bool_isSuccess      
                
    def upgrade(self, custom = False):
        AgentAction.ackAgentUpgradeStatus(AgentConstants.UPGRADE_ACK_MSG,"ACK_UPGRADE")
        AgentConstants.BOOL_AGENT_UPGRADE = True
        AgentConstants.WATCHDOG_UPGRADE_MSG = ""
        if self.initiateUpgrade():
            if custom == True:
                self.log('UPGRADE : Inside patch upgrade ')
                if self.preUpgrade(True):
                    if self.upgradeAction():
                        self.postUpgrade()
            else:
                self.log('UPGRADE : Inside normal upgrade ')
                if self.preUpgrade():
                    if self.upgradeAction():
                        self.postUpgrade()
        if AgentConstants.UPGRADE_USER_MESSAGE == None:
            AgentConstants.WATCHDOG_UPGRADE_MSG = "##"+str(AgentConstants.WATCHDOG_UPGRADE_MSG)
        else:
            AgentConstants.WATCHDOG_UPGRADE_MSG = AgentConstants.UPGRADE_USER_MESSAGE +"##"+str(AgentConstants.WATCHDOG_UPGRADE_MSG)
        AgentAction.ackAgentUpgradeStatus(AgentConstants.WATCHDOG_UPGRADE_MSG,"PRIOR_UPGRADE")
        AgentConstants.BOOL_AGENT_UPGRADE = False
