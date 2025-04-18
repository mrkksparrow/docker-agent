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
from com.manageengine.monagent.collector import DataConsolidator
from com.manageengine.monagent.scheduler import AgentScheduler
from com.manageengine.monagent.util.AgentUtil import ZipUtil,FileZipAndUploadInfo,AgentBuffer
from com.manageengine.monagent.collector import server_inventory

COUNTER_DICT={}
PARAM_VS_PSUTIL_KEY={'bytesrcv':'bytes_recv','bytessent':'bytes_sent','pktsent':'packets_sent','pktrcv':'packets_recv','errorpkts':'errout','ctxtsw':'ctx_switches','interrupts':'interrupts','dwrites':'write_bytes','dreads':'read_bytes'}
    
def schedule_dc():
    try:
        interval=int(AgentConstants.POLL_INTERVAL)
        task=collect_metrics
        taskName='ps_util_metric_collector'
        callback=data_save
        scheduleInfo=AgentScheduler.ScheduleInfo()
        scheduleInfo.setIsPeriodic(True)
        scheduleInfo.setSchedulerName('AgentScheduler')
        scheduleInfo.setTaskName(taskName)
        scheduleInfo.setTime(time.time())
        scheduleInfo.setTask(task)
        scheduleInfo.setCallback(callback)
        scheduleInfo.setInterval(interval)
        scheduleInfo.setLogger(AgentLogger.COLLECTOR)
        AgentScheduler.schedule(scheduleInfo)
    except Exception as e:
        traceback.print_exc()
        AgentLogger.log(AgentLogger.COLLECTOR, 'Error in scheduling ps util metric collector '+str(e)+'\n')

def un_schedule_dc():
    try:
        scheduleInfo = AgentScheduler.ScheduleInfo()
        scheduleInfo.setSchedulerName('AgentScheduler')
        scheduleInfo.setTaskName('ps_util_metric_collector')
        AgentScheduler.deleteSchedule(scheduleInfo)
    except Exception as e:
        traceback.print_exc()
        
def reinit_monitoring():
    try:
        un_schedule_dc()
        schedule_dc()
    except Exception as e:
        traceback.print_exc()

def data_save(server_metrics):
    try:
        bool_isSuccess, str_fileName = com.manageengine.monagent.collector.DataCollector.saveCollectedServerData(server_metrics, AgentConstants.AGENT_UPLOAD_PROPERTIES_MAPPER['001'], "SMData")
    except Exception as e:
        AgentLogger.log([AgentLogger.CRITICAL,AgentLogger.STDERR], '*************************** Exception while saving server collected data in Data dir *************************** '+ repr(e))
        traceback.print_exc()

def collect_metrics():
    server_metrics = {}
    try:
        get_asset_info(server_metrics)
        get_memory_info(server_metrics)
        get_cpu_core_info(server_metrics)
        get_process_metrics(server_metrics)
        get_load_average(server_metrics)
        get_network_command_data(server_metrics)
        get_cpu_stats(server_metrics)
        get_cpu_perf_metrics(server_metrics)
        get_top_process_data(server_metrics)
        get_disk_io(server_metrics)
        get_disk_utilization(server_metrics)
        get_page_info(server_metrics)
        server_inventory.inventory_data_collector()
    except Exception as e:
        AgentLogger.log(AgentLogger.COLLECTOR,'exception occurred in collect metrics')
        traceback.print_exc()
    finally:
        return server_metrics

def get_disk_io(server_metrics):
    try:
        disk_io=AgentConstants.PSUTIL_OBJECT.disk_io_counters()
        server_metrics['dreads'] = get_ps_util_counter_value('dreads',disk_io)
        server_metrics['dwrites'] = get_ps_util_counter_value('dwrites',disk_io)
        server_metrics['diskio'] = int(server_metrics['dreads'])+int(server_metrics['dwrites'])
    except Exception as e:
        AgentLogger.log([AgentLogger.COLLECTOR,AgentLogger.STDERR], '*************************** Exception while calculating consolidated values for Disk IO *********************************')
        traceback.print_exc()

def get_disk_utilization(server_metrics):
    try:
        totalDisk = 0
        totalUsedDisk = 0
        CONFIG_OBJECT = com.manageengine.monagent.collector.DataConsolidator.CONFIG_OBJECTS
        server_metrics['disk']=[]
        disk_parts = AgentConstants.PSUTIL_OBJECT.disk_partitions()
        for each_disk in disk_parts:
            each_disk_data = {}
            each_disk_data['name'] = each_disk.mountpoint
            each_disk_data['filesystem'] = each_disk.fstype
            each_disk_data['file_system'] = each_disk.device
            disk_usage = AgentConstants.PSUTIL_OBJECT.disk_usage(each_disk.mountpoint)
            if CONFIG_OBJECT and'DISKS' in CONFIG_OBJECT and each_disk_data['name'] in CONFIG_OBJECT['DISKS']:
                each_disk_data['id'] = CONFIG_OBJECT['DISKS'][each_disk_data['name']]
            else:
                each_disk_data['id'] = "None"
            each_disk_data['duper'] = disk_usage.percent
            total_space = disk_usage.total / ( 1024 * 1024 )
            free_space = disk_usage.free / ( 1024 * 1024 )
            used_space = total_space - free_space
            free_space_percent = int(round(((free_space/total_space)*100),0))
            each_disk_data['dfper'] = round(free_space_percent)
            each_disk_data['dused'] = round(used_space)
            each_disk_data['dtotal'] = round(total_space)
            each_disk_data['dfree'] = free_space
            totalDisk += total_space
            totalUsedDisk += used_space
            inode_stats = os.statvfs(each_disk.mountpoint)
            each_disk_data['inodes'] = inode_stats.f_files
            each_disk_data['ifree'] = inode_stats.f_ffree
            each_disk_data['iused'] = each_disk_data['inodes'] - each_disk_data['ifree']
            each_disk_data['iuper'] = int((each_disk_data['iused'] * 100.0) / each_disk_data['inodes'] )
            server_metrics['disk'].append(each_disk_data)
        diskUsedPercent = int(round(((totalUsedDisk/totalDisk)*100),0))
        diskFreePercent = 100 - diskUsedPercent
        server_metrics['dfper'] = str(diskFreePercent)
        server_metrics['duper'] = str(diskUsedPercent)
    except Exception as e:
        AgentLogger.log([AgentLogger.COLLECTOR,AgentLogger.STDERR], '*************************** Exception while calculating consolidated values for Disk utilization *********************************')
        traceback.print_exc()

def get_top_process_data(server_metrics):
    try:
        AgentUtil.get_top_process_data()
        top_process_data = AgentConstants.PS_UTIL_PROCESS_DICT
        if top_process_data:
            server_metrics['TOPMEMORYPROCESS'] = top_process_data['TOPMEMORYPROCESS']
            server_metrics['TOPCPUPROCESS'] = top_process_data['TOPCPUPROCESS']
            server_metrics['fd'] = top_process_data['fd']
    except Exception as e:
        AgentLogger.log([AgentLogger.COLLECTOR,AgentLogger.STDERR],'Exception occurred in top process data')
        traceback.print_exc()

def get_cpu_perf_metrics(server_metrics):
    try:
        import psutil
        cpu = psutil.cpu_times_percent(interval=2)
        idle_time=cpu.idle
        if AgentConstants.OS_NAME in [AgentConstants.FREEBSD_OS,AgentConstants.OS_X]:
            server_metrics['cper']=eval(AgentConstants.CPU_FORMULA)
            return
        wait_time=cpu.iowait
        steal_time=cpu.steal
        #kernel version 4.9 bug results in negative steal time
        if steal_time < 0:
            steal_time = 0
            AgentLogger.log(AgentLogger.COLLECTOR,'found negative steal time so setting it to 0 \n')
            AgentLogger.log(AgentLogger.COLLECTOR,'value obtained - {0}'.format(cpu.steal)+'\n')
        server_metrics['id']=idle_time
        server_metrics['wa']=wait_time
        server_metrics['us']=cpu.user
        server_metrics['sy']=cpu.system
        server_metrics['st']=steal_time
        server_metrics['si']=cpu.softirq
        server_metrics['hi']=cpu.irq
        server_metrics['cper']=eval(AgentConstants.CPU_FORMULA)
    except Exception as e:
        AgentLogger.log([AgentLogger.COLLECTOR,AgentLogger.STDERR], '*************************** Exception while setting consolidated values for ps util stats *********************************')
        traceback.print_exc()

def get_cpu_stats(server_metrics):
    try:
        cpu_stats = AgentConstants.PSUTIL_OBJECT.cpu_stats()
        if cpu_stats:
            server_metrics['ctxtsw'] = get_ps_util_counter_value('ctxtsw',cpu_stats)
            server_metrics['interrupts'] = get_ps_util_counter_value('interrupts',cpu_stats)
    except Exception as e:
        AgentLogger.log([AgentLogger.COLLECTOR,AgentLogger.STDERR], '*************************** Exception while fetching interrupts and context switches *********************************')
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
            temp_dict['bytesrcv'] = get_ps_util_counter_value(interface_name+'_bytesrcv',interface_stats)
            temp_dict['bytessent'] = get_ps_util_counter_value(interface_name+'_bytessent',interface_stats)
            temp_dict['bytesrcvkb'] = (int(temp_dict['bytesrcv'])/1024)
            temp_dict['bytessentkb'] = (int(temp_dict['bytessent'])/1024)
            temp_dict['totbyteskb'] = temp_dict['bytesrcvkb'] +  temp_dict['bytessentkb']
            temp_dict['errorpkts'] = get_ps_util_counter_value(interface_name+'_errorpkts',interface_stats)
            temp_dict['pktrcv'] = get_ps_util_counter_value(interface_name+'_pktrcv',interface_stats)
            temp_dict['pktsent'] = get_ps_util_counter_value(interface_name+'_pktsent',interface_stats)
            temp_dict['status']=1
    except Exception as e:
        AgentLogger.log([AgentLogger.COLLECTOR,AgentLogger.STDERR], '*************************** Exception occurred while fetching network json *********************************')
        traceback.print_exc()
    return temp_dict
   
def get_ps_util_counter_value(param,data_obj):
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
        AgentLogger.log([AgentLogger.COLLECTOR,AgentLogger.STDERR], '*************************** Exception occurred in counter values block for param -- {0} *********************************'.format(param))
        traceback.print_exc()
    return round(return_value,2)

def get_counter_value(param,current_value):
    global COUNTER_DICT
    return_value = 0
    try:
        if param in COUNTER_DICT: 
           return_value = ( float(current_value) - float(COUNTER_DICT[param]) ) / int(AgentConstants.POLL_INTERVAL)
        else:
            return_value = 0
            COUNTER_DICT[param] = current_value
    except Exception as e:
        AgentLogger.log([AgentLogger.COLLECTOR,AgentLogger.STDERR], '*************************** Exception occurred in counter values block for param -- {0} *********************************'.format(param))
        traceback.print_exc()
    return round(return_value,2)
        
def get_asset_info(server_metrics):
    try:
        server_metrics['asset']={}
        server_metrics['systemstats'] = {}
        operating_system = platform.platform(terse=1)
        if operating_system:
            server_metrics['asset']['os'] = operating_system
        os_architecture = platform.architecture()
        if os_architecture:
            server_metrics['asset']['arch'] = os_architecture[0]
        processor_name = platform.processor()
        if processor_name:
            server_metrics['asset']['cpu'] = processor_name
        server_metrics['asset']['hostname'] = AgentConstants.HOST_NAME
        server_metrics['asset']['pri_ip'] = AgentConstants.IP_ADDRESS
        #server_metrics['asset']['clock_delay'] = str(AgentUtil.offset_in_machine_clock()[1]) #in secs
        if AgentConstants.PSUTIL_OBJECT:
            login_count = AgentConstants.PSUTIL_OBJECT.users()
            if login_count:
                server_metrics['systemstats']['lc'] = len(login_count)
            process_running = AgentConstants.PSUTIL_OBJECT.pids()
            if process_running:
                server_metrics['systemstats']['totp'] = len(process_running)
            cpu_core_count = AgentConstants.PSUTIL_OBJECT.cpu_count()
            if cpu_core_count:
                server_metrics['asset']['core'] = cpu_core_count
            boot_time = AgentConstants.PSUTIL_OBJECT.boot_time()
            current_time = time.time()
            uptime = int(current_time-boot_time)
            server_metrics['systemstats']['uttsec'] = str(uptime)
            server_metrics['systemstats']['utt'] = AgentUtil.timeConversion(uptime*1000)
    except Exception as e:
        AgentLogger.log([AgentLogger.COLLECTOR,AgentLogger.STDERR], '*************************** Exception occurred while fetching asset data *********************************')
        traceback.print_exc()
        
def get_memory_info(server_metrics):
    try:
        server_metrics['memory'] = {}
        virtual_memory = AgentConstants.PSUTIL_OBJECT.virtual_memory()
        if virtual_memory:
            server_metrics['memory']['tvirm'] = round(virtual_memory.total/1024/1024)
            server_metrics['memory']['fvirm'] = round(virtual_memory.free/1024/1024)
            server_metrics['memory']['uvirm'] = round(virtual_memory.used/1024/1024)
            server_metrics['asset']['ram']=round(virtual_memory.total/1024/1024)
            server_metrics['mper'] = virtual_memory.percent
        swap_memory = AgentConstants.PSUTIL_OBJECT.swap_memory()
        if swap_memory:
            server_metrics['memory']['swpmemper']=swap_memory.percent
            server_metrics['memory']['fvism'] = round(swap_memory.free /1024/1024)
            server_metrics['memory']['tvism'] = round(swap_memory.total/1024/1024)
            server_metrics['memory']['uvism'] = round(swap_memory.used/1024/1024)
    except Exception as e:
        AgentLogger.log([AgentLogger.COLLECTOR,AgentLogger.STDERR], '*************************** Exception occurred while fetching memory info *********************************')
        traceback.print_exc()
        
        
def get_cpu_core_info(server_metrics):
    try:
        list_of_cpu_cores=[]
        cpu_core_load_percentage = AgentConstants.PSUTIL_OBJECT.cpu_percent(interval=1,percpu=True)
        for count,elem in enumerate(cpu_core_load_percentage):
            temp_dict = {}
            temp_dict['core'] = count
            temp_dict['load'] = elem
            list_of_cpu_cores.append(temp_dict)
        server_metrics.setdefault('cpu',list_of_cpu_cores)
    except Exception as e:
        AgentLogger.log([AgentLogger.COLLECTOR,AgentLogger.STDERR], '*************************** Exception occurred while fetching cpu core info *********************************')
        traceback.print_exc()
        
def get_load_average(server_metrics):
    try:
        load_values = os.getloadavg()
        if load_values:
            server_metrics['systemstats']['1min']  = round(load_values[0],2)
            server_metrics['systemstats']['5min']  = round(load_values[1],2)
            server_metrics['systemstats']['15min'] = round(load_values[2],2)
    except Exception as e:
        AgentLogger.log([AgentLogger.COLLECTOR,AgentLogger.STDERR], '*************************** Exception occurred while fetching load average *********************************')
        traceback.print_exc()

def get_process_metrics(server_metrics):
    try:
        process_data = {}
        process_list = []
        process_dict = {}
        process_dc_command = None
        if AgentConstants.PROCESS_MONITORING_NAMES:
            process_list=AgentConstants.PROCESS_MONITORING_NAMES.split('|')
            process_dict = com.manageengine.monagent.collector.DataCollector.ProcessUtil.get_processes_using_psutil(process_list)
        if process_dict:
            list_of_process = process_dict['PROCESS_LOG_DATA']
            ACTIVE_PROCESS_DICT = com.manageengine.monagent.collector.DataConsolidator.ACTIVE_PROCESS_DICT
            ebpf_process_data = com.manageengine.monagent.collector.DataConsolidator.fetch_ebpf_process_data()
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
                            temp_dict['priority'] = each['Priority']
                            temp_dict['uptime'] = each['uptime']
                            temp_dict['size'] = each['size']
                            PID = each['ProcessId']
                            temp_dict['pid'] = PID
                            if PID in ebpf_process_data:
                                temp_dict['tx'] = ebpf_process_data[PID]['tx']
                                temp_dict['rx'] = ebpf_process_data[PID]['rx']
                                temp_dict['rt'] = ebpf_process_data[PID]['rt']
                                AgentLogger.log(AgentLogger.CHECKS,"ebpf data found for process {}::{}".format(PID,pname))
                            if AgentConstants.NO_OF_CPU_CORES:
                                temp_dict['cpu']= float(temp_dict['cpu']) / float(AgentConstants.NO_OF_CPU_CORES)
                            process_data.setdefault(processid,temp_dict)
                if process_not_found:
                   temp_dict={}
                   temp_dict['status'] = 0
                   temp_dict['id']   =  processid
                   temp_dict['args'] =  process_args
                   process_data.setdefault(processid,temp_dict)
        listProcesses=[]
        for key in process_data:
            listProcesses.append(process_data[key])
        server_metrics.setdefault('process',listProcesses)
    except Exception as e:
        AgentLogger.log([AgentLogger.COLLECTOR,AgentLogger.STDERR], '*************************** Exception occurred while fetching process metrics *********************************')    
        traceback.print_exc()
    return listProcesses

def get_page_info(server_metrics):
    try:
        executorObj = AgentUtil.Executor()
        executorObj.setLogger(AgentLogger.COLLECTOR)
        executorObj.setTimeout(30)
        if AgentConstants.OS_NAME == AgentConstants.OS_X:
            executorObj.setCommand("vm_stat | grep 'Pageins\|Pageouts\|faults'")
        else:
            executorObj.setCommand('sysctl vm.stats.vm.v_swappgsin vm.stats.vm.v_swappgsout vm.stats.vm.v_io_faults')
        executorObj.executeCommand()
        retVal    = executorObj.getReturnCode()
        stdOutput = executorObj.getStdOut()
        stdErr    = executorObj.getStdErr()
        if stdOutput:
            page_metrics = stdOutput.splitlines()
            server_metrics['memory']['pin'] = get_counter_value('pin',page_metrics[0].split(':')[1])
            server_metrics['memory']['pout'] = get_counter_value('pout',page_metrics[1].split(':')[1])
            server_metrics['memory']['pfaults'] = get_counter_value('pfaults',page_metrics[2].split(':')[1])
    except Exception as e:
        AgentLogger.log([AgentLogger.COLLECTOR,AgentLogger.STDERR], '*************************** Exception occurred while fetching page info data *********************************')
        traceback.print_exc()

def get_network_command_data(server_metrics):
    Throughput = 0
    try:
        CONFIG_OBJECT = com.manageengine.monagent.collector.DataConsolidator.CONFIG_OBJECTS
        executorObj = AgentUtil.Executor()
        executorObj.setLogger(AgentLogger.COLLECTOR)
        executorObj.setTimeout(30)
        executorObj.setCommand('netstat -i')
        executorObj.executeCommand()
        retVal    = executorObj.getReturnCode()
        stdOutput = executorObj.getStdOut()
        stdErr    = executorObj.getStdErr()
        network_interfaces_dict = {}
        ipv4_list = []
        mac_address = None
        if stdOutput:
            ifconfig_list = stdOutput.splitlines()
            for line in ifconfig_list:
                if 'link' in line or 'Link' in line:
                    nic_info = line.split()
                    nic_name = nic_info[0]
                    mac_address = nic_info[3]
                    if  len(nic_info) < 9:
                        mac_address='00:00:00:00:00:00'
                    network_interfaces_dict[mac_address]={}
                    if '*' in nic_name:
                        network_interfaces_dict[mac_address]['status'] = 0
                    nic_name = nic_name.strip('*')
                    network_interfaces_dict[mac_address]['nic_name'] = nic_name
        dictNicData={}
        listNics = []
        network_stats = AgentConstants.PSUTIL_OBJECT.net_io_counters(pernic=True)
        if network_stats:
            nic_config_dict = CONFIG_OBJECT['NICS']
            if nic_config_dict:
                for mac_address in nic_config_dict:
                    if mac_address in network_interfaces_dict:
                        interface_name = network_interfaces_dict[mac_address]['nic_name']
                        if interface_name in network_stats:
                            temp_dict = get_network_json(network_stats,interface_name,nic_config_dict,mac_address,network_interfaces_dict)
                            Throughput += temp_dict.get('totbyteskb',0.0)
                            dictNicData.setdefault(mac_address,temp_dict)
            else:
                for mac_address in network_interfaces_dict:
                    interface_name = network_interfaces_dict[mac_address]['nic_name']
                    temp_dict = get_network_json(network_stats,interface_name,nic_config_dict,mac_address,network_interfaces_dict)
                    Throughput += temp_dict.get('totbyteskb',0.0)
                    dictNicData.setdefault(mac_address,temp_dict)
        server_metrics['throughput'] = str(round( Throughput, 2))
        for (Macaddr,dictNic) in dictNicData.items():
            listNics.append(dictNic)
            
        for nic,interface in enumerate(listNics):
            nicname=interface['name']
            executorObj.setCommand('ifconfig '+nicname)
            executorObj.executeCommand()
            executorObj.setTimeout(10)
            retVal    = executorObj.getReturnCode()
            Output = executorObj.getStdOut()
            stdErr    = executorObj.getStdErr()
            if Output:
                Output=Output.replace('\n\t',' ')
                Output=Output.split(" ")
                for word in range(len(Output)):
                    if Output[word]=="inet":
                        listNics[nic]['ipv4']=Output[word+1]
                    if Output[word]=="inet6":
                        listNics[nic]['ipv6']=Output[word+1].split("%")[0]
                    if Output[word]=="ether":
                        listNics[nic]['macadd']=Output[word+1]
                listNics[nic]['ipv4'] = "-" if "ipv4" not in listNics[nic].keys() else listNics[nic]['ipv4']
                listNics[nic]['ipv6'] = "-" if "ipv6" not in listNics[nic].keys() else listNics[nic]['ipv6']
                listNics[nic]['macadd'] = "00:00:00:00:00:00" if 'macadd' not in listNics[nic].keys() else listNics[nic]['macadd']
                if listNics[nic]['ipv4'] != "-":
                    ipv4_list.append(listNics[nic]['ipv4'])
            listNics[nic]['bandwidth'] = AgentUtil.get_nicspeed(nicname)     #speed is being sent as bandwidth
        server_metrics.setdefault('network',listNics)
        AgentConstants.NETWORKS_LIST = listNics
        AgentConstants.IP_LIST = ipv4_list
        server_metrics['asset']['ip']=', '.join(AgentConstants.IP_LIST)
    except Exception as e:
        AgentLogger.log(AgentLogger.COLLECTOR,'*************************** Exception while fetching network data *********************************')
        traceback.print_exc()
