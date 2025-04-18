from six.moves.urllib.parse import urlencode
from com.manageengine.monagent.hardware import HardwareConstants
from com.manageengine.monagent import AgentConstants
from com.manageengine.monagent.util import AgentUtil
from com.manageengine.monagent.util.AgentUtil import ZipUtil
from com.manageengine.monagent.logger import AgentLogger
from com.manageengine.monagent.scheduler import AgentScheduler
from com.manageengine.monagent.hardware import SmartMonitoring
from com.manageengine.monagent.apps import persist_data
from com.manageengine.monagent.communication import CommunicationHandler

import json
import time
import sys
import traceback
try:
    import configparser
except Exception as e:
    import ConfigParser as configparser

HARDWARE_CONFIG= configparser.RawConfigParser()
HARDWARE_CONFIG.read(HardwareConstants.HARDWARE_CONF_FILE)
HARDWARE_SCRIPTS_CONFIG= configparser.RawConfigParser()
HARDWARE_SCRIPTS_CONFIG.read(HardwareConstants.HARDWARE_SCRIPT_CONF_FILE)

def initialize():
    try:
        dictRegData={}
        AgentLogger.log(AgentLogger.HARDWARE, 'Hardware initialize started \n')
        HARDWARES=["SMARTDISK"]
        for section in HARDWARES:   
            discover_hardwares(section)               
        initiate_hardware_dc()
    except Exception as e:
        traceback.print_exc()
        AgentLogger.log(AgentLogger.HARDWARE, 'Error during initialize '+str(e)+'\n')
        
def discover_hardwares(section):
    try:
        dis_result={}                            
        script_name=HARDWARE_SCRIPTS_CONFIG.get('HARDWARE_SCRIPTS', section+'_DISCOVERY')
        script_path=HARDWARE_SCRIPTS_CONFIG.get('HARDWARE_SCRIPTS', section+'_PATH') 
        AgentLogger.log(AgentLogger.HARDWARE, 'scripts to be execute '+str(script_name)+'\n') 
        script_path=sys.modules[script_path]
        dis_result=getattr(script_path,script_name)() #UNIQUE KEY AND CONFIG PARAM
        if dis_result and dis_result["unique_key"]:
            for param in dis_result["unique_key"]: 
                if HARDWARE_CONFIG.has_section(section): #OLD SECTION,NEW KEYS
                    if not(HARDWARE_CONFIG.has_option(section,param)):
                        HARDWARE_CONFIG.set(section, param, dis_result['value'])
                        AgentLogger.log(AgentLogger.HARDWARE, 'Discovered  Hardwares: '+" : "+str(dis_result['unique_key'])+'\n')
                else:
                    HARDWARE_CONFIG.add_section(section)  #NEW SECTION ,NEW KEYS
                    HARDWARE_CONFIG.set(section, param, dis_result['value'])
                    AgentLogger.log(AgentLogger.HARDWARE, 'Discovered new Hardwares section: '+" : "+str(dis_result['unique_key'])+'\n')
            with open(HardwareConstants.HARDWARE_CONF_FILE, 'w+') as set:
                    HARDWARE_CONFIG.write(set)
    except Exception as e:
        traceback.print_exc()
        AgentLogger.log(AgentLogger.HARDWARE, 'Error during Discovering Hardwares '+str(e)+'\n') 
        
def initiate_hardware_dc():
    try:
        newly_added=False
        dict_requestParameters={}
        HARDWARE_CONFIG.read(HardwareConstants.HARDWARE_CONF_FILE)
        for section in HARDWARE_CONFIG.sections():
            for unique_key,params in HARDWARE_CONFIG.items(section):
                if not isinstance(params, dict):
                    params=params.replace("'",'"')
                    params=json.loads(params)
                result={}
                attributes={}
                status_check=False
                attributes[unique_key]=params
                result=validate_hardware_output(section,attributes)
                if result and result['output']:
                    if  'status' not in params:
                        newly_added=True
                        dict_requestParameters[section.lower()] = 'true'
                        for key,val in result['output']['config'].items():
                            if key in dict_requestParameters:
                                dict_requestParameters[key] = str(dict_requestParameters[key])+','+val   
                            else:
                                dict_requestParameters[key] = val
                    elif str(params['status'])=='0':
                        mid=params['mid']
                        schedule(result,mid)
                    else:
                        AgentLogger.log(AgentLogger.HARDWARE,"********** Discovery or Scheduling Not initiated  : "+str(params) +"  **********")                                          
        if newly_added:
            send_hardware_discovery(HARDWARE_CONFIG.items(section),dict_requestParameters)   
    except Exception as e:
        traceback.print_exc()
        AgentLogger.log(AgentLogger.HARDWARE, 'Error in initiate_hardware_dc during initialize '+str(e)+'\n')

def validate_hardware_output(section,attributes):
    try:
        result={}
        script_name=HARDWARE_SCRIPTS_CONFIG.get('HARDWARE_SCRIPTS', section)
        script_path=HARDWARE_SCRIPTS_CONFIG.get('HARDWARE_SCRIPTS', section+'_PATH') 
        AgentLogger.log(AgentLogger.HARDWARE, 'Attributes in conf file : '+str(attributes)+'\n') 
        script_path=sys.modules[script_path]
        result['output']=getattr(script_path,script_name)(attributes)
        result['attributes']=attributes
        result['script_name']=script_name
        result['script_path']= script_path
        return result  
    except Exception as e:
        traceback.print_exc()
        AgentLogger.log(AgentLogger.HARDWARE, 'Error during Application Discovery Hardwares '+str(e)+'\n') 

def send_hardware_discovery(hardwares,dict_requestParameters):
    str_url = None
    hardware_key= None
    try:
        dict_requestParameters['agentKey'] = AgentUtil.AGENT_CONFIG.get('AGENT_INFO', 'agent_key')
        dict_requestParameters['CUSTOMERID'] = AgentConstants.CUSTOMER_ID
        dict_requestParameters['bno'] = AgentConstants.AGENT_VERSION
        dict_requestParameters['REDISCOVER'] = "TRUE"
        str_servlet = AgentConstants.APPLICATION_DISCOVERY_SERVLET
        if not dict_requestParameters == None:
            str_requestParameters = urlencode(dict_requestParameters)
            str_url = str_servlet + str_requestParameters
        AgentLogger.log(AgentLogger.HARDWARE, "str_url:"+str_url)
        requestInfo = CommunicationHandler.RequestInfo()
        requestInfo.set_loggerName(AgentLogger.HARDWARE)
        requestInfo.set_method(AgentConstants.HTTP_GET)
        requestInfo.set_url(str_url)
        requestInfo.set_dataType('application/json')
        requestInfo.add_header("Content-Type", 'application/json')
        requestInfo.add_header("Accept", "text/plain")
        requestInfo.add_header("Connection", 'close')
        AgentLogger.log(AgentLogger.HARDWARE, "=========================== STARTING HARDWARE REGISTRATION ========================\n")
        (bool_isSuccess, errorCode, dict_responseHeaders, dict_responseData) = CommunicationHandler.sendRequest(requestInfo)
        AgentLogger.log(AgentLogger.HARDWARE,"HARDWARE  - {0} | headers - {1}  | errrors - {2} ".format(bool_isSuccess,json.dumps(dict_responseHeaders),errorCode))
        if dict_responseHeaders:
            for get_hardware in HARDWARE_CONFIG.sections():
                if get_hardware.lower() in dict_responseHeaders:
                    hardware_key = dict_responseHeaders[get_hardware.lower()]
                    hardware_key=hardware_key.split(",")
                    for unique_key in hardware_key:
                        if '@' in unique_key:
                            ukey,mid=unique_key.split("@") 
                            value_params={}
                            value_params={'mid':mid,'status':0}
                            HARDWARE_CONFIG.set(get_hardware, ukey,value_params)
                            attributes={ukey:value_params}
                            frame=validate_hardware_output(get_hardware,attributes)
                            schedule(frame,mid)
            with open(HardwareConstants.HARDWARE_CONF_FILE, 'w+') as set:
                 HARDWARE_CONFIG.write(set)
        else:
            AgentLogger.log(AgentLogger.HARDWARE, "===NO RESPONSE FOUND===\n")
    except Exception as e:
        AgentLogger.log(AgentLogger.HARDWARE, " Exception while sending data {0}".format(e))
        traceback.print_exc()
                
def schedule(result,mid):
    try:
        script_name=result['script_name']
        script_path=result['script_path']
        args=result['attributes']
        interval=300
        task=getattr(script_path,script_name)
        taskArgs=args
        taskName=mid
        callback=data_save
        scheduleInfo=AgentScheduler.ScheduleInfo()
        scheduleInfo.setIsPeriodic(True)
        scheduleInfo.setSchedulerName('AgentScheduler')
        scheduleInfo.setTaskName(taskName)
        scheduleInfo.setTime(time.time())
        scheduleInfo.setTask(task)
        scheduleInfo.setTaskArgs(taskArgs)
        scheduleInfo.setCallback(callback)
        scheduleInfo.setInterval(interval)
        scheduleInfo.setLogger(AgentLogger.HARDWARE)
        AgentLogger.log(AgentLogger.HARDWARE, 'scheduled : '+str(script_name)+'\n')
        AgentScheduler.schedule(scheduleInfo)
    except Exception as e:
        traceback.print_exc()
        AgentLogger.log(AgentLogger.HARDWARE, 'Error at scheduling '+str(e)+'\n')
    
def data_save(result_args):
    try:
        result_data={}
        dir_prop = None
        app_name=result_args['script']
        result_data=result_args['data']
        if app_name == 'SMARTDISK':
            dir_prop = AgentConstants.AGENT_UPLOAD_PROPERTIES_MAPPER['010']
        status,file_name=persist_data.save(dir_prop, result_data,AgentLogger.HARDWARE)
        if status:
            if dir_prop['instant_zip']:
                ZipUtil.zipFilesAtInstance([[file_name]],dir_prop)
    except Exception as e:
        AgentLogger.log(AgentLogger.HARDWARE, 'Error at Datasave '+str(e)+'\n')
        traceback.print_exc()
                
def suspend_hardware_monitoring(args):
    try:
        str_mtype=args['mtype']
        taskname=args['mid']
        scheduleInfo=AgentScheduler.ScheduleInfo()
        if HARDWARE_CONFIG.has_section(str_mtype):
            for unique_key,params in HARDWARE_CONFIG.items(str_mtype):
                if not isinstance(params, dict):
                    params=params.replace("'",'"')
                    params=json.loads(params)
                if 'mid' in params and params['mid']== taskname:
                    params['status']=5              
                    HARDWARE_CONFIG.set(str_mtype, unique_key,params) 
                    scheduleInfo.setSchedulerName('AgentScheduler')
                    scheduleInfo.setTaskName(taskname)
                    AgentScheduler.deleteSchedule(scheduleInfo)
                    AgentLogger.log(AgentLogger.HARDWARE,'******************Suspending '+str_mtype +" key : "+taskname +'  Monitoring******************\n')
            with open(HardwareConstants.HARDWARE_CONF_FILE, 'w+') as set:
                HARDWARE_CONFIG.write(set)
    except Exception as e :
        AgentLogger.log(AgentLogger.HARDWARE,'**********Error in Suspending '+str_mtype +' Monitoring '+str(e)+'\n')
        traceback.print_exc()
        
def activate_hardware_monitoring(args):
    try:
        str_mtype=args['mtype']
        taskname=args['mid']
        if HARDWARE_CONFIG.has_section(str_mtype):
            for unique_key,params in HARDWARE_CONFIG.items(str_mtype):
                if not isinstance(params, dict):
                    params=params.replace("'",'"')
                    params=json.loads(params)
                attributes={} 
                if 'mid' in params and params["mid"]== taskname:
                    params["status"]=0             
                    HARDWARE_CONFIG.set(str_mtype, unique_key,params)
                    attributes={unique_key:params}
                    frame=validate_hardware_output(str_mtype,attributes)
                    schedule(frame,taskname)
                    AgentLogger.log(AgentLogger.HARDWARE,'******************Activating '+str_mtype +" key : "+taskname +'  Monitoring******************\n')      
            with open(HardwareConstants.HARDWARE_CONF_FILE, 'w+') as set:
                HARDWARE_CONFIG.write(set)
    except Exception as e :
        AgentLogger.log(AgentLogger.HARDWARE,'**********Error in Activating '+str_mtype +' Monitoring '+str(e)+'\n')
        traceback.print_exc()

def delete_hardware_monitoring(args):
    try:
        str_mtype=args['mtype']
        taskname=args['mid']
        if HARDWARE_CONFIG.has_section(str_mtype):
            for unique_key,params in HARDWARE_CONFIG.items(str_mtype):
                if not isinstance(params, dict):
                    params=params.replace("'",'"')
                    params=json.loads(params)
                if 'mid' in params and params["mid"]== taskname:                  
                    scheduleInfo=AgentScheduler.ScheduleInfo()
                    scheduleInfo.setSchedulerName('AgentScheduler')
                    scheduleInfo.setTaskName(taskname)
                    AgentScheduler.deleteSchedule(scheduleInfo)
                    params['status']=3 
                    HARDWARE_CONFIG.set(str_mtype, unique_key,params)  
            AgentLogger.log(AgentLogger.HARDWARE,'\n******************  Deleting '+str_mtype +" Monitoring  key : "+taskname +'  ******************\n')
            with open(HardwareConstants.HARDWARE_CONF_FILE, 'w+') as set:
                HARDWARE_CONFIG.write(set)
    except Exception as e :
        AgentLogger.log(AgentLogger.HARDWARE,'**********Error in Deleting '+str_mtype +' Monitoring '+str(e)+'\n')
        traceback.print_exc()

def rediscover_hardware_monitoring():
    try:
        (bool_isSuccess, dict_monitorsGroup) = AgentUtil.loadDataFromFile(AgentConstants.AGENT_MONITORS_GROUP_FILE)
        if 'HardwareMonitoring' in dict_monitorsGroup['MonitorGroup']:
            AgentLogger.log(AgentLogger.HARDWARE,'******************Rediscover Hardware  Monitoring******************\n')
            for section in HARDWARE_CONFIG.sections():
                for unique_key,params in HARDWARE_CONFIG.items(section):
                    if not isinstance(params, dict):
                        params=params.replace("'",'"')
                        params=json.loads(params)
                if 'status' in params and str(params['status'])=='3':  
                    params.pop("mid",None)
                    params.pop("status",None)
                    HARDWARE_CONFIG.set(section, unique_key,params)
                    AgentLogger.log(AgentLogger.HARDWARE,'******************Deleting '+section +' conf status to Rediscover  Hardware monitoring******************\n')
            initialize()
    except Exception as e :
        AgentLogger.log(AgentLogger.HARDWARE,'**********Error in Rediscover Hardware Monitoring '+str(e)+'\n')
        traceback.print_exc()
        
def reregister_hardware_monitoring(delete_schedule=False):
    try:
        scheduleInfo=AgentScheduler.ScheduleInfo()
        for section in HARDWARE_CONFIG.sections():
            for unique_key,params in HARDWARE_CONFIG.items(section):
                if not isinstance(params, dict):
                    params=params.replace("'",'"')
                    params=json.loads(params)  
                if delete_schedule:
                     if 'status' in params and str(params['status'])=='0':
                        ScheduleInfo=AgentScheduler.ScheduleInfo()
                        scheduleInfo.setSchedulerName('AgentScheduler')
                        scheduleInfo.setTaskName(params["mid"])
                        AgentScheduler.deleteSchedule(scheduleInfo)
                params.pop("mid",None)
                params.pop("status",None)
                HARDWARE_CONFIG.set(section, unique_key,params)
                AgentLogger.log(AgentLogger.HARDWARE,'******************Deleting '+section +' for Re-register  Hardware monitoring******************\n')
        with open(HardwareConstants.HARDWARE_CONF_FILE, 'w+') as set:
            HARDWARE_CONFIG.write(set)
    except Exception as e :
        AgentLogger.log(AgentLogger.HARDWARE,'********** Error in Re-register  Hardware monitoring  '+str(e)+'*********************\n')
        traceback.print_exc()
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
            