# $Id$
import math
import json
import traceback

#s24x7 packages
from com.manageengine.monagent.framework.suite.helper import get_value_from_dict
from . import container_constants
from com.manageengine.monagent.logger import AgentLogger

def join_port_data(data, key, data_dict):
    data_dict["portBind"] = '' if not "portBind" in data_dict else data_dict["portBind"] 
    if type(data) is dict:
        key_list = list(data.keys())
        new_string = ",".join(key_list)
        new_string = new_string if new_string.strip() else "-"
        data_dict['portBind'] = data_dict['portBind'] + key + " : "+ new_string+";"
    else:
        data_dict['portBind'] = data_dict['portBind'] + key + " : -;"
    
def modify_port_bindings_data(data_dict):
    try:
        if data_dict['PortBindings']:
            result_string = ''
            new_port_bind_list = []
            for each_port, bind_details in data_dict["PortBindings"].items():
                new_bind_details = str(bind_details).replace("{", "(")
                new_bind_details = new_bind_details.replace("}", ")")
                new_port_bind_list.append(each_port+"-"+new_bind_details)
            result_string = ','.join(new_port_bind_list)
            data_dict['portBind'] = data_dict['portBind'] + "Bindings : "+result_string+";"
        else:
            data_dict['portBind'] = data_dict['portBind'] + "Bindings : -"+";"
        del data_dict['PortBindings']
    except Exception as e:
        AgentLogger.log(AgentLogger.APPS, "Exception in portbind collection {}".format(e))
        if "PortBindings" in data_dict: del data_dict['PortBindings']
        data_dict['portBind'] = "-"

def modify_volumes_data(data_dict):
    try:
        if data_dict['Volumes']:
            stringList = []
            for key in data_dict['Volumes']:
                mode = key["Mode"]
                if not mode :  mode = "rw"
                string = "Source -" + key["Source"] + ", Destination - " + key["Destination"] + ", Mode - " + mode + ", RW - "+str(key["RW"]) 
                stringList.append(string)
            myString = ";".join(stringList)
            data_dict['volumeBind'] = myString
        else:
            data_dict['volumeBind'] = '-'
        del data_dict['Volumes']
    except Exception as e:
        AgentLogger.log(AgentLogger.APPS, "Exception in volume collection {}".format(e))
        if "Volumes" in data_dict: del data_dict['Volumes']
        data_dict['volumeBind'] = '-'

def parse_port_data(data_dict):
    if data_dict:
        join_port_data(data_dict["Ports"], "Ports", data_dict)
        join_port_data(data_dict["ExposedPorts"], "Exposed Ports", data_dict)
        del data_dict['Ports']
        del data_dict['ExposedPorts']
        modify_port_bindings_data(data_dict)
        modify_volumes_data(data_dict)

def calculate_io_metrics(data_dict):
    total_read, total_write, total_sum = 0.0, 0.0, 0.0
    blk_io_perf_dict = data_dict["BlkioPerf"]
    for each_io,value in blk_io_perf_dict.items():
        if each_io != 'io_queue_recursive' and blk_io_perf_dict.get(each_io):
            for each_op in blk_io_perf_dict[each_io]:
                if each_op['op'] == 'Read' or each_op['op'] == 'read':
                    total_read = total_read + float(each_op['value']/1048576)
                elif each_op['op'] == 'Write' or each_op['op'] == 'write':
                    total_write = total_write + float(each_op['value']/1048576)
                elif each_op['op'] == 'Total' or each_op['op'] == 'total':
                    total_sum = total_sum + float(each_op['value']/1048576)

    data_dict['IORead'] = total_read
    data_dict['IOWrite'] = total_write
    data_dict['IOTotal'] = total_sum
    data_dict.pop("BlkioPerf", None)

def calculate_cpu_percent(prev_total_usage, prev_system_cpu_usage, cpu_stats):
    cpu_percent = 0.0
    try:
        AgentLogger.debug(AgentLogger.APPS,' current usage -- {} {}'.format(cpu_stats["cpu_usage"]["total_usage"],cpu_stats["system_cpu_usage"]))
        AgentLogger.debug(AgentLogger.APPS,' previous usage -- {} {}'.format(prev_total_usage,prev_system_cpu_usage))
        if prev_total_usage is None or prev_total_usage == '-':
            prev_total_usage = 0
        if prev_system_cpu_usage is None or prev_system_cpu_usage == '-':
            prev_system_cpu_usage = 0
        if "cpu_usage" in cpu_stats and "system_cpu_usage" in cpu_stats and "total_usage" in cpu_stats["cpu_usage"]:
            #calculate the change for the cpu usage of the container in between readings
            cpu_count = len(cpu_stats["cpu_usage"]["percpu_usage"]) if "percpu_usage" in cpu_stats["cpu_usage"] else (cpu_stats["online_cpus"] if "online_cpus" in cpu_stats else 0)
            cpu_delta = float(cpu_stats["cpu_usage"]["total_usage"]) - float(prev_total_usage)
            #calculate the change for the entire system between readings
            system_delta = float(cpu_stats["system_cpu_usage"]) - float(prev_system_cpu_usage)
            if system_delta > 0.0 and cpu_delta > 0.0 :
                cpu_percent = (cpu_delta / system_delta) * cpu_count * 100.0
                # cpu_percent = (cpu_delta / system_delta) * 100
                cpu_percent = '{:.2f}'.format(cpu_percent)
    except Exception as e:
        traceback.print_exc()
        AgentLogger.log(AgentLogger.APPS, "exception while calculating cpu percentage -- {0}".format(e))
    finally:
        cpu_stats["cpu_percent"] = cpu_percent

def calculate_cpu_metrics(data_dict, cont_id, prev_data):
    try:
        calculate_cpu_percent(get_value_from_dict(prev_data, cont_id+".total_usage")[1], get_value_from_dict(prev_data, cont_id+".system_cpu_usage")[1],
                              data_dict["CpuPerf"])
        if not cont_id in prev_data:
            prev_data[cont_id] = {}
        prev_data[cont_id]["total_usage"] = data_dict["CpuPerf"]["cpu_usage"]["total_usage"]
        prev_data[cont_id]["system_cpu_usage"] = data_dict["CpuPerf"]["system_cpu_usage"]
        prev_data[cont_id]["flag"] = True
    except Exception as e:
        AgentLogger.log(AgentLogger.APPS, "exception while calculating cpu metrics -- {0}".format(e))
        traceback.print_exc()

def calculate_mem_percentage(data_dict):
    data_dict_memory = data_dict['MemoryPerf']
    mem_percent = 0.0
    try :
        if "usage" in data_dict_memory and "limit" in data_dict_memory:
            mem_percent = (data_dict_memory["usage"] / data_dict_memory["limit"] ) * 100
    except Exception as e:
        print(e)
    data_dict["memory_percent"] = round(mem_percent,2)
    data_dict["Memory"] = round(data_dict_memory["usage"]  / ( 1024 * 1024 ),2)

def update_mem_stats(mem_perf_dict):
    if "stats" in mem_perf_dict:
        stats = mem_perf_dict["stats"]
        if "active_anon" in stats:
            stats["active_anon"] = str(stats["active_anon"] / 1048576)
        if "inactive_anon" in stats:
            stats["inactive_anon"] = str(stats["inactive_anon"] / 1048576)
        if "active_file" in stats:
            stats["active_file"] = str(stats["active_file"] / 1048576)
        if "inactive_file" in stats:
            stats["inactive_file"] = str(stats["inactive_file"] / 1048576)
        if "cache" in stats:
            stats["cache"] = str(stats["cache"] / 1048576)
        if "rss" in stats:
            stats["rss"] = str(stats["rss"] / 1048576)
        if "unevictable" in stats:
            stats["unevictable"] = str(stats["unevictable"] / 1048576)
    
def calculate_mem_metrics(data_dict, cont_id, prev_data):
    update_mem_stats(data_dict["MemoryPerf"])
    calculate_mem_percentage(data_dict)

def calculate_network_metrics(data_dict, cont_id, prev_data):
    network_stats = {}
    network_stats["rx_bytes_num"] = 0
    network_stats["tx_bytes_num"] = 0
    try:
        for net, net_val in data_dict["NetworkPerf"].items():
            if "rx_bytes" in net_val:
                network_stats["rx_bytes_num"] = network_stats["rx_bytes_num"] + net_val["rx_bytes"]
            if "tx_bytes" in net_val:
                network_stats["tx_bytes_num"] = network_stats["tx_bytes_num"] + net_val['tx_bytes']
        if "rx_bytes_num" in network_stats and "tx_bytes_num" in network_stats :
            network_stats["traffic"] = str((network_stats["rx_bytes_num"] + network_stats["tx_bytes_num"])/1024)
        network_stats["rx_bytes"] = str(network_stats["rx_bytes_num"]/1024)
        network_stats["tx_bytes"] = str(network_stats["tx_bytes_num"]/1024)
    except Exception as e:
        traceback.print_exc()
    data_dict["NetworkPerf"] = network_stats


def parse_data(result_data_dict, metrics_list, child_data_dict): 
    for metric in metrics_list:
        if metric in child_data_dict:
            result_data_dict[metric] = child_data_dict[metric]

def delete_all_extra_perf_metrics(data_dict):
    for perf_metric in container_constants.PERF_METRICS:
        data_dict.pop(perf_metric, None)
    
def collect_metrics(data_dict, cont_id, prev_data):
    calculate_io_metrics(data_dict)
    calculate_cpu_metrics(data_dict, cont_id, prev_data)
    calculate_mem_metrics(data_dict, cont_id, prev_data)
    calculate_network_metrics(data_dict, cont_id, prev_data)
    parse_data(data_dict, container_constants.NET_PERF_METRICS, data_dict["NetworkPerf"])
    parse_data(data_dict, container_constants.CPU_PERF_METRICS, data_dict["CpuPerf"])
    if 'stats' in data_dict['MemoryPerf']:
        parse_data(data_dict, container_constants.MEM_PERF_METRICS, data_dict["MemoryPerf"]["stats"])
    delete_all_extra_perf_metrics(data_dict)