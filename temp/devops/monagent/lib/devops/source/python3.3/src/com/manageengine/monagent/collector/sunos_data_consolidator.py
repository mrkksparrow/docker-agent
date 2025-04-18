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

def get_sunos_cpu(dictData, dictKeyData, dictConfig):
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
        get_cpu_core_load(dictData)
    except Exception as e:
        AgentLogger.log(AgentLogger.COLLECTOR,'exception occurred while fetching cpu metrics')
        traceback.print_exc()

def get_cpu_core_load(dictData):
    cpu_cores_list=[]
    try:
        executorObj = AgentUtil.Executor()
        executorObj.setLogger(AgentLogger.COLLECTOR)
        executorObj.setTimeout(30)
        executorObj.setCommand(AgentConstants.SUN_OS_CPU_CORE_COMMAND)
        executorObj.executeCommand()
        retVal    = executorObj.getReturnCode()
        stdOutput = executorObj.getStdOut()
        stdErr    = executorObj.getStdErr()
        AgentLogger.log(AgentLogger.COLLECTOR,' cpu core command -- {0}'.format(stdOutput))
        if stdOutput:
            lines=stdOutput.split('\n')
            for each in lines:
                if 'CPU' in each:
                    continue
                split_each_line = each.split()
                if split_each_line:
                    temp_dict = {}
                    temp_dict['core'] = split_each_line[0]
                    temp_dict['load'] = 100-int(split_each_line[15])
                    cpu_cores_list.append(temp_dict)
        dictData.setdefault('cpu',cpu_cores_list)
    except Exception as e:
        AgentLogger.log(AgentLogger.COLLECTOR,'exception occurred while fetching cpu core ')
        traceback.print_exc()

def get_sunos_mem(dictData, dictKeyData, dictConfig):
    try:
        memory_data = dictKeyData['Memory_Utilization'][0]
        if 'tvirm' in memory_data:
            dictData['memory']['tvirm'] = int(float(memory_data['tvirm']))
        if 'fvirm' in memory_data:
            dictData['memory']['fvirm'] = int(float(memory_data['fvirm'])/1024)
        dictData['memory']['uvirm'] = dictData['memory']['tvirm'] - dictData['memory']['fvirm']
        if 'tvism' in memory_data:
            dictData['memory']['tvism'] = int(float(memory_data['tvism'])/1024)
        if 'uvism' in memory_data:
            dictData['memory']['uvism'] = int(float(memory_data['uvism'])/1024)
        if 'pin' in dictData:
            dictData['memory']['pin'] = dictData['pin']
        if 'pout' in dictData:
            dictData['memory']['pout'] = dictData['pout']
        dictData['asset']['ram'] = int(float(dictData['memory']['tvirm']))
        mem_used_percent = round((((float(dictData['memory']['tvirm']) - float(dictData['memory']['fvirm']))/float(dictData['memory']['tvirm']))*100),2)
        dictData['mper'] = str(mem_used_percent)
        dictData['memory']['fvism']=float(dictData['memory']['tvism'])-float(dictData['memory']['uvism'])
        swapmem_used_percent = round((((float(dictData['memory']['tvism']) - float(dictData['memory']['fvism']))/float(dictData['memory']['tvism']))*100),2)
        dictData['memory']['swpmper'] = str(swapmem_used_percent)
        if AgentConstants.IOSTAT_UTILITY_PRESENT:
            dictData['dbusy'], dictData['didle'], dictData['readops'], dictData['readops'], dictData['aql'] = AgentUtil.metrics_from_iostat()
    except Exception as e:
        AgentLogger.log(AgentLogger.COLLECTOR,'exception occurred while fetching memory metrics')
        traceback.print_exc()
                   
def get_sunos_disk(dictData , dictKeyData , dictConfig):
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
            totalSpace = round(float(each_disk['Size_KB']) / 1024)
            usedSpace = round(float(each_disk['Used_KB']) / 1024)
            temp_dict['duper'] = each_disk['Used_Percentage']
            temp_dict['dfper'] = 100 - int(each_disk['Used_Percentage'])
            temp_dict['name']  = each_disk['Name']
            temp_dict['file_system'] = each_disk['FileSystem']
            temp_dict['dtotal'] = totalSpace
            temp_dict['dused'] = usedSpace
            temp_dict['dfree'] = totalSpace - usedSpace
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