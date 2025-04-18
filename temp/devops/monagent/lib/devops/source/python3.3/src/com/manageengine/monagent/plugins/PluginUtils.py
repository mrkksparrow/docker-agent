import json
import os
import time
import traceback
import threading
import shutil
from com.manageengine.monagent import AgentConstants,module_object_holder
from com.manageengine.monagent.logger import AgentLogger
from com.manageengine.monagent.util import AgentUtil
from com.manageengine.monagent.util.AgentUtil import FileUtil
from importlib.machinery import SourceFileLoader
if not AgentConstants.IS_VENV_ACTIVATED:
    from func_timeout import func_timeout, FunctionTimedOut
import com

thread_Lock=threading.Lock()
update_File_Lock=threading.Lock()
PLUGIN_CONF_DICT={}

def getPluginsConfFileObj(): 
    fileObj = AgentUtil.FileObject()
    fileObj.set_filePath(AgentConstants.AGENT_PLUGINS_CONF_FILE)
    fileObj.set_dataType('json')
    fileObj.set_mode('rb')
    fileObj.set_dataEncoding('UTF-8')
    fileObj.set_loggerName(AgentLogger.PLUGINS)
    fileObj.set_logging(False)
    return fileObj

def getPluginsIdFileObj():
    fileObj = AgentUtil.FileObject()
    fileObj.set_filePath(AgentConstants.AGENT_PLUGINS_SITE24X7ID)
    fileObj.set_dataType('json')
    fileObj.set_mode('rb')
    fileObj.set_dataEncoding('UTF-8')
    fileObj.set_loggerName(AgentLogger.PLUGINS)
    fileObj.set_logging(False)
    return fileObj

def getPluginsListFileObj(): 
    fileObj = AgentUtil.FileObject()
    fileObj.set_filePath(AgentConstants.AGENT_PLUGINS_LISTS_FILE)
    fileObj.set_dataType('json')
    fileObj.set_mode('rb')
    fileObj.set_dataEncoding('UTF-8')
    fileObj.set_loggerName(AgentLogger.PLUGINS)
    fileObj.set_logging(False)
    return fileObj

def updatePluginJson(dict_Site24X7Id):
    ''' Function will update plugin id in the pluginid file '''
    try:
        thread_Lock.acquire()
        global PLUGIN_CONF_DICT
        str_pluginName = None
        responseDict=json.loads(dict_Site24X7Id)
        AgentLogger.debug(AgentLogger.PLUGINS,' response dict -- {0}'.format(json.dumps(responseDict)))
        AgentLogger.debug(AgentLogger.PLUGINS,' conf dict -- {0}'.format(json.dumps(PLUGIN_CONF_DICT)))
        for key,value in responseDict.items():
            str_pluginName = key
            if key in PLUGIN_CONF_DICT:
                oldDict={}
                oldDict = PLUGIN_CONF_DICT.pop(key)
                oldDict.update(value)
        PLUGIN_CONF_DICT.setdefault(str_pluginName,{})
        PLUGIN_CONF_DICT[str_pluginName]=oldDict
        if not os.path.exists(AgentConstants.AGENT_PLUGINS_SITE24X7ID):
            AgentUtil.FileUtil.createFile(AgentConstants.AGENT_PLUGINS_SITE24X7ID,AgentLogger.PLUGINS)
        bool_FileLoaded, tempDict = AgentUtil.loadDataFromFile(AgentConstants.AGENT_PLUGINS_SITE24X7ID)
        if tempDict==None:
            tempDict={}
        if tempDict and str_pluginName in tempDict:
            existingDict={}
            existingDict = tempDict.pop(key)
            existingDict.update(value)
            tempDict.setdefault(str_pluginName,{})
            if 'error_msg' in existingDict and 'status' in existingDict and existingDict['status']==0:
                existingDict.pop('error_msg')
            tempDict[str_pluginName]=existingDict
        else:
            tempDict.setdefault(str_pluginName,{})
            tempDict[str_pluginName]=oldDict
        bool_FileSaved = AgentUtil.writeDataToFile(AgentConstants.AGENT_PLUGINS_SITE24X7ID, tempDict)
        if(not bool_FileSaved):
            AgentLogger.log(AgentLogger.PLUGINS, "PLUGINS ID" + "Unable to update id file")
    except Exception as e:
        traceback.print_exc()
    finally:
        thread_Lock.release()

def updateDictToFile(d1):
    update_File_Lock.acquire()
    try:
        bool_FileLoaded, tempDict = AgentUtil.loadDataFromFile(AgentConstants.AGENT_PLUGINS_SITE24X7ID)
        for key,value in d1.items():
            tempDict.pop(key)
        d1.update(tempDict)
        bool_FileSaved = AgentUtil.writeDataToFile(AgentConstants.AGENT_PLUGINS_SITE24X7ID, d1)
        if(not bool_FileSaved):
            AgentLogger.log(AgentLogger.PLUGINS, "PLUGINS ID" + "Unable to update id file")
    except Exception as e:
        traceback.print_exc()
    finally:
        update_File_Lock.release()
    
def updatePluginConfigDict():
    try:
        if os.path.exists(AgentConstants.AGENT_PLUGINS_SITE24X7ID):
            fileObj = AgentUtil.FileObject()
            fileObj.set_filePath(AgentConstants.AGENT_PLUGINS_SITE24X7ID)
            fileObj.set_dataType('json')
            fileObj.set_mode('rb')
            fileObj.set_dataEncoding('UTF-8')
            fileObj.set_loggerName(AgentLogger.PLUGINS)
            fileObj.set_logging(False)
            global PLUGIN_CONF_DICT
            bool_FileLoaded, PLUGIN_CONF_DICT = FileUtil.readData(fileObj)
            if not bool_FileLoaded:
                PLUGIN_CONF_DICT = {}
            AgentLogger.log(AgentLogger.PLUGINS, "Plugin Configuration Data -- {0} -- {1}".format(bool_FileLoaded,json.dumps(PLUGIN_CONF_DICT)))
    except Exception as e:
        AgentLogger.log(AgentLogger.PLUGINS, "Exception Occured while updating plugin conf dictionary")
        AgentLogger.log(AgentLogger.PLUGINS, "UPDATED PLUGIN_CONF_DICT ===> {0}".format(PLUGIN_CONF_DICT))

def getPluginConfDict():
    global PLUGIN_CONF_DICT
    return PLUGIN_CONF_DICT

def exec_plugin_util(file_name,commd,params,temp):
    try:
        script_path = commd.split(" ")[0]
        script_name = file_name.split(".")[0]
        AgentLogger.log(AgentLogger.PLUGINS,' Plugin module load parameter --- {} :: {} :: {} '.format(script_name,script_path,params))
        custom_parser = SourceFileLoader(script_name, script_path).load_module()
        dict_val = custom_parser.run(params)
        AgentLogger.log(AgentLogger.PLUGINS,' Plugin load module execution succesfull -- {}'.format(dict_val))
        return dict_val
    except Exception as e:
        AgentLogger.log(AgentLogger.PLUGINS, str(traceback.print_exc()))

def exec_plugin_function_timeout(file_name,commd,timeout,params):
    dict_to_return={}
    dict_to_return['result'] = True
    try:
        return_value_from_exec = func_timeout(timeout, exec_plugin_util, args=(file_name,commd,params,1))
        dict_to_return['output'] = return_value_from_exec
        AgentLogger.debug(AgentLogger.PLUGINS,' return value -- {}'.format(dict_to_return))
    except FunctionTimedOut:
        dict_to_return['timedout']=True
        AgentLogger.log(AgentLogger.PLUGINS,' timeout occurred ')
    except Exception as e:
        AgentLogger.log(AgentLogger.PLUGINS,' exception occurred ')
        dict_to_return['result'] = False
        traceback.print_exc()
    return dict_to_return,dict_to_return['result']

def re_register_plugins(dict_task = {}):
    if 'PLUGIN_NAME' in dict_task:
        rediscoverDeletedPlugins(dict_task)
    else:
        FileUtil.deleteFile(AgentConstants.AGENT_PLUGINS_SITE24X7ID,AgentLogger.PLUGINS)
        global PLUGIN_CONF_DICT
        PLUGIN_CONF_DICT = {}
        AgentConstants.FORCE_LOAD_PLUGINS = True
    module_object_holder.plugins_obj.refresh_ignored_plugins_list(dict_task)

def rediscoverDeletedPlugins(dict_task):
    try:
        AgentLogger.log(AgentLogger.PLUGINS, "removing plugin delete entry")
        fileObj = getPluginsIdFileObj()
        bool_toReturn, dict_monitorsInfo = FileUtil.readData(fileObj)
        pname = dict_task['PLUGIN_NAME'] if 'PLUGIN_NAME' in dict_task else None
        if not pname==None:
            if pname in dict_monitorsInfo:
                if dict_monitorsInfo[pname]['status'] in [3,2]:
                    dict_monitorsInfo.pop(pname)
            else:
                AgentLogger.log(AgentLogger.PLUGINS, "plugin not present in delete list")
        AgentUtil.writeDataToFile(AgentConstants.AGENT_PLUGINS_SITE24X7ID,dict_monitorsInfo)
        updatePluginConfigDict()
    except Exception as e:
        AgentLogger.log(AgentLogger.PLUGINS, "-- Unable to re discover deleted plugins --")
        traceback.print_exc()

def updatePluginStatus(str_plugName,status):
    bool_FileSaved = False
    bool_FileLoaded, tempDict = AgentUtil.loadDataFromFile(AgentConstants.AGENT_PLUGINS_SITE24X7ID)
    if bool_FileLoaded:
        if tempDict and str_plugName in tempDict:
            tempDict[str_plugName]['status']=status
            bool_FileSaved = AgentUtil.writeDataToFile(AgentConstants.AGENT_PLUGINS_SITE24X7ID, tempDict)
        else:
            AgentLogger.log(AgentLogger.PLUGINS, "Plugin configuration is not available ")
    else:
        AgentLogger.log(AgentLogger.PLUGINS,'pl_id mapper file not found')
    return bool_FileSaved

def getNagiosPluginName(pluginCommand):
    pluginName = pluginCommand.split(" ")
    name = pluginName[0]
    return name.split("/")[-1]

def getDefaultPluginName(pluginCommand):
    return pluginCommand.split("/")[-1]

def fetchPluginName(pluginCommand,pluginType):
    if pluginType=='nagios':
        return getNagiosPluginName(pluginCommand)
    else:
        return getDefaultPluginName(pluginCommand)
    
def fetchExecutablePlugins():
    pluginFiles=[]
    SUCCESS_LIST=[]
    inv_dict={}
    for item in os.listdir(AgentConstants.AGENT_PLUGINS_DIR):
        if os.path.isfile(os.path.join(AgentConstants.AGENT_PLUGINS_DIR, item)) and os.path.splitext(item)[1] in ['.py','.sh']:
            inv_dict[item]={}
            inv_dict[item]['error_msg']='plugin file is not in a separate folder'
            inv_dict[item]['status'] = 2

        elif os.path.isdir(os.path.join(AgentConstants.AGENT_PLUGINS_DIR, item)):
            if len(os.listdir(os.path.join(AgentConstants.AGENT_PLUGINS_DIR, item))) == 0:
                dir_name = item.lower()
                inv_dict[dir_name]={}
                inv_dict[dir_name]['error_msg']='no plugin found in the directory'
                inv_dict[dir_name]['status'] = 2
            for files in os.listdir(os.path.join(AgentConstants.AGENT_PLUGINS_DIR, item)):
                if os.path.isfile(os.path.join(AgentConstants.AGENT_PLUGINS_DIR+"/"+item, files)) and item.lower() == os.path.splitext(files)[0].lower():
                    if not files.startswith('.') and not files == AgentConstants.AGENT_PLUGINS_NAGIOS_FILE and not files.endswith('~') and not files.endswith('.swp') and not files.endswith('.swo') and not files.endswith('.cfg') and not files.endswith('.zip'):
                        pluginFiles.append(os.path.join(AgentConstants.AGENT_PLUGINS_DIR+"/"+item, files))
                        SUCCESS_LIST.append(os.path.splitext(files)[0].lower())
                    try:
                        fileName=os.path.join(AgentConstants.AGENT_PLUGINS_DIR+"/"+item, files)
                        os.chmod(fileName,0o700)
                    except Exception as e:
                        AgentLogger.log(AgentLogger.PLUGINS, "Exception while changing file permission ====> "+repr(fileName))
                elif os.path.isdir(os.path.join(AgentConstants.AGENT_PLUGINS_DIR+"/"+item, files)):
                    if os.path.basename(os.path.join(AgentConstants.AGENT_PLUGINS_DIR+"/"+item, files)) == '__pycache__':
                        AgentLogger.debug(AgentLogger.PLUGINS, "__pycache__ folder found in plugin ====> "+item)
                    else :
                        AgentLogger.log(AgentLogger.PLUGINS, "another directory found inside plugin ====> "+item)
                    continue
                elif item.lower() != os.path.splitext(files)[0].lower() and os.path.splitext(os.path.basename(os.path.join(AgentConstants.AGENT_PLUGINS_DIR+"/"+item, files)))[1] in ['.py','.sh']:
                    dir_name = item.lower()
                    inv_dict[dir_name]={}
                    inv_dict[dir_name]['error_msg']="plugin file name is not matched with directory name"
                    inv_dict[dir_name]['status'] = 2
    DELETE_LIST=[]
    for key in inv_dict.keys():
        if key in SUCCESS_LIST:
            DELETE_LIST.append(key)
    for each in DELETE_LIST:
        inv_dict.pop(each)
    AgentConstants.PLUGIN_FOLDER_DICT=inv_dict
    module_object_holder.plugins_obj.updateInventoryToServer()
    AgentLogger.log(AgentLogger.PLUGINS,'Executable Plugins List -- {0}'.format(pluginFiles))
    return pluginFiles

def reloadPlugins():
    module_object_holder.plugins_obj.loadPlugins()
    module_object_holder.plugins_obj.doPluginDC()
    
def removePluginConfig(pluginName):
    global PLUGIN_CONF_DICT
    AgentLogger.log(AgentLogger.PLUGINS,'==== Removing Plugin Config ===='+repr(pluginName))
    if pluginName in PLUGIN_CONF_DICT:
        PLUGIN_CONF_DICT.pop(pluginName)
    AgentLogger.log(AgentLogger.PLUGINS,'==== Plugin Config after removal ===='+repr(PLUGIN_CONF_DICT))
        
def processSAM(dict_task):
    str_requestType = 5
    str_mtype = dict_task['mtype']
    if str_mtype == 'PLUGIN':
        bool_updateStatus = updatePluginStatus(dict_task['configuration']['plugin_name'],str_requestType)
        if bool_updateStatus:
            updatePluginConfigDict()
            AgentConstants.UPDATE_PLUGIN_INVENTORY=True
    elif str_mtype =='DOCKER':
        com.manageengine.monagent.docker_old.DockerAgent.suspendMonitoring()
    else:
        AgentLogger.log(AgentLogger.PLUGINS,' monitor type not supported for this action ---> '+repr(dict_task))
    

def processAAM(dict_task):
    str_requestType = 0
    str_mtype = dict_task['mtype']
    if str_mtype == 'PLUGIN':
        bool_updateStatus = updatePluginStatus(dict_task['configuration']['plugin_name'],str_requestType)
        if bool_updateStatus:
            updatePluginConfigDict()
            AgentConstants.UPDATE_PLUGIN_INVENTORY=True 
    elif str_mtype =='DOCKER':
        com.manageengine.monagent.docker_old.DockerAgent.activateDocker()
    else:
        AgentLogger.log(AgentLogger.PLUGINS,' monitor type not supported for this action ---> '+repr(dict_task))

    
def processDAM(dict_task):
    str_requestType = 3
    str_mtype = dict_task['mtype']
    if str_mtype == 'PLUGIN':
        bool_updateStatus = updatePluginStatus(dict_task['configuration']['plugin_name'],str_requestType)
        if bool_updateStatus:
            updatePluginConfigDict()
            AgentConstants.UPDATE_PLUGIN_INVENTORY=True
    elif str_mtype =='DOCKER':
        com.manageengine.monagent.docker_old.DockerAgent.deleteMonitoring()
    else:
        AgentLogger.log(AgentLogger.PLUGINS,' monitor type not supported for this action ---> '+repr(dict_task))
       
def deployPlugin(dict_task):
    """This method is to place a plugin under plugins directory from temp directory."""
    AgentLogger.log(AgentLogger.PLUGINS,' Deploying Plugin ---> '+repr(dict_task))
    str_pluginName = dict_task['name']
    str_pluginName=str_pluginName.lower()
    try:
        if str_pluginName not in PLUGIN_CONF_DICT:
            from_dir = AgentConstants.AGENT_PLUGINS_TMP_DIR+str_pluginName
            to_dir = AgentConstants.AGENT_PLUGINS_DIR+str_pluginName
            shutil.copytree(from_dir,to_dir)
        else:
            AgentLogger.log(AgentLogger.PLUGINS, "-- Plugin already deployed -- {0}".format(PLUGIN_CONF_DICT[str_pluginName]))
    except Exception as e:
        AgentLogger.log(AgentLogger.PLUGINS, "-- Unable to deploy plugin --")
        traceback.print_exc()    

def disablePlugins(dict_task):
    """ This method is to disable plugins """
    AgentLogger.log(AgentLogger.PLUGINS,' Disabling Plugins ---> '+repr(dict_task))
    str_section=AgentConstants.PLUGINS_SECTION
    str_option=AgentConstants.PLUGINS_ENABLED_KEY
    try:
        if AgentUtil.AGENT_CONFIG.has_section(str_section) and AgentUtil.AGENT_CONFIG.has_option(str_section,str_option):
            if AgentUtil.AGENT_CONFIG.get(str_section, str_option)=='1':
                AgentUtil.AGENT_CONFIG.set(str_section, str_option,'0')
                AgentUtil.persistAgentInfo()
            else:
                AgentLogger.log(AgentLogger.PLUGINS,' Plugins Already Disabled ---> {0}'.format(AgentUtil.AGENT_CONFIG.get(str_section, str_option)))
        else:
            AgentUtil.AGENT_CONFIG.add_section(str_section)
            AgentUtil.AGENT_CONFIG.set(str_section,str_option,'0')
            AgentUtil.persistAgentInfo()
    except Exception as e:
        AgentLogger.log(AgentLogger.PLUGINS, "-- Exception while disabling plugin --")
        traceback.print_exc()
        
def enablePlugins(dict_task):
    """ This method is to enable plugins """
    AgentLogger.log(AgentLogger.PLUGINS,' Enabling Plugins ---> '+repr(dict_task))
    str_section=AgentConstants.PLUGINS_SECTION
    str_option=AgentConstants.PLUGINS_ENABLED_KEY
    try:
        if AgentUtil.AGENT_CONFIG.has_section(str_section) and AgentUtil.AGENT_CONFIG.has_option(str_section,str_option):
            AgentUtil.AGENT_CONFIG.remove_section(AgentConstants.PLUGINS_SECTION)
            AgentUtil.persistAgentInfo()
        else:
            AgentLogger.log(AgentLogger.PLUGINS,' Plugins Already Enabled ---> {0}'.format(AgentUtil.AGENT_CONFIG.get(str_section, str_option)))
    except Exception as e:
        AgentLogger.log(AgentLogger.PLUGINS, "-- Exception while enabling plugin --")
        traceback.print_exc()

def configurePluginCount(dict_task):
    """ This method is to configure plugin count """
    AgentLogger.log(AgentLogger.PLUGINS,' Plugin Count Configuration ---> '+repr(dict_task))
    try:
        if dict_task['count'] and dict_task['count'].isdigit():
            AgentUtil.AGENT_CONFIG.set('AGENT_INFO','count',dict_task['count'])
            AgentUtil.persistAgentInfo()
            AgentConstants.FORCE_LOAD_PLUGINS = True
        else:
            AgentLogger.log(AgentLogger.PLUGINS,' Plugin Configuration Not Updated ---> ')
            AgentLogger.log(AgentLogger.PLUGINS,' Count Value Not a Number ---> '+repr(dict_task))
    except Exception as e:
        AgentLogger.log(AgentLogger.PLUGINS, "-- Exception while modifying plugin count --")
        traceback.print_exc()
    
def CleanPluginFolder(dict_task):
    bool_CleanUp=False
    folderToDelete=None
    import shutil
    try:
        pluginName = dict_task['PLUGIN_NAME']
        folderToDelete,fileExt = os.path.splitext(pluginName)
        toCleanUp = AgentConstants.AGENT_PLUGINS_DIR+folderToDelete
        if '.' not in toCleanUp:
            if os.path.exists(toCleanUp):
               shutil.rmtree(AgentConstants.AGENT_PLUGINS_DIR+folderToDelete)
            rediscoverDeletedPlugins(dict_task)
            bool_CleanUp=True
        else:
            AgentLogger.log(AgentLogger.PLUGINS, "Clean up failed due to illegal plugin file name")
    except Exception as e:
        AgentLogger.log(AgentLogger.PLUGINS, "-- Exception while deleting plugin folder --")
        traceback.print_exc()
    finally:
        if bool_CleanUp:
            AgentLogger.log(AgentLogger.PLUGINS, "Plugin Cleaned Up Successfully {0}".format(folderToDelete))
