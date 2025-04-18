#$Id$

import traceback
import json
import six.moves.urllib.request as urlconnection
from com.manageengine.monagent import AgentConstants
from com.manageengine.monagent.logger import AgentLogger
from com.manageengine.monagent.communication import CommunicationHandler
from com.manageengine.monagent.kubernetes import KubeGlobal

def get_azure_resource_id():
    bool_flag, resource_id = False, None
    try:
        bool_flag, resp_data = CommunicationHandler.send_request_to_url(AgentConstants.AZURE_RESOURCEID_API, None, {"metadata": "true"})
        if bool_flag:
            KubeGlobal.PROVIDER = "Azure"
            resource_id = resp_data['resourceId']
    except Exception as e:
        AgentLogger.log(AgentLogger.STDOUT,'Exception occurred while fetching azure resource id '+repr(e))
    return bool_flag, resource_id

def check_vmware_platform():
    bool_flag, json_dict = False, {}
    try:
        vmware_process_info = [p.info for p in AgentConstants.PSUTIL_OBJECT.process_iter(attrs=['pid', 'name','cmdline']) if '/usr/sbin/vmtoolsd' in p.info['cmdline']]
        if vmware_process_info:
            KubeGlobal.PROVIDER = "Vmware"
            bool_flag = True
            json_dict['cloudPlatform']="VMWare"
        else:
            AgentLogger.log(AgentLogger.STDOUT,'Not a VMWare instance '+repr(vmware_process_info))
    except Exception as e:
        traceback.print_exc()
    return bool_flag, json_dict, {}

def check_gcp_platform():
    bool_flag, json_dict, resp_data = False, {}, {}
    try:
        bool_flag, resp_data = CommunicationHandler.send_request_to_url('http://169.254.169.254/computeMetadata/v1/instance/id', None, {"Metadata-Flavor":"Google"})
        if bool_flag:
            KubeGlobal.PROVIDER = "GCP"
            json_dict["key"]="id"
            json_dict["id"] = resp_data
            json_dict["cloudPlatform"] = "GCP"
            json_dict["privateIp"] = get_gcp_vm_ip()
    except Exception as e:
        AgentLogger.log(AgentLogger.STDOUT,'Not a gcp instance '+repr(e))
    return bool_flag, json_dict, resp_data

def get_gcp_vm_ip():
    ip_address = None
    try:
        bool_flag, resp_data = CommunicationHandler.send_request_to_url('http://169.254.169.254/computeMetadata/v1/instance/network-interfaces/0/ip', None, {"Metadata-Flavor":"Google"})
        if resp_data and len(resp_data) > 0: 
            ip_address = resp_data
    except Exception as e:
        traceback.print_exc()
    finally:
        return ip_address

def check_aws_platform():
    bool_flag, json_dict, resp_data = False, {}, {}
    try:
        bool_flag, resp_data = CommunicationHandler.send_request_to_url("http://169.254.169.254/latest/dynamic/instance-identity/document")
        if not bool_flag:
            bool_flag,auth_token = CommunicationHandler.send_request_to_url("http://169.254.169.254/latest/api/token",None,{"X-aws-ec2-metadata-token-ttl-seconds":"21600"},"PUT")
            if auth_token:
                bool_flag, resp_data = CommunicationHandler.send_request_to_url("http://169.254.169.254/latest/dynamic/instance-identity/document",None,{"X-aws-ec2-metadata-token":auth_token})
        if bool_flag:
            KubeGlobal.PROVIDER = "AWS"
            json_dict['cloudPlatform']="AWS"
            json_dict["key"]="instanceId"
            json_dict["instanceId"]=resp_data["instanceId"]
            json_dict['privateIp']=resp_data.get('privateIp', None)
            json_dict['hostname'] = get_ec2_hostname()
            get_aws_tags()
    except Exception as e:
        AgentLogger.log(AgentLogger.STDOUT,'Not an AWS instance '+repr(e))
    return bool_flag, json_dict, resp_data

def get_aws_tags():
    final_tags = ","
    auth_token = None
    try:
        bool_flag, resp_data = CommunicationHandler.send_request_to_url("http://169.254.169.254/latest/meta-data/tags/instance")
        if not resp_data:
            bool_flag,auth_token = CommunicationHandler.send_request_to_url("http://169.254.169.254/latest/api/token",None,{"X-aws-ec2-metadata-token-ttl-seconds":"21600"},"PUT")
            if auth_token:
                bool_flag, resp_data = CommunicationHandler.send_request_to_url("http://169.254.169.254/latest/meta-data/tags/instance",None,{"X-aws-ec2-metadata-token":auth_token})
        if resp_data:
            AgentLogger.log(AgentLogger.MAIN,'response of tags api : {}'.format(resp_data,type(resp_data)))
            if isinstance(resp_data, str):
                AgentLogger.log(AgentLogger.MAIN,'string instance')
                tags_list = resp_data.splitlines()
                AgentLogger.log(AgentLogger.MAIN,'tags list : {}'.format(tags_list))
                tags_dict = {}
                final_list = []
                for each in tags_list:
                    if auth_token:
                        bool_flag, tag_value = CommunicationHandler.send_request_to_url("http://169.254.169.254/latest/meta-data/tags/instance/{}".format(each),None,{"X-aws-ec2-metadata-token":auth_token})
                    else:
                        bool_flag, tag_value = CommunicationHandler.send_request_to_url("http://169.254.169.254/latest/meta-data/tags/instance/{}".format(each))
                    AgentLogger.log(AgentLogger.MAIN,'tag api output :: {}'.format(bool_flag,tag_value))
                    if tag_value:
                        final_list.append(each+":"+str(tag_value))
                    else:
                        final_list.append(each)
                final_tags = final_tags.join(final_list)
            AgentLogger.log(AgentLogger.MAIN,'final tags :: {}'.format(final_tags))
            AgentConstants.AWS_TAGS = final_tags
    except Exception as e:
        traceback.print_exc()

def check_azure_platform():
    bool_flag, json_dict, meta_dict = False, {}, {}
    try:
        bool_flag, resp_data = CommunicationHandler.send_request_to_url("http://169.254.169.254/metadata/v1/InstanceInfo")
        if bool_flag:
            KubeGlobal.PROVIDER = "Azure"
            json_dict["cloudPlatform"]="Azure"
            json_dict["key"]="ID"
            json_dict["ID"]=resp_data["ID"]
            meta_dict.update(resp_data)
            try:
                headers = {'Metadata':'true'}
                bool_flags, resp_data = CommunicationHandler.send_request_to_url("http://169.254.169.254/metadata/instance?api-version=2021-02-01", headers=headers)
                AgentLogger.log(AgentLogger.STDOUT,"Metadata fetched : "+ repr(resp_data))
                privateIp = resp_data['network']['interface'][0]['ipv4']['ipAddress'][0]['privateIpAddress']
                hostname = resp_data['compute']['osProfile']['computerName']
                AgentConstants.AWS_TAGS = resp_data['compute']['tags'].replace(';',',')
                AgentLogger.log(AgentLogger.STDOUT, "Identified Azure vm hostname via cloud api - {}".format(hostname))
                meta_dict.update(resp_data)
            except:
                privateIp = hostname = None
            json_dict['privateIp'] = privateIp
            json_dict['hostname'] = hostname
    except Exception as e:
        AgentLogger.log(AgentLogger.STDOUT,'Not azure instance '+repr(e))
    return bool_flag, json_dict, meta_dict

def check_upcloud_platform():
    bool_flag, json_dict, resp_data = False, {}, {}
    try:
        bool_flag, resp_data = CommunicationHandler.send_request_to_url("http://169.254.169.254/metadata/v1.json")
        if bool_flag:
            KubeGlobal.PROVIDER = "UpCloud"
            json_dict["cloudPlatform"]="UpCloud"
            json_dict["key"]="instance_id"
            json_dict["instance_id"]=resp_data["instance_id"]
    except Exception as e:
        AgentLogger.log(AgentLogger.STDOUT,'Not an upcloud instance '+repr(e))
    return bool_flag, json_dict, resp_data
    
def check_digital_ocean_platform():
    bool_flag, json_dict, resp_data = False, {}, {}
    try:
        bool_flag, resp_data = CommunicationHandler.send_request_to_url("http://169.254.169.254/metadata/v1.json")
        if bool_flag:
            KubeGlobal.PROVIDER = "DigitalOcean"
            json_dict["cloudPlatform"]="DigitalOcean"
            json_dict["key"]="droplet_id"
            json_dict["droplet_id"]=resp_data["droplet_id"]
    except Exception as e:
        AgentLogger.log(AgentLogger.STDOUT,'Not a digital ocean instance '+repr(e))
    return bool_flag, json_dict, resp_data

def get_hostname_for_gcp_vms():
    resp_data = None
    try:
        bool_flag, resp_data = CommunicationHandler.send_request_to_url("http://169.254.169.254/computeMetadata/v1/instance/name", None, {"Metadata-Flavor":"Google"})
    except Exception as e:
        traceback.print_exc()
    return resp_data

def get_ec2_hostname():
    hostname = None
    try:
        bool_flag, auth_token = CommunicationHandler.send_request_to_url("http://169.254.169.254/latest/api/token",None, {"X-aws-ec2-metadata-token-ttl-seconds": "21600"},"PUT")
        if auth_token:
            bool_flag, hostname = CommunicationHandler.send_request_to_url("http://169.254.169.254/latest/meta-data/hostname", None,{"X-aws-ec2-metadata-token": auth_token})
            AgentLogger.log(AgentLogger.MAIN, "Identified hostname for EC2 from cloud api - {}".format(hostname))
    except Exception as e:
        traceback.print_exc()
    finally:
        return hostname
    
def check_oci_platform():
    bool_flag, json_dict, resp_data = False, {}, {}
    try:
        bool_flag, resp_data = CommunicationHandler.send_request_to_url("http://169.254.169.254/opc/v2/instance/",None, {"Authorization":"Bearer Oracle"})
        if bool_flag:
            json_dict["cloudPlatform"] = "Oracle"
            json_dict["key"]="id"
            json_dict["id"] = resp_data["id"]
            json_dict["hostname"] = resp_data["hostname"]
    except Exception as e:
        AgentLogger.log(AgentLogger.STDOUT,'Not an Oracle instance '+repr(e))
    finally:
        return bool_flag, json_dict, resp_data