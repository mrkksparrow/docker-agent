#!/usr/bin/python
import json
import re
import subprocess
import shutil
from com.manageengine.monagent.logger import AgentLogger
from com.manageengine.monagent.scheduler import AgentScheduler
from com.manageengine.monagent.util import AgentUtil
import traceback

def init_smartctl_path():
    global smartctl_path
    smartctl_path='/usr/sbin/smartctl'
    try:
        temp_path=shutil.which('smartctl')
        if temp_path:
            smartctl_path=temp_path
            AgentLogger.log(AgentLogger.HARDWARE, 'Smartctl path : '+str(smartctl_path))
    except Exception as e:
        AgentLogger.log(AgentLogger.HARDWARE, 'Smartctl path error --{0} so Default_path is taken --{1} \n'.format(e,smartctl_path))
        
class SmartDiskMonitoring(object):
    def __init__(self,args):
        try:
            for key,value in args.items():
                self.disk=key
                params = value
            if  'mid' in params: 
                self.mid=params['mid']
            else:
                self.mid=None
        except Exception as e:
            traceback.print_exc()
            AgentLogger.log(AgentLogger.HARDWARE, 'Error at SmartDiskMonitoring init '+str(e))
    
    def data_extract(self):
        try:  
            smart_data={}
            parameter_dictionary={}
            executorObj = AgentUtil.Executor()
            executorObj.setLogger(AgentLogger.HARDWARE)
            executorObj.setTimeout(30)
            executorObj.setCommand(smartctl_path+' --all -A '+self.disk)
            executorObj.executeCommand()
            retVal    = executorObj.getReturnCode()
            stdOutput = executorObj.getStdOut()
            stdErr    = executorObj.getStdErr()
            if not stdErr:
                parameter_dictionary['onchange']={}
                output=str(stdOutput) 
                if '\\t' in output:
                    output=output.replace('\\t','')
                else:
                    output=output.replace('\t','')
                output_list=re.split('(\\\\n)+|(\\\n)+',output)
                    
                attribute_index=output_list.index('ID# ATTRIBUTE_NAME          FLAG     VALUE WORST THRESH TYPE      UPDATED  WHEN_FAILED RAW_VALUE')        
                for info in output_list:        
                    try:
                        if ':' in info: 
                            key,value =(str(info).split(':',1))
            
                            if len(value):
                                if 'SMART overall-health self-assessment test result' in key:
                                    key='SMART health assessment test'
                                parameter_dictionary['onchange'][key.replace(" ","_")]=(str(value)).strip()            
                        if output_list.index(info) > attribute_index:                        
                            if ' Temperature_Celsius ' in info:
                                id,attribute_name,flag,value,worst,thresh,types,updated,when_failed,raw_value,min,max,min_val,max_val=re.findall(r"[\w\-\(\)]+",info)
                            else:                                              
                                id,attribute_name,flag,value,worst,thresh,types,updated,when_failed,raw_value=re.findall(r"[\w\-\(\)]+",info)                
                            if type(int(id))==int:
                                #value given here is raw_value
                                parameter_dictionary[attribute_name.lower()]=(str(raw_value).strip())
                                parameter_dictionary[attribute_name.lower()+'_worst']=(str(worst)).strip()
                                parameter_dictionary[attribute_name.lower()+'_threshold']=(str(thresh).strip())
                    except Exception as e:
                        continue
                if self.mid:
                    parameter_dictionary['mid']=self.mid
                data=(json.dumps(parameter_dictionary,sort_keys=True))
                AgentLogger.log(AgentLogger.HARDWARE,' Smart Disk Data Collected : '+str(data)) 
                smart_data['script']='SMARTDISK'
                smart_data['data']=data
                smart_data['config']={'disk':self.disk}
                unavailable='- NA -'
                if 'Model_Family' in parameter_dictionary['onchange']:
                    smart_data['config']['model_family']=parameter_dictionary['onchange']['Model_Family'].lower()
                else:
                    if 'Device_Model' in parameter_dictionary['onchange'] and 'toshiba' in parameter_dictionary['onchange']['Device_Model'].lower():
                        smart_data['config']['model_family'] = 'toshiba'
                    else:
                        smart_data['config']['model_family']=unavailable
                    
                if 'Device_Model' in parameter_dictionary['onchange']:
                    smart_data['config']['device_model']=parameter_dictionary['onchange']['Device_Model'].lower()
                else:
                    smart_data['config']['device_model']=unavailable
            else:
                AgentLogger.log(AgentLogger.HARDWARE, '***** No data collected for smartdisk :: {} :: {} :: {} *****'.format(self.disk, stdOutput, stdErr))
                smart_data=False
        except Exception as e:
            AgentLogger.log(AgentLogger.HARDWARE, '***** Exception while collecting smartdisk data :: {} ::{} *****'.format(self.disk,e))
            traceback.print_exc()
            smart_data=False
        finally:
            return smart_data
                    
def smartdisk(args):
    try:
        smart=SmartDiskMonitoring(args)
        result=smart.data_extract()
        return result
    except Exception as e:
        traceback.print_exc()
        AgentLogger.log(AgentLogger.HARDWARE, 'Error at SmartDisk'+str(e))

def discover_disk():
        try:
            config={}
            disk_name=[]
            init_smartctl_path()
            output=subprocess.check_output([smartctl_path, "--scan"])            
            output=(output.decode("utf-8"))
            tempoutput=(re.split(' |\n|\\n',output))
            for itr in range(0,len(tempoutput)):
                if(tempoutput[itr]=='-d'):
                    disk_name.append(tempoutput[itr-1])
            AgentLogger.log(AgentLogger.HARDWARE, "Discovered Disk Name : "+str(disk_name))
            config["unique_key"]=disk_name
            config["value"]={}
        except subprocess.CalledProcessError as e:
            AgentLogger.log(AgentLogger.HARDWARE, e.output) 
            config=False  
        except Exception as e:
            AgentLogger.log(AgentLogger.HARDWARE, 'Smartctl command not found in Discovering Disk '+str(e))
            traceback.print_exc()
            config=False
        finally:
            return config
        