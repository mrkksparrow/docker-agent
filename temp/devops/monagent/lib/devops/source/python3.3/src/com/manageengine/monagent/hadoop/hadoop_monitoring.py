import json
import time
import sys
import traceback , os
    
from com.manageengine.monagent.util import AgentUtil,AppUtil
from com.manageengine.monagent.logger import AgentLogger
from com.manageengine.monagent import AgentConstants,AppConstants
from com.manageengine.monagent.scheduler import AgentScheduler

from com.manageengine.monagent.hadoop.data_parser import collect_data

def schedule_data_collection(metric_data):
    try:
        interval=int(metric_data['config']['interval'])
        task=collect_data
        taskArgs=metric_data
        taskName=metric_data['config']['mid']
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
        scheduleInfo.setLogger(AgentLogger.APPS)
        AgentLogger.log(AgentLogger.APPS, 'dc scheduled for monitor :: '+str(taskName)+'\n')
        AgentScheduler.schedule(scheduleInfo)
        if metric_data['app_name'] in AppConstants.app_vs_mids:
            AppConstants.app_vs_mids[metric_data['app_name']].append(metric_data['config']['mid'])
        else:
            AppConstants.app_vs_mids[metric_data['app_name']] = [metric_data['config']['mid']]
    except Exception as e:
        traceback.print_exc()
        AgentLogger.log(AgentLogger.APPS, 'Error at scheduling '+str(e)+'\n')

def data_save(final_dict):
    dir_prop = None
    if final_dict and 'node' in final_dict:
        app_name = final_dict['node']
        for key , value in final_dict.items():
            if key not in ['state','node']:
                list_of_dnodes = final_dict[key]
                chunks_of_dnodes = AgentUtil.list_chunks(list_of_dnodes,AgentConstants.NODE_COUNT_IN_DC)
                for each_chunks in chunks_of_dnodes:
                    data_dict={}
                    data_dict[key]=[]
                    data_dict[key]=each_chunks
                    if 'state' in final_dict:
                        data_dict['state']=final_dict['state']
                    data_dict['node']=final_dict['node']
                    if app_name == 'hadoop_namenode':
                        dir_prop = AgentConstants.AGENT_UPLOAD_PROPERTIES_MAPPER['007']
                    elif app_name == 'hadoop_datanode':
                        dir_prop = AgentConstants.AGENT_UPLOAD_PROPERTIES_MAPPER['008']
                    elif app_name == 'hadoop_yarn':
                        dir_prop = AgentConstants.AGENT_UPLOAD_PROPERTIES_MAPPER['009']
                    AppUtil.persist_apps_data(app_name, data_dict, dir_prop)
    else:
        AgentLogger.debug(AgentLogger.APPS, 'no data found')
                
def get_app_specific_params(request_params,metric_data,app_name,app_conf_object):
    try:
        get_registration_api = metric_data[app_name]['register_api']
        apis_to_hit = get_registration_api['api']
        output_dict = {}
        for each in apis_to_hit:
            dict_data = AppUtil.get_default_params()
            dict_data['url'] = app_conf_object[app_name]['protocol']+"://"+app_conf_object[app_name]['host']+":"+app_conf_object[app_name]['port']+each
            with AppUtil.handle_request(dict_data) as resp:
                if 'register' in output_dict:
                    output_dict[get_registration_api['output_tag']].append(resp.data)
                else:
                    output_dict[get_registration_api['output_tag']] = [resp.data]
        request_params['app'] = app_name.upper()
        if 'yarn' not in app_name:
            request_params['hadoop'] = True
            request_params['cluster_id'] = output_dict['register'][0]['beans'][0]['ClusterId']
            AppUtil.update_a_content(request_params['cluster_id'],AgentConstants.HDFS_CLUSTER_ID_FILE)
            request_params['ip'] = output_dict['register'][1]['beans'][0]['tag.Hostname']
            if 'Version' in output_dict['register'][0]['beans'][0]:
                request_params['Version'] = output_dict['register'][0]['beans'][0]['Version']
            else:
                request_params['Version'] = output_dict['register'][0]['beans'][0]['SoftwareVersion']
            request_params['state'] = output_dict['register'][2]['beans'][0]['State']
            nn=None
            xml_content = AppUtil.read_hadoop_xml_file(AppConstants.hadoop_zk_locate_xml)
            if xml_content:
                if 'dfs.nameservices' in xml_content:
                    service_name = xml_content['dfs.nameservices']
                    service_names_list = xml_content['dfs.ha.namenodes.'+service_name].split(',')
                    nn = []
                    for each_service in service_names_list:
                        nn.append(xml_content['dfs.namenode.http-address'+'.'+service_name+'.'+each_service].split(":")[0].split('.')[0])
                request_params['nn']=nn
        else:
            request_params['ip'] = AgentConstants.HOST_NAME
            cluster_id = AppUtil.read_a_content(AgentConstants.HDFS_CLUSTER_ID_FILE)
            if cluster_id:
                request_params['cluster_id'] = cluster_id 
            request_params['yarn_config'] = {'host':str(app_conf_object[app_name]['host']),'port':str(app_conf_object[app_name]['port'])}
    except Exception as e:
        traceback.print_exc()

def discovery(rediscover,app_name,app_conf_object,app_conf_file,metric_data):
    try:
        schedule_dc = False
        discover_app = False
        if app_conf_object:
            mid = app_conf_object[app_name]['mid']
            enabled = app_conf_object[app_name]['enabled']
            if enabled == '1':
                if mid!='0':
                    schedule_dc = True
                else:
                    discover_app = True
            else:
                if rediscover:
                    discover_app = True
                    AgentLogger.log(AgentLogger.APPS,'re-discovering {}'.format(app_name)+'\n')
                else:
                    AgentLogger.log(AgentLogger.APPS,'application {} disabled | suspended or deleted'.format(app_name)+'\n')
        else:
            discover_app = True
        status = False
        if discover_app:
            hostname , port = AppUtil.check_for_apps(app_name)
            if port:
                status , error = AppUtil.persist_app_conf(app_name, 0, 1, {app_name:{"protocol":"http", "host":hostname, "port":port}})
            if status:
                with AppUtil.readconf_file(app_conf_file) as fp:
                    app_conf_object, status, error_msg = fp
                request_params = AgentUtil.get_default_reg_params()
                get_app_specific_params(request_params,metric_data,app_name,app_conf_object)
                status , app_key = AppUtil.apps_registration(app_name,request_params)
                app_conf_object[app_name]['mid'] = app_key
                with AppUtil.writeconf_file(app_conf_file, app_conf_object) as fp:
                    _persist_status, _persist_error = fp
                if app_key!='0':
                    schedule_dc = True
            else:
                AgentLogger.log(AgentLogger.APPS,'application not present :: {}'.format(app_name)+'\n')
        if schedule_dc:
            metric_data['config'] = app_conf_object[app_name]
            metric_data['app_name'] = app_name
            schedule_data_collection(metric_data)
    except Exception as e:
        traceback.print_exc()

def initialize(rediscover=False):
    apps_list = [AppConstants.namenode_app,AppConstants.datanode_app,AppConstants.yarn_app]
    for apps in apps_list:
        app_conf_file = os.path.join(AgentConstants.APPS_FOLDER,apps.split('_')[0], AppConstants.app_conf_file_name[apps])
        metric_file = os.path.join(AgentConstants.APPS_FOLDER,apps.split('_')[0],AppConstants.app_metrics_conf_file_name[apps])
        status , metric_data = AgentUtil.loadDataFromFile(metric_file)
        app_conf_object = None
        with AppUtil.readconf_file(app_conf_file) as fp:
            app_conf_object, status, error_msg = fp
        discovery(rediscover,apps,app_conf_object,app_conf_file,metric_data)