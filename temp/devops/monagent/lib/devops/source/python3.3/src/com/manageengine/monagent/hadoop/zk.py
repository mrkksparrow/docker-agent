import socket
import json,traceback

from com.manageengine.monagent.logger import AgentLogger
from xml.etree.ElementTree import tostring
from com.manageengine.monagent import AgentConstants,AppConstants
from com.manageengine.monagent.util import AgentUtil

class ZooKeeper(object):
    def __init__(self,config):
        self.configurations=config
        self.zookeeper_commands = ['mntr','ruok','conf']
        self.host=self.configurations.get('host', 'localhost')
        self.port=self.configurations.get('port', '2181')

    def metricCollector(self):
        AgentLogger.debug(AgentLogger.APPS,' host and port :: {} {}'.format(self.host,self.port))
        data = {}
        data['@'+'type']=AppConstants.zookeeper_app.upper()
        data['@'+'availability']=1
        data['@'+'id']=self.host
        for command in self.zookeeper_commands:
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(4)#socket timeout
                s.connect((self.host, int(self.port)))
                s.sendall(AgentUtil.text_to_bytes(command))
                reply = AgentUtil.bytes_to_text(s.recv(1024))
                if command == 'conf':
                    data = self.parse_conf(data, reply)
                elif command == 'ruok':
                    data = self.parse_ruok(data, reply)
                elif command == 'srvr':
                    data = self.parse_srvr(data, reply)
                elif command == 'mntr':
                    data = self.parse_mntr(data, reply)
                del s
            except Exception as exception:
                if command == "ruok":
                    data['@'+'availability']=0
                    data['@'+'msg']='failed to read from socket'
                traceback.print_exc()
        return data

    def parse_conf(self, data, reply):
        conf_metrics = ['clientPort','tickTime','maxClientCnxns','minSessionTimeout','maxSessionTimeout','initLimit','syncLimit']
        for line in reply.split('\n'):
            try:
                if not line:
                    continue
                key, value = line.split('=')
                if key in conf_metrics:
                    data["@"+key.lower()] = int(value)
            except Exception as e:
                traceback.print_exc()
        return data

    def parse_mntr(self, data, reply):
        data['@'+'zk_server_state'] = -1
        for line in reply.split('\n'):
            if not line:
                continue
            split_line = line.split('\t')
            key = split_line[0]
            value = split_line[1].split('.')[0]
            if key == 'zk_version':
                value = value.split('-')[0]
            data["@"+key.lower()] = value
        if '@zk_open_file_descriptor_count' in data and '@zk_max_file_descriptor_count' in data:
            data['@zk_fd'] = (int(data['@zk_open_file_descriptor_count']) / int(data['@zk_max_file_descriptor_count'])) * 100
        return data

    def parse_ruok(self, data, reply):
        if reply == 'imok':
            data["@"+'imok'] = reply
        else:
            data["@"+'imok'] = "0"
        return data

    def parse_srvr(self, data, reply):
        for line in reply.split('\n'):
            if not line or line.startswith('Zookeeper version'):
                continue
            key, value = line.split(':')
            if key == 'Node count':
                key = 'node_count'
            if key in ['Mode', 'Zxid']:
                continue
            if key.startswith('Latency min/avg/max'):
                data["@"+'latency_min'] = int(value.split('/')[0])
                data["@"+'latency_avg'] = int(value.split('/')[1])
                data["@"+'latency_max'] = int(value.split('/')[2])
            elif key.startswith('Proposal sizes last/min/max'):
                data["@"+'proposal_sizes_last'] = int(value.split('/')[0])
                data["@"+'proposal_sizes_min'] = int(value.split('/')[1])
                data["@"+'proposal_sizes_max'] = int(value.split('/')[2])
            else:
                data["@"+key.lower()] = int(value.strip())
        return data

def main(zk_config):
    if AppConstants.zookeeper_app in AgentConstants.SKIP_STANDBY_NODES:
        AgentLogger.log(AgentLogger.APPS,'skip_standby_dc set to true hence skipping dc of zookeeper')
        return None
    configurations = {'host':zk_config['host'],'port':zk_config['port']}
    config_obj = AgentConstants.APPS_CONFIG_DATA
    if config_obj and AppConstants.zookeeper_app.upper() in config_obj:
        app_config = config_obj[AppConstants.zookeeper_app.upper()]
        p_key = zk_config['host']
        if zk_config['host'] in AppConstants.skip_dc_for_nodes:
            AgentLogger.log(AgentLogger.APPS,' skipping dc as {}  is in stop dc node list :: {}'.format(AppConstants.zookeeper_app,zk_config['host'])+'\n')
            return None
        if p_key in app_config and int(app_config[p_key]['status']) != 0:
            AgentLogger.log(AgentLogger.APPS,' skipping dc as app status is not active :: {}'.format(app_config[p_key])+'\n')
            return None
    zookeeper_plugin = ZooKeeper(configurations)
    zk_data = zookeeper_plugin.metricCollector()
    xml_output = {}
    xml_output[zk_config['mid']]= []
    temp_dict = {}
    temp_dict['DC'] = zk_data
    result = AgentConstants.XMLJSON_BF.etree(temp_dict)
    if AppConstants.nn_state:
        xml_output['state'] = AppConstants.nn_state
    xml_output['node'] = AppConstants.zookeeper_app
    xml_output[zk_config['mid']].append(tostring(result[0]).decode('utf-8'))
    return xml_output

if __name__ == "__main__":
    configurations = {'host':ZOOKEEPER_HOST,'port':ZOOKEEPER_PORT}
    zookeeper_plugin = ZooKeeper(configurations)
    result = zookeeper_plugin.metricCollector()