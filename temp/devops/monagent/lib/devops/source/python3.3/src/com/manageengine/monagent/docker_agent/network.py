'''
Created on 22-Jan-2018

@author: giri
'''
#python packages
from __future__ import division
import shlex
import traceback
import json
import copy

#s24x7 packages
from com.manageengine.monagent.docker_agent.collector import Metrics
from com.manageengine.monagent.logger import AgentLogger
from com.manageengine.monagent import AgentConstants
from com.manageengine.monagent.framework.suite.helper import s247_commandexecutor
from com.manageengine.monagent.framework.suite.helper import handle_counter_values
from com.manageengine.monagent.docker_agent import constants


class Network(Metrics):
    
    PREV_COUNTER_HOLDER_TEMPLATE = {"BytesReceivedPersec": 0, "PacketsReceivedUnicastPersec": 0, "BytesSentPersec":0, "PacketsSentUnicastPersec":0, "PacketsOutboundErrors":0, \
                           "PacketsOutboundDiscarded":0, "PacketsReceivedNonUnicastPersec":0, "PacketsSentNonUnicastPersec":0}
    
    PREV_COUNTER_HOLDER = {}
    
    def handle_network_data(self):
        network_config = constants.CONFIG_DICT.get("nw", [])
        value_list = []
        metrics_list = ["AdapterDesc", "Status", "MACAddress", "BytesReceivedPersec", "PacketsReceivedUnicastPersec", "BytesSentPersec", "PacketsSentUnicastPersec", "PacketsOutboundErrors",\
                        "PacketsOutboundDiscarded", "PacketsReceivedNonUnicastPersec", "PacketsSentNonUnicastPersec"]
        per_sec_metric_list = ["BytesSentPersec", "BytesReceivedPersec", "PacketsReceivedUnicastPersec", "PacketsReceivedNonUnicastPersec"]
        if AgentConstants.OS_NAME == AgentConstants.SUN_OS.lower():
            _output = ""
            net_stat_output = AgentConstants.DOCKER_PSUTIL.net_if_stats()
            per_nic_output = AgentConstants.DOCKER_PSUTIL.net_io_counters(pernic=True)
            if_addr = AgentConstants.DOCKER_PSUTIL.net_if_addrs()
            for key, value in per_nic_output.items():
                status = "1" if net_stat_output.get(key).isup is True else "0"
                ip_addr = if_addr[key][0].address
                rx_bytes = str(value.bytes_recv)
                rx_packets = str(value.packets_recv)
                tx_bytes = str(value.bytes_sent)
                tx_packets = str(value.packets_sent)
                tx_errors = str(value.errout)
                tx_drops = str(value.dropout)
                _output = _output + key + " -- "+ status + " -- " + ip_addr + " -- " + rx_bytes + " -- " + rx_packets + " -- " + tx_bytes + " -- " + tx_packets + " -- " + tx_errors +\
                     " -- "+ tx_drops + " -- " + rx_packets + "\n"
        else:
            with s247_commandexecutor(constants.DA_NETWORK_DATA_COMMAND, env=constants.ENV_DICT) as op:
                _output, _returncode, _errormsg, _outputtype = op
        
        AgentLogger.log(AgentLogger.DA, "interface output :: {}".format(_output))
        if "\n" in _output:
            output_list = _output.split("\n")[:-1]
            for line in output_list:
                lines = line.strip().split("--")
                lines = list(map(lambda x : x.strip(), lines))
                value_dict = dict(zip(metrics_list, lines))
                adapter_name = value_dict["AdapterDesc"]
                id_list = list(map(lambda x : x["id"] if x["ma"] == value_dict["MACAddress"] and x["nn"] == adapter_name else None, network_config))
                id_list = list(filter(lambda x : x, id_list))
                value_dict["id"] = id_list[0] if id_list else "None"
                value_dict["PacketsSentNonUnicastPersec"] = "0"
                mac_addr = value_dict["MACAddress"]
                mac_addr = mac_addr.replace("0", "")
                mac_addr = mac_addr.replace(":", "")
                uniq_key = adapter_name + "_" + mac_addr
                if not uniq_key:    continue
                if not uniq_key in Network.PREV_COUNTER_HOLDER:    Network.PREV_COUNTER_HOLDER[uniq_key] = Network.PREV_COUNTER_HOLDER_TEMPLATE.copy()
                handle_counter_values(value_dict, Network.PREV_COUNTER_HOLDER[uniq_key])
                for key in per_sec_metric_list:
                    value_dict[key] = round(float(value_dict[key])/AgentConstants.MONITORING_INTERVAL, 2)
                for key, value in zip(per_sec_metric_list, ["bytessentkb", "bytesrcvkb"]):
                    value_dict[value] = int(float(value_dict[key])/1024)
                value_dict["totbyteskb"] = value_dict["bytessentkb"] + value_dict["bytesrcvkb"]
                value_list.append(value_dict)
        self.result_dict["Network Data"]["Network Data"] = value_list

    def construct(self):
        self.handle_network_data()
    
    def collect(self):
        self.construct()
        self.parse(self.final_dict)
