#s24x7 packages
from com.manageengine.monagent.logger import AgentLogger
from com.manageengine.monagent import AgentConstants
import platform
import os

script_path = AgentConstants.DOCKER_SCRIPT_PATH
if platform.system() == AgentConstants.SUN_OS:
    script_path = os.path.join(AgentConstants.AGENT_SCRIPTS_DIR, "sunos_script.sh")

DA_SYSTEMUPTIME_COMMAND = "{} {}".format(script_path, "system_uptime")
DA_PROCESSORNAME_COMMAND = "{} {}".format(script_path, "processor")
DA_SYSTEMSTATS_COMMAND = "{} {}".format(script_path, "system_stats")
DA_MEMSTATS_COMMAND = "{} {}".format(script_path, "mem_stats")
DA_PROCESSQUEUE_COMMAND = "{} {}".format(script_path, "process_queue")
DA_NETWORK_DATA_COMMAND = "{} {}".format(script_path, "if_data")
DA_NETWORK_STATS_COMMAND = "{} {}".format(script_path, "if_traffic")
DA_DISK_COMMAND = "{} {}".format(script_path, "disk_details")

ENV_DICT = {"PROC_FOLDER":AgentConstants.PROCFS_PATH, "SYS_FOLDER":AgentConstants.SYSFS_PATH}

NEEDED_INSTANCE_ATTRS = {"result_dict":{}, "final_dict":{}, "metrics_list":{}}

#system.py
SYSTEM_PARENT_RESULT_DICT = {"Number Of Cores" : {"Number Of Cores":[{"NumberOfCores":"-"}], "ERRORMSG":"NO ERROR", "parseTag":"ASSET_IMPL"}, 
                             "OS Architecture" : {"OS Architecture":[{"OSArchitecture":"-"}], "ERRORMSG":"NO ERROR", "parseTag":"ASSET_IMPL"}, 
                             "System Uptime" : {"System Uptime":[{"Utime":"-", "IdleTime": "-"}], "ERRORMSG":"NO ERROR", "parseTag":"ASSET_IMPL"},
                             "System Stats" : {"System Stats":[{"Last 1 min Avg":"-", "Last 5 min Avg":"-", "Last 15 min Avg":"-", "Process Count":"-"}], "ERRORMSG":"NO ERROR", "parseTag":"SYSTEM_IMPL"},
                             "Process Queue" : {"Process Queue":[{"Procs Running":"-", "Procs Blocked":"-"}]}
                             } 

SYSTEM_PARENT_FINAL_DICT = {"systemstats" : {"1min":"System Stats.System Stats.0.Last 1 min Avg", "5min":"System Stats.System Stats.0.Last 5 min Avg", 
                                             "15min":"System Stats.System Stats.0.Last 15 min Avg", "cr":"System Stats.System Stats.0.Process Count", 
                                             "prun":"Process Queue.Process Queue.0.Procs Running", "pblck":"Process Queue.Process Queue.0.Procs Blocked",
                                             "bt" : "-", "it" : "-", "utt" : "-", "totp" : "-"}, 
                            "asset" : {"core" : "-", "cpu":"-", "instance":"-", "arch":"-", "ip":"-", "os":"-", "hostname":"-", "ram":"-"}}

#network.py
NETWORK_PARENT_RESULT_DICT = {"Network Data" : {"Network Data" : []},
                              "ERRORMSG":"NO ERROR", "parseTag":"NETWORK_IMPL"
                              }

NETWORK_PARENT_FINAL_DICT = {"network":[{"ipv4":"-", "ipv6":"-","totbyteskb":"Network Data.Network Data.{}.totbyteskb", "status":"Network Data.Network Data.{}.Status", "id" : "Network Data.Network Data.{}.id", "name": "Network Data.Network Data.{}.AdapterDesc", "macadd": "Network Data.Network Data.{}.MACAddress",
                                         "bytesrcv":"Network Data.Network Data.{}.BytesReceivedPersec", "bytessent":"Network Data.Network Data.{}.BytesSentPersec", "pktsent":"Network Data.Network Data.{}.PacketsSentUnicastPersec",
                                         "bytesrcvkb":"Network Data.Network Data.{}.bytesrcvkb", "bytessentkb":"Network Data.Network Data.{}.bytessentkb", "discardpkts":"Network Data.Network Data.{}.PacketsOutboundDiscarded",
                                          "errorpkts":"Network Data.Network Data.{}.PacketsOutboundErrors", "pktrcv":"Network Data.Network Data.{}.PacketsReceivedUnicastPersec", "iter":"Network Data.Network Data", "bandwidth":"100000000"}]}
#memory,py
MEMORY_PARENT_RESULT_DICT = {"Memory Utilization" : {"Memory Utilization" : [{"TotalVisibleMemorySize":"-", "FreePhysicalMemory":"-", "TotalVirtualMemorySize":"-", "FreeVirtualMemory":"-",
                                                                              "Caption":"-", "FreePhyPercent":"-", "FreeVirtPercent":"-"}], "parseTag":"MEMORY_IMPL,ASSET_IMPL", "ERRORMSG":"NO ERROR"},
                             "Memory Statistics" : {"Memory Statistics" : [{"PagesInputPersec" : "-", "PagesOutputPersec" : "-", "PageFaultsPersec" : "-"}],
                                                    "parseTag" : "MEMORY_IMPL", "ERRORMSG" : "NO ERROR"}}

MEMORY_PARENT_FINAL_DICT = {"memory" : {"tvism" : "Memory Utilization.Memory Utilization.0.TotalVisibleMemorySize", "fvism" : "Memory Utilization.Memory Utilization.0.FreePhysicalMemory",
                                        "tvirm" : "Memory Utilization.Memory Utilization.0.TotalVirtualMemorySize", "fvirm":"Memory Utilization.Memory Utilization.0.FreeVirtualMemory",
                                        "uvism" : "-", "uvirm":"-", "pfaults":"Memory Statistics.Memory Statistics.0.PageFaultsPersec", "pin":"Memory Statistics.Memory Statistics.0.PagesInputPersec",
                                         "pout" : "Memory Statistics.Memory Statistics.0.PagesOutputPersec"}}

#disk.py
DISK_PARENT_RESULT_DICT = {"Disk Statistics" : {"Disk Statistics" : [{"Name":"Disk I/O bytes", "DiskReadBytesPersec":"-", "DiskWriteBytesPersec":"-"}], 
                                                "ERRORMSG":"NO ERROR", "parseTag" : "ROOT_IMPL"},
                           "Disk Utilization" : {"Disk Utilization" : [], "ERRORMSG":"NO ERROR", "parseTag" : "DISK_IMPL"}}

DISK_PARENT_FINAL_DICT = {"disk" : [{"id" : "Disk Utilization.Disk Utilization.{}.id", "dused": "Disk Utilization.Disk Utilization.{}.UsedSpace", "name":"Disk Utilization.Disk Utilization.{}.Name", 
                                     "duper":"Disk Utilization.Disk Utilization.{}.UsedDiskPercent","dfree":"Disk Utilization.Disk Utilization.{}.FreeSpace", 
                                     "dfper":"Disk Utilization.Disk Utilization.{}.FreeDiskPercent", "iter":"Disk Utilization.Disk Utilization", "dtotal":"Disk Utilization.Disk Utilization.{}.Size","filesystem":"Disk Utilization.Disk Utilization.{}.FileSystem"}]}
#cpu.py
CPU_PARENT_RESULT_DICT = { "CPU_Monitoring" : {"CPU_Monitoring" : [{"Output":"-"}]},
                           "CPU Cores Usage":{"CPU Cores Usage":[]}, "parseTag" : "CPU_IMPL,SYSTEM_IMPL", "ERRORMSG":"NO ERROR"}
CPU_PARENT_FINAL_DICT = {"cpu" : [{"core":"CPU Cores Usage.CPU Cores Usage.{}.Name", "load":"CPU Cores Usage.CPU Cores Usage.{}.PercentProcessorTime", 
                                   "iter":"CPU Cores Usage.CPU Cores Usage"}]}

#process.py
PROCESS_DISCOVERY_DICT = {"pid" : "ProcessId", "name" : "Name", "exe" : "ExecutablePath", "cmdline" : "CommandLine", "cpu_percent" : "CPU_UTILIZATION", 
                          "memory_percent" : "MEMORY_UTILIZATION", "num_threads": "ThreadCount", "num_fds": "HandleCount", "username" : "User"}

PROCESS_FREE_ADD_DICT = {"pid" : "PROCESS_ID", "name" : "Name", "exe" : "PathName", "cmdline" : "Arguments"}

#"nice":"priority"
PROCESS_DETAILED_DICT = {"pid" : "pid", "name" : "name", "cmdline" : "args", "num_fds" : "handle", "num_threads" : "thread", "username":"user", 
                         "exe":"path", "memory_percent":"memory", "cpu_percent": "cpu" }
PROCESS_PARENT_RESULT_DICT = {"Process":{}}
PROCESS_PARENT_FINAL_DICT = {"Process":{}}

#"Avg. CPU Usage(%)" Avg. Memory Usage(MB)"
PROCESS_TOPMEMORY = {"pid":"Process Id", "name" : "Process Name", "cpu_percent":"CPU Usage(%)",  "memory_percent":"Memory Usage(MB)",  "num_threads":"Thread Count", "num_fds":"Handle Count", 
                     "exe":"Path", "cmdline":"Command Line Arguments"}

#configurations
CONFIG_DICT = {}
NEW_CONFIG_DICT = {}
