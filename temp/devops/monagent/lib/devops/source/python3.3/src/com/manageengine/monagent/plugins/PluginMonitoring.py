import json
import os
import re
import time
import traceback
import threading
import shutil
import platform
import math 
try:
    import configparser
except Exception as e:
    import ConfigParser as configparser
from six.moves.urllib.parse import urlencode
from com.manageengine.monagent import AgentConstants,module_object_holder
from com.manageengine.monagent.logger import AgentLogger
from com.manageengine.monagent.util import AgentUtil
from com.manageengine.monagent.util import DesignUtils
from com.manageengine.monagent.util import AgentBuffer
from com.manageengine.monagent.util import MetricsUtil
from com.manageengine.monagent.util.AgentUtil import FileUtil, FileZipAndUploadInfo,ZipUtil,AGENT_CONFIG
from com.manageengine.monagent.plugins import PluginUtils
from com.manageengine.monagent.scheduler import AgentScheduler
from com.manageengine.monagent.security import AgentCrypt
import com

pluginUtil = None
customFileLock = threading.Lock()

previousLastModifiedTime=0
IGNORED_PLUGINS = {}
collection_Time=0
DONT_VALIDATE=['plugin_version','output','heartbeat_required']
NOT_FOR_ENCRYPTION=['poll_interval','timeout']

registration_lock = threading.Lock()

class Plugins():
    def __init__(self):
        self.id = None
        self.name = None
        self.timeout = AgentConstants.DEFAULT_SCRIPT_TIMEOUT
        self.fileType = None
        self.command = None
        self.pluginType=None
        self.ispluginRegistered=None
        self.pluginStatus=None
        self.isPluginSupported=None
        self.nagiosVersion=None
        self.folderName = None
        self.plugin_ignore_filepath = None
        self.plugin_directory = None
        self.plugin_cfg = None
        self.decrypted_value = None
        self.plugin_cfg_file = None
        self.poll_interval = AgentConstants.PLUGINS_DC_INTERVAL
        self.time_out= int(AgentConstants.PLUGIN_DEFAULT_TIME_OUT)
        self.instance_name = None
        self.use_agent_python = False
        self.absolute_file_name = None
        self.params_dict = {}
        self.global_config_dict = {}
        self.config_to_encrypt = ['password']
        self.send_to_statsd = False
        
    def setPluginDetails(self,plugCmd,pluginType,instance=None,config_file_obj=None):
        try:
            self.name = module_object_holder.plugins_util.fetchPluginName(plugCmd,pluginType)
            self.command = getCmdForExecution(self.fileType,plugCmd)
            self.pluginType=pluginType
            self.folderName,self.fileType = fetchFileType(self.name)
            self.plugin_directory = os.path.dirname(self.command) 
            self.nagiosVersion = getNagiosVersion(pluginType,plugCmd)
            self.isPluginSupported=checkForPluginSupport(self.fileType,self.pluginType)
            self.plugin_cfg_file = self.plugin_directory+'/'+self.folderName+'.cfg'
            list_of_config_to_encrypt=self.config_to_encrypt
            plugin_name = self.name
            if instance and config_file_obj:
                plugin_name = self.name+"-"+str(instance)
                temp_list = []
                if config_file_obj.has_section('global_configurations'):
                    self.global_config_dict = dict(config_file_obj.items('global_configurations'))
                    if 'use_agent_python' in self.global_config_dict and (self.global_config_dict['use_agent_python']=="1" or self.global_config_dict['use_agent_python']=="true"):
                        self.use_agent_python = True
                        self.global_config_dict.pop('use_agent_python')
                        AgentLogger.log(AgentLogger.PLUGINS, '{0} -> plugin configured to use agent python for execution'.format(self.name))
                    if 'keys_to_encrypt' in self.global_config_dict:
                        keys_to_encrypt = self.global_config_dict.get('keys_to_encrypt')
                        if keys_to_encrypt:
                            list_of_config_to_encrypt = keys_to_encrypt.split(',')
                    for k , v in self.global_config_dict.items():
                        if k != 'keys_to_encrypt' and k != 'use_agent_python':
                            if self.fileType == '.sh':
                                temp_list.append(str(self.global_config_dict[k]))
                            else:
                                temp_list.append('--'+k+'='+str(self.global_config_dict[k]))
                self.instance_name = instance
                for config_name , config_value in config_file_obj.items(instance):
                    if config_value=='None':
                        config_value=''
                    if config_name=='use_agent_python' and config_value=="1":
                        self.use_agent_python = True
                        AgentLogger.log(AgentLogger.PLUGINS, '{} -> plugin configured to use agent python for execution'.format(self.name))
                        continue
                    if config_name == 'send_to_statsd':
                        self.send_to_statsd = True
                        AgentLogger.log(AgentLogger.PLUGINS,'{0} -> plugin configured to push metrics to statsd '.format(self.name))
                        continue
                    if config_name.startswith('encrypted.'):
                        if self.fileType == '.sh':
                            temp_list.append(str(AgentCrypt.decrypt_with_ss_key(config_value)))
                        else:
                            temp_list.append('--'+config_name.rpartition('encrypted.')[-1]+"="+str(AgentCrypt.decrypt_with_ss_key(config_value)))
                        self.params_dict[config_name.rpartition('encrypted.')[-1]]=AgentCrypt.decrypt_with_ss_key(config_value)
                    else:
                        self.params_dict[config_name]=str(config_value)
                        if self.fileType == '.sh':
                            temp_list.append(str(config_value))
                        else:
                            temp_list.append('--'+config_name+"="+str(config_value))
                        if config_name in list_of_config_to_encrypt:
                            value = AgentCrypt.encrypt_with_ss_key(config_value)
                            config_file_obj.set(instance,'encrypted.'+config_name, value)
                            config_file_obj.remove_option(instance, config_name)
                confFile = open(self.plugin_cfg_file,"w") 
                config_file_obj.write(confFile)
                self.decrypted_value = ' '.join(temp_list)
                self.command =  self.command+" "+self.decrypted_value
                self.params_dict.update(self.global_config_dict)
            if com.manageengine.monagent.collector.DataConsolidator.CONFIG_OBJECTS and 'plugins' in com.manageengine.monagent.collector.DataConsolidator.CONFIG_OBJECTS and plugin_name in com.manageengine.monagent.collector.DataConsolidator.CONFIG_OBJECTS['plugins']:
                self.time_out = com.manageengine.monagent.collector.DataConsolidator.CONFIG_OBJECTS['plugins'][plugin_name]['timeout']
                self.poll_interval = com.manageengine.monagent.collector.DataConsolidator.CONFIG_OBJECTS['plugins'][plugin_name]['poll_interval']
            self.absolute_file_name = os.path.join(self.plugin_directory,self.name)
            #self.use_agent_python = self.check_for_agent_python(self.absolute_file_name,self.name)
            AgentLogger.debug(AgentLogger.PLUGINS,'final command -- {0}'.format(self.command))
        except Exception as e:
            AgentLogger.log([AgentLogger.PLUGINS, AgentLogger.STDERR], ' *************************** Exception while setting Plugin monitor details *************************** ' + str(self.name) + " ==> " + repr(e))
            traceback.print_exc()

    def check_for_agent_python(self, absolute_file_name,file_name):
        use_agent_python = False
        try:
            if not AgentConstants.IS_VENV_ACTIVATED:
                import mmap
                with open(absolute_file_name, 'rb', 0) as file, \
                    mmap.mmap(file.fileno(), 0, access=mmap.ACCESS_READ) as s:
                    if s.find(b's247ScriptOutput') != -1:
                        use_agent_python = True
                        AgentLogger.log(AgentLogger.PLUGINS,'agent python true \n')
        except Exception as e:
            traceback.print_exc()
        return use_agent_python

    def setPluginStatus(self):
        try:
            plug_name = self.name
            if self.instance_name:
                plug_name = self.name+"-"+self.instance_name
            bool_reg,plug_status=getPluginStatus(plug_name)
            self.ispluginRegistered=bool_reg
            self.pluginStatus=plug_status
        except Exception as e:
            AgentLogger.log(AgentLogger.PLUGINS, '*********** Exception while setting plugin status ***********')
            traceback.print_exc()

    def pluginDC(self):
        global IGNORED_PLUGINS
        if self.isPluginSupported:
            if int(self.pluginStatus) in [0,2,9]:
                if self.use_agent_python:
                    if self.global_config_dict:
                        for k , v in self.global_config_dict.items():
                            if k != 'keys_to_encrypt':
                                self.params_dict[k]=v
                    outputDict,result = PluginUtils.exec_plugin_function_timeout(self.name,self.command,self.time_out,self.params_dict)
                    #AgentLogger.log(AgentLogger.PLUGINS,"agent python plugin - {0} | output - {1}".format(self.command,json.dumps(outputDict)))
                    AgentLogger.debug(AgentLogger.PLUGINS,"plugin - {0} | output - {1}".format(self.command,json.dumps(outputDict)))
                else:
                    outputDict, result = self.executeScript()
                    #AgentLogger.log(AgentLogger.PLUGINS,"system python plugin - {0} | output - {1}".format(self.command,json.dumps(outputDict)))
                    AgentLogger.debug(AgentLogger.PLUGINS,"plugin - {0} | output - {1}".format(self.command,json.dumps(outputDict)))
                AgentLogger.log(AgentLogger.PLUGINS,"Plugin - {0} | Poll Interval - {1} executed.".format(self.name, self.poll_interval))
                try:
                    if result:
                        if self.pluginType == 'nagios':
                            self.parseNagiosPlugins(outputDict)
                        else:
                            if self.fileType == '.sh':
                                self.parseShellPlugins(outputDict)
                            else:
                                self.parsePyPlugins(outputDict)
                    else:
                        AgentLogger.log(AgentLogger.PLUGINS, '======== Plugin Execution Result Not Obtained ========= {0}{1}'.format(outputDict, result))
                except Exception as e:
                    AgentLogger.log([AgentLogger.PLUGINS, AgentLogger.STDERR], ' *************************** Exception for Plugin  *************************** {0}'.format(self.name))
                    traceback.print_exc()
            else:
                AgentLogger.log(AgentLogger.PLUGINS, 'Plugin Not Executed - Plugin Not Active -  Suspended or Deleted ---> {0} '.format(self.name))
        else:
            AgentLogger.log(AgentLogger.PLUGINS, 'Plugin Not Executed - Plugin Type Not Supported ---> {0} '.format(self.name))
            error_msg='plugin file type not supported'
            module_object_holder.plugins_obj.populateIgnorePluginsList(self.name,error_msg)
            AgentConstants.UPDATE_PLUGIN_INVENTORY=True
            
            
    def executeScript(self):
        dictToReturn = {}
        result = True
        stdOutput=''
        stdErr=''
        try:
            executorObj = AgentUtil.Executor()
            executorObj.setLogger(AgentLogger.PLUGINS)
            executorObj.setTimeout(self.time_out)
            if self.command is not None:
                executorObj.setCommand(self.command)
                executorObj.executeCommand()
                dictToReturn['result'] = executorObj.isSuccess()
                retVal    = executorObj.getReturnCode()
                stdOutput = executorObj.getStdOut()
                stdErr    = executorObj.getStdErr()
                is_timed_out = executorObj.is_timed_out()
                dictToReturn['timedout'] = is_timed_out
                if retVal is not None:
                    dictToReturn['exit_code'] = retVal
                if self.fileType=='.py' and self.pluginType!='nagios':
                    if not stdOutput == None and stdOutput!='':
                        try:
                            dictToReturn['output'] = json.loads(stdOutput)
                        except Exception as e:
                            dictToReturn['error'] = AgentConstants.PLUGIN_NON_JSON_OUTPUT
                            AgentLogger.log(AgentLogger.PLUGINS, 'Plugin output not in json format ==== {0}'.format(self.name))
                else:
                    dictToReturn['output'] = stdOutput.rstrip('\n')
                if not stdErr == None and stdErr!='':
                    dictToReturn['error'] = AgentUtil.getModifiedString(stdErr,200,200)
            else:
                AgentLogger.log(AgentLogger.PLUGINS, 'Command is NULL for the Plugin ==== {0}'.format(self.name))
                result = False
        except Exception as e:
            AgentLogger.log([AgentLogger.PLUGINS, AgentLogger.STDERR], '********* Exception While Executing the Script*********' + repr(e))
            traceback.print_exc()
        finally:
            return dictToReturn, result
    
    def doPluginDataValidation(self,upload_dict,plugin_name):
        try:
            if 'data' in upload_dict and upload_dict['data']:
                data_dict = upload_dict['data']
                for key, value in data_dict.items():
                    if key not in DONT_VALIDATE:
                        float_val=isinstance(value, float)
                        int_val=isinstance(value, int)
                        if float_val:
                            final_value='{:.2f}'.format(value)
                            data_dict[key]=final_value
                        if int_val:
                            integer_value=float(value)
                            final_value='{:.2f}'.format(integer_value)
                            data_dict[key]=final_value
                upload_dict['data']=data_dict
                
                #plugin version should be a postive integer
                if '.' in str(upload_dict['data']['plugin_version']):
                    upload_dict['message'] = 'Plugin version {} is unsupported, as the version must be an integer.'.format(upload_dict['data']['plugin_version'])
                    upload_dict['availability'] = 0
            else:
                AgentLogger.log(AgentLogger.PLUGINS, 'Data Validation - There is no Data in Upload dictionary :: {} ===> '+repr(upload_dict)+' '.format(plugin_name))
        except Exception as e:
            traceback.print_exc()
        return upload_dict
        
    def send_to_statsd_listener(self,metric_dict):
        statsd_client = MetricsUtil.statsd_util_obj.get_statsd_instance()
        data = metric_dict['data']
        for each in DONT_VALIDATE:
            if each in data:
                data.pop(each)
        tags = {'plugin':self.name,'instance':self.instance_name}
        for k , v in data.items():
            try:
               statsd_client.gauge(k,float(v),tags=tags)
            except Exception as e:
                AgentLogger.log(AgentLogger.PLUGINS,'error while pushing to metrics agent :: {}'.format(e))
                traceback.print_exc()
                        
    def postPluginExecution(self,key, upload_dict):
        try:
            global IGNORED_PLUGINS
            if self.instance_name:
                key = self.name+'-'+self.instance_name
            if key in IGNORED_PLUGINS:
                if upload_dict['availability']:
                    PluginHandler.removePluginFromIgnoreList(self,key)    
                else:
                    IGNORED_PLUGINS[key]['count'] = IGNORED_PLUGINS[key]['count']+1
                    if IGNORED_PLUGINS[key]['count'] == 12:
                        AgentLogger.log(AgentLogger.PLUGINS, "Plugin "+self.name+" is in ignored state "+str(IGNORED_PLUGINS[key]))
                        return
            upload_dict=self.doPluginDataValidation(upload_dict,key)
            global PLUGIN_CONF_DICT
            PLUGIN_CONF_DICT = module_object_holder.plugins_util.getPluginConfDict()
            config_Change = False
            if self.send_to_statsd:
                self.send_to_statsd_listener(upload_dict)
                return
            if not self.ispluginRegistered:
                AgentLogger.log([AgentLogger.MAIN,AgentLogger.PLUGINS], 'Plugin Registration ===> '+repr(key)+'\n')
                if len(PLUGIN_CONF_DICT) < int(AgentUtil.AGENT_CONFIG.get('AGENT_INFO','count')):
                    upload_dict['type'] = key
                    configDict={}
                    if key not in PLUGIN_CONF_DICT:
                        PLUGIN_CONF_DICT.setdefault(key,{})
                    if 'plugin_version' not in upload_dict['data']:
                        configDict['version']="1"
                    else:
                        configDict['version']=upload_dict['data']['plugin_version']
                    if 'heartbeat_required' not in upload_dict['data']:
                        configDict['heartbeat_required']='true'
                    else:
                        configDict['heartbeat_required']=upload_dict['data']['heartbeat_required']
                    PLUGIN_CONF_DICT[key]['version']=configDict['version']
                    PLUGIN_CONF_DICT[key]['heartbeat_required']=configDict['heartbeat_required']
                    PLUGIN_CONF_DICT[key]['plugin_name']=self.name
                    if self.instance_name:
                        PLUGIN_CONF_DICT[key]['instance_name']=self.instance_name
                    else:
                        PLUGIN_CONF_DICT[key]['instance_name']=''
                    registerScript(key, upload_dict,self)
                else:
                    AgentLogger.log(AgentLogger.PLUGINS, 'Plugin Count Exceeds So moving to Ignore List ===> '+repr(key))
                    AgentLogger.log(AgentLogger.PLUGINS, 'Plugin Count ===> '+repr(len(PLUGIN_CONF_DICT)))
                    PluginHandler.populateIgnorePluginsList(key,'plugin count exceeded')
                    module_object_holder.plugins_util.removePluginConfig(key)
            else:
                #1 Version Check
                if 'plugin_version' in upload_dict['data'] and 'version' in PLUGIN_CONF_DICT[key]:
                    previous_Version = PLUGIN_CONF_DICT[key]['version']
                    current_Version = upload_dict['data']['plugin_version']
                    if int(current_Version) > int(previous_Version):
                        config_Change=True
                        PLUGIN_CONF_DICT[key]['version']=current_Version
                #2 heart beat check
                if 'heartbeat_required' in upload_dict['data'] and 'heartbeat_required' in PLUGIN_CONF_DICT[key]:
                    previous_HeartBeat = PLUGIN_CONF_DICT[key]['heartbeat_required']
                    current_HeartBeat = upload_dict['data']['heartbeat_required']
                    if str(current_HeartBeat).lower() != str(previous_HeartBeat).lower():
                        config_Change=True
                        PLUGIN_CONF_DICT[key]['heartbeat_required']=current_HeartBeat
                #3 plugin name and instance name check
                if not all(each in upload_dict['data'] for each in ['plugin_name', 'instance_name']) and not all(each in PLUGIN_CONF_DICT[key] for each in['plugin_name', 'instance_name']):
                    config_Change=True
                    PLUGIN_CONF_DICT[key]['plugin_name']=self.name
                    if self.instance_name:
                        PLUGIN_CONF_DICT[key]['instance_name']=self.instance_name
                    else:
                        PLUGIN_CONF_DICT[key]['instance_name']=''
                if config_Change:
                    temp_Dict={}
                    temp_Dict.setdefault(key,{})
                    temp_Dict[key]=PLUGIN_CONF_DICT[key]
                    module_object_holder.plugins_util.updateDictToFile(temp_Dict)
                uploadScriptResponse(key, upload_dict, PLUGIN_CONF_DICT,config_Change)
        except Exception as e:
            traceback.print_exc()
                
    
    def parseShellPlugins(self,outputDict):
        upload_dict = {}
        output_dict = {}
        file=self.name
        exit_code_check = False
        AgentLogger.debug(AgentLogger.PLUGINS,'plugin execution output - {0}'.format(outputDict))
        if 'exit_code' in outputDict and outputDict['exit_code']!=0:
            exit_code_check = True
        if 'error' in outputDict and outputDict['error']!='' and exit_code_check:
            upload_dict['availability']=0
            upload_dict['data']={}
            upload_dict['message']=outputDict['error']
            AgentLogger.log(AgentLogger.PLUGINS,' plugin out - {0} | error out - {1}'.format(outputDict,upload_dict))
        elif 'timedout' in outputDict and outputDict['timedout']==True:
            upload_dict['message']='plugin execution timed out'
            upload_dict['availability']=0
            upload_dict['data']={}
        else:
            if 'output' in outputDict:
                script_output = outputDict['output']
            if script_output.startswith('{') and script_output.endswith('}'):
                outputDict['output']=json.loads(script_output)
                self.parsePyPlugins(outputDict)
                return
            else:
                import re
                list_dict=re.split(r'\|', script_output.rstrip('\t'))
                for entry in list_dict:
                    str_entry=str(entry)
                    list_elem=str_entry.split(":")
                    output_dict[list_elem[0].strip()]=list_elem[1]
                if 'status' in output_dict and int(output_dict['status'])==0:
                    err_msg='error message not configured'
                    if 'msg' in output_dict and output_dict['msg']!='':
                        err_msg=output_dict['msg']
                    upload_dict['availability']=0
                    upload_dict['data']={}
                    upload_dict['message']=err_msg
                    if 'plugin_version' in outputDict:
                        upload_dict['plugin_version'] = outputDict['plugin_version']
                else:
                    upload_dict['availability']=1
                    upload_dict['data']=output_dict
                    if upload_dict['data'].get('units','') == '{}':
                        del upload_dict['data']['units']
                    if 'units' in upload_dict['data']:
                        units_data=upload_dict['data'].pop('units')
                        units_data=units_data[1:-1]
                        units_dict=re.split(r'\,', units_data.rstrip('\t'))
                        units_pair={}
                        for units_entry in units_dict:
                            pair=str(units_entry)
                            elem=pair.split("-")
                            units_pair[elem[0]]=elem[1]
                            upload_dict['units']=units_pair
        self.postPluginExecution(file, upload_dict)
            
    def parsePyPlugins(self,outputDict):
        global PLUGIN_CONF_DICT
        PLUGIN_CONF_DICT = module_object_holder.plugins_util.getPluginConfDict()
        upload_dict = {}
        error_Dict={}
        script_output = {}
        exit_code_check = False
        AgentLogger.debug(AgentLogger.PLUGINS,'plugin output - {0}'.format(outputDict))
        if 'exit_code' in outputDict and outputDict['exit_code']!=0:
            exit_code_check = True
        if 'output' in outputDict:
            script_output = outputDict['output']
        if 'error' in outputDict and exit_code_check:
            error_Dict['status']=0
            error_Dict['msg']=outputDict['error']
            AgentLogger.log(AgentLogger.PLUGINS,' plugin out - {0} | error out - {1}'.format(outputDict,error_Dict))
        if 'error' in outputDict and outputDict['error']==AgentConstants.PLUGIN_NON_JSON_OUTPUT:
            upload_dict['availability']=0
            upload_dict['message']=outputDict['error']
        if 'status' in error_Dict and int(error_Dict['status'])==0:
            upload_dict['message']=error_Dict['msg']
            upload_dict['availability']=0
            upload_dict['data']={}
        elif 'status' in script_output and int(script_output['status'])==0:
            err_msg='error message not configured'
            if 'msg' in script_output and script_output['msg']!='':
                err_msg=script_output['msg']
            upload_dict['message']=err_msg
            upload_dict['availability']=0
            upload_dict['data']={}
        else:
            if 'timedout' in outputDict and outputDict['timedout']==True:
                upload_dict['message']='plugin execution timed out'
                upload_dict['availability']=0
                upload_dict['data']={}
            else:
                upload_dict['availability']=1
                upload_dict['data']=script_output
                if 'units' in upload_dict['data']:
                    upload_dict['units']=upload_dict['data'].pop('units')
                if 'validation output' in upload_dict['data']:
                    upload_dict['data'].pop('validation output')
        if 'plugin_version' in script_output:
            upload_dict['plugin_version']=script_output['plugin_version']
        else:
            if self.name in PLUGIN_CONF_DICT:
                upload_dict['plugin_version']=PLUGIN_CONF_DICT[self.name]['version']
        self.postPluginExecution(self.name, upload_dict)
    
    def parseNagiosPlugins(self,outputDict):
        key = self.name
        upload_dict={}
        upload_dict['data'] = {}
        script_output = ""
        if 'output' in outputDict:
            script_output = outputDict['output']
        if 'error' in outputDict and outputDict['error']==AgentConstants.PLUGIN_NON_JSON_OUTPUT:
            upload_dict['availability']=0
            upload_dict['message']=outputDict['error']
        if 'error' in outputDict:
            upload_dict['availability'] = 0
            upload_dict['msg'] = outputDict['error']
        elif 'exit_code' in outputDict and outputDict['exit_code'] >= 2:
            upload_dict['availability']=0
            if '|' in script_output:
                self.getPerfData(upload_dict, script_output)    
                upload_dict['msg'] = script_output.split('|')[0]
            else:
                upload_dict['msg'] = script_output if not script_output.strip() == "" else "error occurred during plugin execution"
        else:
            upload_dict['availability']=1
            upload_dict=self.getPerfData(upload_dict,script_output)
            if 'exit_code' in outputDict:
                upload_dict['data'][self.name+'_status']=outputDict['exit_code']

        upload_dict['data']['plugin_version'] = self.nagiosVersion
        self.postPluginExecution(key, upload_dict)
        
    def getPerfData(self,upload_dict,parsable_Out):
        if "|" in parsable_Out:
                perfData = parsable_Out.split("|")
                if len(perfData) > 1:
                    list_perf = perfData[1].strip().split(" ")
                    for each in list_perf:
                        list_elem = each.split(";")[0].split("=")
                        match = re.match('(?P<number>[\d]+[.]?\d*)(?P<units>.*)', list_elem[1].strip())
                        if match and 'number' in match.groupdict():
                            upload_dict['data'][list_elem[0]] = match.groupdict()['number']
                            if 'units' in match.groupdict():
                                if 'units' not in upload_dict:
                                    upload_dict['units']={}
                                upload_dict['units'][list_elem[0]] = match.groupdict()['units']
                        else:
                            upload_dict['data'][list_elem[0]] = list_elem[1].strip()
        else:
            upload_dict['data']['output']=parsable_Out
        return upload_dict
    
class PluginHandler(DesignUtils.Singleton):
    _plugins_Dict = {}
    _plugins_List = []
    _lock = threading.Lock()
    
    def __init__(self):
        self._createNagiosFile()
        module_object_holder.plugins_util.updatePluginConfigDict()
    
    def getPluginList(self):
        return self._plugins_List
    
    def _createNagiosFile(self):
        try:
            if not os.path.exists(AgentConstants.AGENT_PLUGINS_DIR):
               AgentLogger.log(AgentLogger.PLUGINS,'creating plugins directory')
               os.mkdir(AgentConstants.AGENT_PLUGINS_DIR)
               src = AgentConstants.AGENT_PLUGINS_TMP_DIR+AgentConstants.AGENT_PLUGINS_NAGIOS_FILE
               dst = AgentConstants.AGENT_PLUGINS_DIR+AgentConstants.AGENT_PLUGINS_NAGIOS_FILE
               from shutil import copyfile
               copyfile(src, dst)
        except Exception as e:
            traceback.print_exc() 
    
    def _loadPluginsList(self):
        dict_monitorsInfo={}
        try:
            fileObj = module_object_holder.plugins_util.getPluginsListFileObj()
            bool_toReturn, dict_monitorsInfo = FileUtil.readData(fileObj)
            if os.path.exists(AgentConstants.AGENT_PLUGINS_CONF_FILE):
                try:
                    fileObj = module_object_holder.plugins_util.getPluginsConfFileObj()# -- for nagios
                    bool_toReturn, dict_nagiosMonitorsInfo = FileUtil.readData(fileObj)
                    dict_monitorsInfo.update(dict_nagiosMonitorsInfo)
                except Exception as e:
                    AgentLogger.log([AgentLogger.PLUGINS, AgentLogger.STDERR], ' *************************** Exception while loading Nagios Plugins List  *************************** ' + repr(e))
                    traceback.print_exc()
            for plugin_type in dict_monitorsInfo:
                for each_item in dict_monitorsInfo[plugin_type]:
                    self.__class__._plugins_List.append(each_item)
                    self.create_plugin_objects(each_item,plugin_type)
            AgentLogger.log(AgentLogger.PLUGINS, '------------------------------------------------------------------------------------------------------')
        except Exception as e:
            AgentLogger.log([AgentLogger.PLUGINS, AgentLogger.STDERR], ' *************************** Exception while loading Plugins List  *************************** ' + repr(e))
            traceback.print_exc()
    
    
    def create_plugin_objects(self,each_item,plugin_type):
        plugin = None
        config_file_present = False
        config_file_obj = None
        plugin_directory = os.path.dirname(each_item)
        plugin_folder,plugin_file_type = fetchFileType(each_item)
        plugin_config_file = plugin_folder+'.cfg'
        if os.path.exists(plugin_config_file):
            config_file_present=True
            config_file_obj = configparser.RawConfigParser()
            config_file_obj.read(plugin_config_file)
        if AgentConstants.CRYPTO_MODULE == None:
           config_file_present = False 
        if  plugin_type == AgentConstants.NAGIOS_PLUGIN_TYPE or not config_file_present:
            plugin = Plugins()
            plugin.setPluginDetails(each_item,plugin_type)
            name_check = module_object_holder.plugins_util.getNagiosPluginName(each_item)
            self.__class__._plugins_Dict[name_check] = plugin
        else:
            instance_list = config_file_obj.sections()
            for each_instance in instance_list:
                if each_instance!='global_configurations':
                    plugin = Plugins()
                    plugin.setPluginDetails(each_item,plugin_type,each_instance,config_file_obj)
                    self.__class__._plugins_Dict[plugin.name +"-"+ each_instance] = plugin
        AgentLogger.debug(AgentLogger.PLUGINS,' plugin object -- {0}'.format(self.__class__._plugins_Dict))
    
    def update_plugin_config(self,plugin_dict):
        try:
            if 'plugin_name' in plugin_dict:
                plugin_name = plugin_dict['plugin_name']
                poll_interval = int(plugin_dict['poll_interval'])
                if plugin_name in self.__class__._plugins_Dict:
                    plugin = self.__class__._plugins_Dict.pop(plugin_name)
                    plugin.poll_interval = poll_interval
                    if 'timeout' in plugin_dict:
                        plugin.time_out = int(plugin_dict['timeout'])
                    scheduleInfo = AgentScheduler.ScheduleInfo()
                    scheduleInfo.setSchedulerName('PluginScheduler')
                    scheduleInfo.setTaskName(plugin_name)
                    AgentScheduler.deleteSchedule(scheduleInfo)
                    self.__class__._plugins_Dict[plugin_name] = plugin
                self.change_plugin_schedule(plugin_name)
        except Exception as e:
            traceback.print_exc()
    
    def change_plugin_schedule(self,plugin_name):
        try:
            plugin_obj = self.__class__._plugins_Dict[plugin_name]
            task = self.pluginExecutor
            taskArgs = plugin_obj
            scheduleInfo = AgentScheduler.ScheduleInfo()
            scheduleInfo.setSchedulerName('PluginScheduler')
            scheduleInfo.setTaskName(plugin_name)
            scheduleInfo.setTime(time.time())
            scheduleInfo.setTask(task)
            scheduleInfo.setTaskName(plugin_name)
            scheduleInfo.setTaskArgs(taskArgs)
            scheduleInfo.setIsPeriodic(True)
            scheduleInfo.setInterval(plugin_obj.poll_interval)
            scheduleInfo.setLogger(AgentLogger.PLUGINS)
            AgentScheduler.schedule(scheduleInfo)
        except Exception as e:
            traceback.print_exc()
    
    def _loadDefaultPlugins(self):
        default_Plugins=[]
        try:
            if not os.path.exists(AgentConstants.AGENT_PLUGINS_LISTS_FILE):
                AgentUtil.FileUtil.createFile(AgentConstants.AGENT_PLUGINS_LISTS_FILE,AgentLogger.PLUGINS)
            default_Plugins = module_object_holder.plugins_util.fetchExecutablePlugins()
            AgentLogger.debug(AgentLogger.PLUGINS,'Executable Plugins =====> {}'.format(json.dumps(default_Plugins)))
            dict_monitorsInfo={}
            dict_monitorsInfo['plugins']=default_Plugins
            fileObj = module_object_holder.plugins_util.getPluginsListFileObj()
            fileObj.set_data(dict_monitorsInfo)
            fileObj.set_mode('wb')
            with customFileLock:
                bool_toReturn, str_filePath = FileUtil.saveData(fileObj)
        except Exception as e:
            AgentLogger.log([AgentLogger.PLUGINS, AgentLogger.STDERR], ' *************************** Exception while loading Plugins List  *************************** ' + repr(e))
            traceback.print_exc()
    
    def deletePlugins(self):
        try:
            self.__class__._plugins_List=[]
            self.__class__._plugins_Dict.clear()
        except Exception as e:
            AgentLogger.log([AgentLogger.PLUGINS, AgentLogger.STDERR], '*************************** Exception while deleting PLUGINS *************************** ' + repr(e))
            traceback.print_exc()
    
    def loadPlugins(self):
        lastModifiedTime = max(os.path.getmtime(root) for root,_,_ in os.walk(AgentConstants.AGENT_PLUGINS_DIR))
        global previousLastModifiedTime
        if lastModifiedTime > previousLastModifiedTime or AgentConstants.FORCE_LOAD_PLUGINS:
            AgentLogger.log(AgentLogger.PLUGINS,'Loading Plugins')
            if AgentConstants.FORCE_LOAD_PLUGINS:
                AgentConstants.FORCE_LOAD_PLUGINS = False
            import fnmatch
            no_of_folders = len(fnmatch.filter(os.listdir(AgentConstants.AGENT_PLUGINS_DIR),'*'))
            if no_of_folders > 100:
                AgentConstants.AGENT_SCHEDULER_NO_OF_PLUGIN_WORKERS = math.ceil(no_of_folders/20)
                AgentScheduler.Scheduler.startScheduler('PluginScheduler', AgentConstants.AGENT_SCHEDULER_NO_OF_PLUGIN_WORKERS)
                AgentLogger.log(AgentLogger.PLUGINS,'scheduling  {0}'.format(AgentConstants.AGENT_SCHEDULER_NO_OF_PLUGIN_WORKERS))
            else :
                AgentConstants.AGENT_SCHEDULER_NO_OF_PLUGIN_WORKERS = 5
            with self._lock:
                self.deletePlugins()
            self._loadDefaultPlugins()
            self._loadPluginsList()
            previousLastModifiedTime = lastModifiedTime
            self.doPluginDC()
    
    def loadPluginTask(self):
        try:
            task = self.loadPlugins
            scheduleInfo = AgentScheduler.ScheduleInfo()
            scheduleInfo.setSchedulerName('AgentScheduler')
            scheduleInfo.setTaskName('PluginLoader')
            scheduleInfo.setTime(time.time())
            scheduleInfo.setTask(task)
            scheduleInfo.setIsPeriodic(True)
            scheduleInfo.setInterval(AgentConstants.PLUGINS_LOAD_INTERVAL)
            scheduleInfo.setLogger(AgentLogger.PLUGINS)
            AgentScheduler.schedule(scheduleInfo)
        except Exception as e:
            traceback.print_exc()
    
    def doPluginDC(self):
        try:
            with self._lock:
                for pluginName, plugin in self.__class__._plugins_Dict.items():
                    task = self.pluginExecutor
                    taskArgs = plugin
                    scheduleInfo = AgentScheduler.ScheduleInfo()
                    scheduleInfo.setSchedulerName('PluginScheduler')
                    scheduleInfo.setTaskName(pluginName)
                    scheduleInfo.setTime(time.time())
                    scheduleInfo.setTask(task)
                    scheduleInfo.setTaskArgs(taskArgs)
                    scheduleInfo.setIsPeriodic(True)
                    scheduleInfo.setInterval(plugin.poll_interval)
                    scheduleInfo.setLogger(AgentLogger.PLUGINS)
                    AgentScheduler.schedule(scheduleInfo)
        except Exception as e:
            AgentLogger.log([AgentLogger.PLUGINS, AgentLogger.STDERR], '************* Exception while DC of Plugin ****' + repr(e))
            traceback.print_exc()
    
    def pluginExecutor(self,plugin):
        try:
            plugin.setPluginStatus()
            plugin.pluginDC()
        except Exception as e:
            traceback.print_exc()
    
    def initiatePluginDC(self):
        try:
            self._loadDefaultPlugins()
            self._loadPluginsList()
            self.doPluginDC()
        except Exception as e:
            traceback.print_exc()
            
    def removePluginFromIgnoreList(self,pluginName):
        global IGNORED_PLUGINS
        if pluginName in IGNORED_PLUGINS:
            IGNORED_PLUGINS.pop(pluginName)
            AgentLogger.log(AgentLogger.PLUGINS,'==== Ignored Plugins List  ===='+repr(IGNORED_PLUGINS))

    def populateIgnorePluginsList(self,pluginName,errorMsg):
        global IGNORED_PLUGINS
        if pluginName not in IGNORED_PLUGINS:
            IGNORED_PLUGINS[pluginName] = {}
            IGNORED_PLUGINS[pluginName]['count'] = 1
            IGNORED_PLUGINS[pluginName]['error_msg'] = errorMsg
            AgentLogger.log(AgentLogger.PLUGINS,'List of Ignored Plugins ====> {}'.format(json.dumps(IGNORED_PLUGINS))+'\n')
            AgentConstants.UPDATE_PLUGIN_INVENTORY=True
        
    def refresh_ignored_plugins_list(self,dict_task):
        global IGNORED_PLUGINS
        AgentLogger.log(AgentLogger.PLUGINS,'entry in re-registration | List of IGNORED_PLUGINS ====> {}'.format(json.dumps(IGNORED_PLUGINS)))
        if 'PLUGIN_NAME' in dict_task:
            pname = dict_task['PLUGIN_NAME']
            if pname in IGNORED_PLUGINS:
                IGNORED_PLUGINS.pop(pname)
                module_object_holder.plugins_util.rediscoverDeletedPlugins(dict_task)
            else:
                AgentLogger.log(AgentLogger.PLUGINS,' plugin not present in the ignored list  -- {0}'.format(pname))
        else:
            IGNORED_PLUGINS = {}
        AgentLogger.log(AgentLogger.PLUGINS,'exit in re-registration | List of IGNORED_PLUGINS ====> {}'.format(json.dumps(IGNORED_PLUGINS)))
        
    def updateInventoryToServer(self):
        inventory_dict={}
        plugins_dict=None
        if not AgentConstants.PLUGIN_FOLDER_DICT == None:
            inventory_dict = AgentConstants.PLUGIN_FOLDER_DICT
        if os.path.exists(AgentConstants.AGENT_PLUGINS_SITE24X7ID):
            bool_FileLoaded, plugins_dict = AgentUtil.loadDataFromFile(AgentConstants.AGENT_PLUGINS_SITE24X7ID)
        if plugins_dict:
            for key,value in plugins_dict.items():
                temp_dict = {}
                foldername,file_type = fetchFileType(key)
                temp_dict['status']=value['status']
                if 'version' in value:
                    temp_dict['version']=value['version']
                if 'heartbeat_required' in value:
                    temp_dict['heartbeat_required']=value['heartbeat_required']
                if 'instance_name' in value:
                    temp_dict['instance_name']=value['instance_name']
                if 'plugin_name' in value:
                    temp_dict['plugin_name']=value['plugin_name']
                if 'error_msg' in value:
                    temp_dict['error_msg']=value['error_msg']
                inventory_dict[key]=temp_dict
        if IGNORED_PLUGINS:
            for item,value in IGNORED_PLUGINS.items():
                inventory_dict[item]={}
                inventory_dict[item]['status']=2
                inventory_dict[item]['error_msg']=value['error_msg']
        try:
            if not inventory_dict==None:
                str_servlet = AgentConstants.DATA_AGENT_HANDLER_SERVLET
                dict_requestParameters      =   {
                'agentKey'  :   AgentUtil.AGENT_CONFIG.get('AGENT_INFO', 'agent_key'),
                'action'  :   AgentConstants.PLUGIN_INVENTORY,
                'bno' : AgentConstants.AGENT_VERSION,
                'custID'  :   AgentConstants.CUSTOMER_ID        
                }
                str_jsonData = json.dumps(inventory_dict)#python dictionary to json string
                AgentLogger.log(AgentLogger.PLUGINS, 'Plugin Inventory to be sent : '+repr(str_jsonData))
                str_url = None
                if not dict_requestParameters == None:
                    str_requestParameters = urlencode(dict_requestParameters)
                    str_url = str_servlet + str_requestParameters
                requestInfo = com.manageengine.monagent.communication.CommunicationHandler.RequestInfo()
                requestInfo.set_loggerName(AgentLogger.PLUGINS)
                requestInfo.set_method(AgentConstants.HTTP_POST)
                requestInfo.set_url(str_url)
                requestInfo.set_data(str_jsonData)
                requestInfo.add_header("Content-Type", 'application/json')
                requestInfo.add_header("Accept", "text/plain")
                requestInfo.add_header("Connection", 'close')
                (isSuccess, int_errorCode, dict_responseHeaders, dict_responseData) = com.manageengine.monagent.communication.CommunicationHandler.sendRequest(requestInfo)
        except Exception as e:
            traceback.print_exc()
    
#filename can be used as folder name too
def fetchFileType(fileName):
    fileName, fileExt = os.path.splitext(fileName)
    return fileName,fileExt

def getPluginStatus(name):
        bool_pluginreg = False
        plugin_status = 0
        try:
            tempIdDict = module_object_holder.plugins_util.getPluginConfDict()
            if tempIdDict and name in tempIdDict:
                    if 'pluginkey' in tempIdDict[name]:
                        bool_pluginreg = True
                    plugin_status = tempIdDict[name]['status']
        except Exception as e:
            traceback.print_exc()
        return bool_pluginreg,plugin_status
  
def uploadScriptResponse(key, upload_dict, tempIdDict,config_Change):
    try:
        upload_dict['ct'] = AgentUtil.getTimeInMillis()
        if 'units' in upload_dict and config_Change==False:
                upload_dict.pop('units')
        if 'heartbeat_required' in upload_dict['data']:
            upload_dict['data'].pop('heartbeat_required')
        
        if 'plugin_version' in upload_dict['data']:
            version=upload_dict['data']['plugin_version']
            upload_dict['data'].pop('plugin_version')
        elif 'plugin_version' in upload_dict:
            version=upload_dict['plugin_version']
            upload_dict.pop('plugin_version')
        else:
            version="1"
        upload_dict['version'] =version
        pluginkey= tempIdDict[key]['pluginkey']
        if config_Change:
            upload_dict['config_data']=tempIdDict[key]
        savePluginData(upload_dict,pluginkey,key)
    except Exception as e:
        AgentLogger.log([AgentLogger.PLUGINS, AgentLogger.STDERR], ' *************************** Exception while uploading response to Server *************************** ' + repr(e))
        traceback.print_exc()
            
def registerScript(key, upload_dict,self):
    global registration_lock
    dict_requestParameters = {}
    requestInfo = com.manageengine.monagent.communication.CommunicationHandler.RequestInfo()
    plugin_disp_name = None
    with registration_lock:
        try:
            if AgentConstants.PLUGIN_DEPLOY_CONFIG and self.name in AgentConstants.PLUGIN_DEPLOY_CONFIG:
                dict_requestParameters['deployment_params'] = AgentConstants.PLUGIN_DEPLOY_CONFIG[self.name]
            dict_requestParameters['agentkey'] = AgentUtil.AGENT_CONFIG.get('AGENT_INFO', 'agent_key')
            dict_requestParameters['plugin_name'] = self.name
            server_name = AgentConstants.HOST_NAME
            if AgentUtil.AGENT_CONFIG.has_option('AGENT_INFO','display_name') and not AgentUtil.AGENT_CONFIG.get('AGENT_INFO','display_name')=='0':
                server_name = AgentUtil.AGENT_CONFIG.get('AGENT_INFO','display_name')
            if 'display_name' in upload_dict:
                plugin_disp_name = upload_dict.pop('display_name')
            else:
                if self.instance_name:
                    dict_requestParameters['name']= self.name+"-"+self.instance_name
                    plugin_disp_name = self.name+"-"+self.instance_name+"-"+server_name
                else:
                    plugin_disp_name = self.name+"-"+server_name
            dict_requestParameters['display_name'] = plugin_disp_name
            dict_requestParameters['ct'] = AgentUtil.getTimeInMillis()
            dict_requestParameters['bno'] = AgentConstants.AGENT_VERSION
            if 'plugin_version' in upload_dict['data']:
                version=upload_dict['data']['plugin_version']
                upload_dict['data'].pop('plugin_version')
            else:
                version="1"
            if 'heartbeat_required' in upload_dict['data']:
                heartbeat=upload_dict['data']['heartbeat_required']
                upload_dict['data'].pop('heartbeat_required')
            else:
                heartbeat="true"
            dict_requestParameters['version'] =version
            dict_requestParameters['heartbeat_required'] = heartbeat
            AgentLogger.log(AgentLogger.PLUGINS, 'Registering Plugin =======> {0} '.format(json.dumps(dict_requestParameters))+'\n')
            dict_requestParameters['apikey'] = AgentConstants.CUSTOMER_ID
            str_servlet = AgentConstants.PLUGIN_REGISTER_SERVLET
            if not dict_requestParameters == None:
                str_requestParameters = urlencode(dict_requestParameters)
                str_url = str_servlet + str_requestParameters
            str_dataToSend = json.dumps(upload_dict)
            str_contentType = 'application/json'
            requestInfo.set_loggerName(AgentLogger.PLUGINS)
            requestInfo.set_method(AgentConstants.HTTP_POST)
            requestInfo.set_url(str_url)
            requestInfo.set_data(str_dataToSend)
            requestInfo.set_dataType(str_contentType)
            requestInfo.add_header("Content-Type", str_contentType)
            requestInfo.add_header("Accept", "text/plain")
            requestInfo.add_header("Connection", 'close')
            (bool_isSuccess, errorCode, dict_responseHeaders, dict_responseData) = com.manageengine.monagent.communication.CommunicationHandler.sendRequest(requestInfo)
            if not bool_isSuccess and errorCode!=200:
                module_object_holder.plugins_util.removePluginConfig(key)
                if 'message' in upload_dict:
                    error_msg = upload_dict['message']
                else:
                    error_msg = 'Plugin registration failed with ' + str(errorCode)
                PluginHandler.populateIgnorePluginsList(self, key, error_msg)
            com.manageengine.monagent.communication.CommunicationHandler.handleResponseHeaders(dict_responseHeaders, dict_responseData, 'PLUGINS')
        except Exception as e:
            AgentLogger.log([AgentLogger.PLUGINS, AgentLogger.STDERR], ' *************************** Exception while registering Plugin to Server *************************** ' + repr(e))
            traceback.print_exc()

def getCmdForExecution(fileExt, cmd):
    command = None
    try:
        if '---site24x7version' in cmd:
            command=cmd.split('---site24x7version')[0]
            AgentLogger.log(AgentLogger.PLUGINS,' nagios cmd ==== {0}'.format(command))
        else:
#             if platform.system() == 'Darwin':
#                 command = "sudo "+cmd
#             else:
            command = cmd
    except Exception as e:
        AgentLogger.log([AgentLogger.PLUGINS, AgentLogger.STDERR], ' *************************** Exception while fetching command for execution *************************** ' + repr(e))
        traceback.print_exc()
    return command

def getNagiosVersion(pluginType,cmd):
    version_Value=1
    try:
        if pluginType == 'nagios' and '---site24x7version' in cmd:
            version_Value=cmd.split('---site24x7version=')[1]
            AgentLogger.log(AgentLogger.PLUGINS,' nagios Version ==== {0}'.format(version_Value))
    except Exception as e:
         AgentLogger.log(AgentLogger.PLUGINS,' Exception in getting nagios version ')
         traceback.print_exc()
    return version_Value

def checkForPluginSupport(file,pluginType):
    if pluginType == 'nagios':
        return True
    if file=='.py' or file=='.sh':
        return True
    else:
        return False

def savePluginData(pluginData,key,name):
    try:
        AgentLogger.debug(AgentLogger.PLUGINS,'Plugin :: {0} | Data to Persist :: {1} '.format(name,json.dumps(pluginData)))
        str_fileName = FileUtil.getUniquePluginFileName(key,pluginData['ct'])
        str_filePath = AgentConstants.AGENT_UPLOAD_PROPERTIES_MAPPER['002']['data_path'] + '/' + str_fileName
        fileObj = AgentUtil.FileObject()
        fileObj.set_fileName(str_fileName)
        fileObj.set_filePath(str_filePath)
        fileObj.set_data(pluginData)
        fileObj.set_dataType('json')
        fileObj.set_mode('wb')
        fileObj.set_dataEncoding('UTF-16LE')
        fileObj.set_logging(False)
        fileObj.set_loggerName(AgentLogger.PLUGINS)            
        bool_toReturn, str_filePath = FileUtil.saveData(fileObj)
        if bool_toReturn:
            AgentLogger.debug(AgentLogger.PLUGINS,'Statistics file name and saved to : '+str_fileName + str_filePath)
    except Exception as e:
        AgentLogger.log([AgentLogger.UDP,AgentLogger.STDERR], ' *************************** Exception while saving plugin data *************************** '+ repr(e))
        traceback.print_exc()
