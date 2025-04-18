#$Id$
import os
import json
import traceback
import platform
import time

import com
from com.manageengine.monagent import AgentConstants
from com.manageengine.monagent.logger import AgentLogger
from com.manageengine.monagent.util import AgentUtil

try:
    import psutil
except Exception as e:
    traceback.print_exc()
    AgentLogger.log(AgentLogger.COLLECTOR,'exception while importing ps util ')

COUNTER_DICT={}
PARAM_VS_PSUTIL_KEY={'bytesrcv':'bytes_recv','bytessent':'bytes_sent','pktsent':'packets_sent','pktrcv':'packets_recv','errorpkts':'errout','ctxtsw':'ctx_switches','interrupts':'interrupts','dwrites':'write_bytes','dreads':'read_bytes'}


def get_metrics(dictData , dictKeyData , dictConfig):
    try:
        get_load_average(dictData)
        get_process_metrics(dictData)
        get_asset_info(dictData)
        get_system_stats(dictData)
    except Exception as e:
        AgentLogger.log(AgentLogger.COLLECTOR,'exception occurred in collect metrics')
        traceback.print_exc()

def collect_metrics(dictData , dictKeyData , dictConfig):
    try:
        get_asset_info(dictData)
        get_memory_info(dictData)
        get_cpu_core_info(dictData)
        get_process_metrics(dictData)
        get_load_average(dictData)
        get_network_data(dictData,dictConfig)
        get_cpu_stats(dictData)
        get_ps_util_cpu_stats(dictData)
        get_top_process_data(dictData)
        get_disk_io(dictData)
    except Exception as e:
        AgentLogger.log(AgentLogger.COLLECTOR,'exception occurred in collect metrics')
        traceback.print_exc()

def get_system_stats(dictData):
    try:
        executorObj = AgentUtil.Executor()
        executorObj.setLogger(AgentLogger.COLLECTOR)
        executorObj.setTimeout(30)
        executorObj.setCommand('who -q && ps aux | wc -l')
        executorObj.executeCommand()
        retVal    = executorObj.getReturnCode()
        stdOutput = executorObj.getStdOut()
        stdErr    = executorObj.getStdErr()
        AgentLogger.log(AgentLogger.COLLECTOR,' login and process count command output -- {0}'.format(stdOutput))
        if stdOutput:
           lines = stdOutput.split('\n')
           dictData['systemstats']['lc']=len(lines[0].split())
           dictData['systemstats']['totp']=int(lines[2].strip())-1  
    except Exception as e:
        traceback.print_exc()

def get_disk_io(dictData):
    try:
        disk_io=psutil.disk_io_counters()
        dictData['dreads'] = get_counter_value('dreads',disk_io)
        dictData['dwrites'] = get_counter_value('dwrites',disk_io)
        dictData['diskio'] = int(dictData['dreads'])+int(dictData['dwrites'])
    except Exception as e:
        AgentLogger.log(AgentLogger.COLLECTOR,'exception occurred in disk io')
        traceback.print_exc()

def get_top_process_data(dictData):
    try:
        AgentUtil.get_top_process_data()
        top_process_data = AgentConstants.PS_UTIL_PROCESS_DICT
        if top_process_data:
            dictData['TOPMEMORYPROCESS']=top_process_data['TOPMEMORYPROCESS']
            dictData['TOPCPUPROCESS']=top_process_data['TOPCPUPROCESS']
            dictData['fd']=top_process_data['fd']
    except Exception as e:
        AgentLogger.log(AgentLogger.COLLECTOR,'exception occurred in top process data')
        traceback.print_exc()

def get_ps_util_cpu_stats(dictData):
    try:
        import psutil
        cpu = psutil.cpu_times_percent(interval=2)
        idle_time = cpu.idle
        wait_time = cpu.iowait
        dictData['id']= idle_time
        dictData['wa']=wait_time
        dictData['us']=cpu.user
        dictData['sy']=cpu.system
        dictData['cper']=eval(AgentConstants.CPU_FORMULA)
    except Exception as e:
        AgentLogger.log(AgentLogger.COLLECTOR,'exception occurred in fetching cpu stats')
        traceback.print_exc()


def get_cpu_stats(dictData):
    try:
        cpu_stats = psutil.cpu_stats()
        if cpu_stats:
            dictData['ctxtsw'] = get_counter_value('ctxtsw',cpu_stats)
            dictData['interrupts'] = get_counter_value('interrupts',cpu_stats)
    except Exception as e:
        AgentLogger.log(AgentLogger.COLLECTOR,'exception occurred while fetching context switches and interrupts')
        traceback.print_exc()

def get_network_json(network_stats,interface_name,nic_config_dict,mac_address,network_interfaces_dict):
    temp_dict={}
    try:
        if nic_config_dict and mac_address in nic_config_dict:
            temp_dict['id'] = nic_config_dict[mac_address]
        else:
            temp_dict['id'] = "None"
        temp_dict['name'] = interface_name
        temp_dict['macadd'] = mac_address
        if 'status' in network_interfaces_dict[mac_address]:
            temp_dict['status']=0
        else:
            interface_stats = network_stats[interface_name]
            temp_dict['bandwidth'] = 100
            temp_dict['bytesrcv'] = get_counter_value(interface_name+'_bytesrcv',interface_stats)
            temp_dict['bytessent'] = get_counter_value(interface_name+'_bytessent',interface_stats)
            temp_dict['bytesrcvkb'] = (int(temp_dict['bytesrcv'])/1024)
            temp_dict['bytessentkb'] = (int(temp_dict['bytessent'])/1024)
            temp_dict['totbyteskb'] = temp_dict['bytesrcvkb'] +  temp_dict['bytessentkb']
            temp_dict['errorpkts'] = get_counter_value(interface_name+'_errorpkts',interface_stats)
            temp_dict['pktrcv'] = get_counter_value(interface_name+'_pktrcv',interface_stats)
            temp_dict['pktsent'] = get_counter_value(interface_name+'_pktsent',interface_stats)
            temp_dict['status']=1
    except Exception as e:
        AgentLogger.log(AgentLogger.COLLECTOR,'exception occurred while fetching network json')
        traceback.print_exc()
    return temp_dict
   
def get_counter_value(param,data_obj):
    global COUNTER_DICT
    return_value = 0
    try:
        if '_' in param:
            ps_util_key = PARAM_VS_PSUTIL_KEY[param.split('_')[1]]
        else:
            ps_util_key = PARAM_VS_PSUTIL_KEY[param]
        if param in COUNTER_DICT: 
           return_value = ( getattr(data_obj,ps_util_key) - float(COUNTER_DICT[param]) ) / int(AgentConstants.POLL_INTERVAL)
        else:
            return_value = 0
            COUNTER_DICT[param] = getattr(data_obj,ps_util_key)
    except Exception as e:
        AgentLogger.log(AgentLogger.COLLECTOR,'exception occurred in counter values block for param -- {0}'.format(param))
        traceback.print_exc()
    return round(return_value,2)
   
   
def get_aix_cpu(dictData, dictKeyData, dictConfig):
    try:
        cpu_data = dictKeyData['Cpu_Utilization'][0]
        if 'cpu_idle' in cpu_data:
            cpu_idle_percentage = cpu_data['cpu_idle']
            dictData['id'] = cpu_idle_percentage
            dictData['cper'] = 100 - float(cpu_idle_percentage)
        if 'cpu_user' in cpu_data:
            dictData['us'] = cpu_data['cpu_user']
        if 'cpu_wait' in cpu_data:
            dictData['wa'] = cpu_data['cpu_wait']
        if 'cpu_sys' in cpu_data:
            dictData['sy'] = cpu_data['cpu_sys']
        if 'interrupts' in cpu_data:
            dictData['interrupts'] = cpu_data['interrupts']
        if 'ctxtsw' in cpu_data:
            dictData['ctxtsw'] = cpu_data['ctxtsw']
        if 'pin' in cpu_data:
            dictData['pin'] = cpu_data['pin']
        if 'pout' in cpu_data:
            dictData['pout'] = cpu_data['pout']
    except Exception as e:
        AgentLogger.log(AgentLogger.COLLECTOR,'exception occurred while fetching cpu metrics')
        traceback.print_exc()

def get_aix_mem(dictData, dictKeyData, dictConfig):
    try:
        memory_data = dictKeyData['Memory_Utilization'][0]
        if 'tvirm' in memory_data:
            dictData['memory']['tvirm'] = int(float(memory_data['tvirm']))
        if 'uvirm' in memory_data:
            dictData['memory']['uvirm'] = int(float(memory_data['uvirm']))
        if 'fvirm' in memory_data:
            dictData['memory']['fvirm'] = int(float(memory_data['fvirm']))
        if 'tvism' in memory_data:
            dictData['memory']['tvism'] = int(float(memory_data['tvism']))
        if 'uvism' in memory_data:
            dictData['memory']['uvism'] = int(float(memory_data['uvism']))
        if 'available' in memory_data:
            dictData['memory']['available'] = int(float(memory_data['available']))
        if 'pin' in dictData:
            dictData['memory']['pin'] = dictData['pin']
        if 'pout' in dictData:
            dictData['memory']['pout'] = dictData['pout']
        dictData['asset']['ram'] = int(float(dictData['memory']['tvirm']))
        memUsedPercent = round((((float(dictData['memory']['tvirm']) - float(dictData['memory']['available']))/float(dictData['memory']['tvirm']))*100),2)
        dictData['mper'] = str(memUsedPercent)
        dictData['memory']['fvism']=float(dictData['memory']['tvism'])-float(dictData['memory']['uvism'])
        swapmemUsedPercent = round((((float(dictData['memory']['uvism']))/float(dictData['memory']['tvism']))*100),2)
        dictData['memory']['swpmemper'] = str(swapmemUsedPercent)
    except Exception as e:
        AgentLogger.log(AgentLogger.COLLECTOR,'exception occurred while fetching memory metrics')
        traceback.print_exc()
        
           
def get_aix_disk(dictData , dictKeyData , dictConfig):
    list_of_disks=[]
    totalDisk = 0
    totalUsedDisk = 0
    defaultDiskPer = 0
    try:
        listKeyDicts = dictKeyData['Disk_Utilization']
        for each_disk in listKeyDicts:
            temp_dict = {}
            if dictConfig and'DISKS' in dictConfig and each_disk['Name'] in dictConfig['DISKS']:
                temp_dict['id'] = dictConfig['DISKS'][each_disk['Name']]
            else:
                temp_dict['id'] = "None"
            temp_dict['duper'] = each_disk['Used_Percentage']
            temp_dict['dfper'] = 100 - int(each_disk['Used_Percentage'])
            temp_dict['name']  = each_disk['Name']
            temp_dict['dused'] = float(each_disk['Used_KB']) / 1024
            temp_dict['dfree'] = (float(each_disk['Size_KB']) - float(each_disk['Used_KB'])) / 1024
            totalSpace = float(each_disk['Size_KB']) / 1024
            usedSpace = float(each_disk['Used_KB']) / 1024
            totalDisk += totalSpace
            totalUsedDisk += usedSpace
            list_of_disks.append(temp_dict)
        dictData.setdefault('disk',list_of_disks)
        try:
            diskUsedPercent = int(round(((totalUsedDisk/totalDisk)*100),0))
        except ZeroDivisionError as e:
            diskUsedPercent = defaultDiskPer
        diskFreePercent = 100 - diskUsedPercent
        dictData['dfper'] = str(diskFreePercent)
        dictData['duper'] = str(diskUsedPercent)
    except Exception as e:
        AgentLogger.log(AgentLogger.COLLECTOR,'exception occurred while fetching disk stats')
        traceback.print_exc() 
        
        
def get_asset_info(dictData):
    try:
        operating_system = platform.system()
        if operating_system:
            dictData['asset']['os'] = operating_system
        
        os_architecture = platform.architecture()
        if os_architecture:
            dictData['asset']['arch'] = os_architecture[0]
        
        processor_name = platform.processor()
        if processor_name:
            dictData['asset']['cpu'] = processor_name
        
        if AgentConstants.PSUTIL_OBJECT:
            login_count = AgentConstants.PSUTIL_OBJECT.users()
            if login_count:
                dictData['systemstats']['lc'] = len(login_count)
            
            process_running = psutil.pids()
            if process_running:
                dictData['systemstats']['totp'] = len(process_running)
            
            cpu_core_count = AgentConstants.PSUTIL_OBJECT.cpu_count()
            if cpu_core_count:
                dictData['asset']['core'] = cpu_core_count
                
            boot_time = AgentConstants.PSUTIL_OBJECT.boot_time()
            current_time = time.time()
            uptime = int(current_time-boot_time)*(1000)
            uptime = AgentUtil.timeConversion(uptime)
            
            dictData['systemstats']['utt'] = uptime
    except Exception as e:
        AgentLogger.log(AgentLogger.COLLECTOR,'exception occurred while fetching asset data')
        traceback.print_exc()
        
        
def get_memory_info(dictData):
    try:
        virtual_memory = psutil.virtual_memory()
        if virtual_memory:
            dictData['memory']['tvirm'] = virtual_memory.total/1024/1024
            dictData['memory']['fvirm'] = virtual_memory.free/1024/1024
            dictData['memory']['uvirm'] = virtual_memory.used/1024/1024
            dictData['asset']['ram']=virtual_memory.total/1024/1024
            dictData['mper'] = virtual_memory.percent
        swap_memory = psutil.swap_memory()
        if swap_memory:
            dictData['memory']['swpmemper']=swap_memory.percent
            dictData['memory']['fvism'] = swap_memory.free /1024/1024
            dictData['memory']['tvism'] = swap_memory.total/1024/1024
            dictData['memory']['uvism'] = swap_memory.used/1024/1024
    except Exception as e:
        AgentLogger.log(AgentLogger.COLLECTOR,'exception occurred while fetching memory info')
        traceback.print_exc()
        
        
def get_cpu_core_info(dictData):
    try:
        list_of_cpu_cores=[]
        cpu_core_load_percentage = psutil.cpu_percent(interval=1,percpu=True)
        for count,elem in enumerate(cpu_core_load_percentage):
            temp_dict = {}
            temp_dict['core'] = count
            temp_dict['load'] = elem
            list_of_cpu_cores.append(temp_dict)
        dictData.setdefault('cpu',list_of_cpu_cores)
    except Exception as e:
        AgentLogger.log(AgentLogger.COLLECTOR,'exception occurred while fetching cpu core info')
        traceback.print_exc()
        
def get_load_average(dictData):
    try:
        executorObj = AgentUtil.Executor()
        executorObj.setLogger(AgentLogger.COLLECTOR)
        executorObj.setTimeout(30)
        executorObj.setCommand('uptime')
        executorObj.executeCommand()
        retVal    = executorObj.getReturnCode()
        stdOutput = executorObj.getStdOut()
        stdErr    = executorObj.getStdErr()
        AgentLogger.log(AgentLogger.COLLECTOR,' uptime command output -- {0}'.format(stdOutput))
        if stdOutput:
            stdOutput = stdOutput.split(',')
            if len(stdOutput) > 3 and 'load average:' in stdOutput[3]:
                dictData['systemstats']['1min']  = stdOutput[3].strip('load average:')
                dictData['systemstats']['5min']  = stdOutput[4].strip()
                dictData['systemstats']['15min'] = stdOutput[5].strip()
            days = int(stdOutput[0].split()[2])
            hrs = int(stdOutput[1].split(':')[0])
            mins = int(stdOutput[1].split(':')[1])
            uptime_secs = (days * 86400) + (hrs*3600) + (mins*60)
            dictData['systemstats']['uttsec'] = str(uptime_secs)
            dictData['systemstats']['utt'] = AgentUtil.timeConversion(uptime_secs * 1000)
    except Exception as e:
        AgentLogger.log(AgentLogger.COLLECTOR,'exception occurred while fetching load average and uptime ')
        traceback.print_exc()

'''
TODO / ADD if necessary
commented psutil method of collecting process data
removed psutil method of collecting process cpu utilization
'''        
def get_process_metrics(dictData):
    try:
        process_data = {}
        process_list = []
        process_dict = {}
        listProcesses=[]
        process_dc_command = None
        if AgentConstants.PROCESS_MONITORING_NAMES:
            process_list=AgentConstants.PROCESS_MONITORING_NAMES.split('|')
            process_command = "'{}'".format(AgentConstants.PROCESS_MONITORING_NAMES)
            if AgentConstants.OS_NAME == AgentConstants.SUN_OS:
                process_dc_command = AgentConstants.SUNOS_PROCESS_COMMAND+" "+"|"+" "+"/usr/xpg4/bin/grep -E "+process_command
            else:
                process_dc_command = AgentConstants.AIX_PROCESS_COMMAND+" "+"|"+" "+"grep -E "+process_command
            process_dict = com.manageengine.monagent.collector.DataCollector.ProcessUtil.get_aix_process_data(process_dc_command)
            AgentLogger.debug(AgentLogger.COLLECTOR,' process data :: {}'.format(json.dumps(process_dict)))
        #process_dict = com.manageengine.monagent.collector.DataCollector.ProcessUtil.get_processes_using_psutil(process_list)
        if process_dict:
            list_of_process = process_dict['PROCESS_LOG_DATA']
            ACTIVE_PROCESS_DICT = com.manageengine.monagent.collector.DataConsolidator.ACTIVE_PROCESS_DICT
            for processid in ACTIVE_PROCESS_DICT.keys():
                process_config = ACTIVE_PROCESS_DICT[processid]
                process_name = process_config['pn']
                process_args = process_config['args']
                process_not_found = True
                temp_dict={}
                for each in list_of_process:
                    pname = each['Name']
                    pargs = each['CommandLine']
                    if process_name == pname:
                        if process_args == pargs:
                            process_not_found = False
                            if temp_dict:
                                temp_dict['instance'] = 1+temp_dict['instance']
                            else:
                                temp_dict['instance'] = 1
                            temp_dict['status'] = 1
                            temp_dict['id'] = processid
                            temp_dict['name'] = pname
                            temp_dict['args'] = pargs
                            temp_dict['cpu'] = each['CPU_UTILIZATION']
                            temp_dict['thread'] = each['ThreadCount']
                            temp_dict['handle'] = each['HandleCount']
                            temp_dict['memory'] = each['MEMORY_UTILIZATION']
                            PID=each['ProcessId']
                            temp_dict['pid'] = PID
                            if AgentConstants.NO_OF_CPU_CORES:
                                temp_dict['cpu'] = float(temp_dict['cpu']) / AgentConstants.NO_OF_CPU_CORES
                            process_data.setdefault(processid,temp_dict)
                if process_not_found:
                   temp_dict={}
                   temp_dict['status'] = 0
                   temp_dict['id']   =  processid
                   temp_dict['args'] =  process_args
                   process_data.setdefault(processid,temp_dict)
        for key in process_data:
            listProcesses.append(process_data[key])
        dictData.setdefault('process',listProcesses)
    except Exception as e:
        AgentLogger.log(AgentLogger.COLLECTOR,'exception occurred while fetching process metrics')
        traceback.print_exc()
    return listProcesses
        
def get_network_data(dictData,dictConfig):
    try:
        executorObj = AgentUtil.Executor()
        executorObj.setLogger(AgentLogger.COLLECTOR)
        executorObj.setTimeout(30)
        executorObj.setCommand('netstat -i')
        executorObj.executeCommand()
        retVal    = executorObj.getReturnCode()
        stdOutput = executorObj.getStdOut()
        stdErr    = executorObj.getStdErr()
        AgentLogger.log(AgentLogger.COLLECTOR,' netstat command output -- {0} \n'.format(stdOutput))
        network_interfaces_dict = {}
        mac_address=None
        if stdOutput:
            ifconfig_list = stdOutput.splitlines()
            for line in ifconfig_list:
                if 'link' in line:
                    nic_info = line.split()
                    nic_name = nic_info[0]
                    mac_address = nic_info[3]
                    if nic_name=='lo0':
                        mac_address='127.0.0.1'
                    network_interfaces_dict[mac_address]={}
                    if '*' in nic_name:
                        network_interfaces_dict[mac_address]['status'] = 0
                    nic_name = nic_name.strip('*')
                    network_interfaces_dict[mac_address]['nic_name'] = nic_name
        AgentLogger.log(AgentLogger.COLLECTOR,' network interfaces dict -- {0}'.format(json.dumps(network_interfaces_dict)))
        dictNicData={}
        listNics = []
        network_stats = psutil.net_io_counters(pernic=True)
        if network_stats:
            nic_config_dict = dictConfig['NICS']
            if nic_config_dict:
                for mac_address in nic_config_dict:
                    interface_name = network_interfaces_dict[mac_address]['nic_name']
                    if interface_name in network_stats:
                        temp_dict = get_network_json(network_stats,interface_name,nic_config_dict,mac_address,network_interfaces_dict)
                        dictNicData.setdefault(mac_address,temp_dict)
            else:
                for mac_address in network_interfaces_dict:
                    interface_name = network_interfaces_dict[mac_address]['nic_name']
                    temp_dict = get_network_json(network_stats,interface_name,nic_config_dict,mac_address,network_interfaces_dict)
                    dictNicData.setdefault(mac_address,temp_dict)
        for (Macaddr,dictNic) in dictNicData.items():
            listNics.append(dictNic)
        dictData.setdefault('network',listNics)
    except Exception as e:
        AgentLogger.log(AgentLogger.COLLECTOR,'exception occurred while fetching network data')
        traceback.print_exc()