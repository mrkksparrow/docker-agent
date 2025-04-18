# $Id$
import json
import time
import sys,random
import traceback , os
    
from com.manageengine.monagent.util import AgentUtil,AppUtil
from com.manageengine.monagent.logger import AgentLogger
from com.manageengine.monagent import AgentConstants,AppConstants
from com.manageengine.monagent.scheduler import AgentScheduler
from six.moves.urllib.parse import urlencode
from .container_stats import DockerStats
from com.manageengine.monagent.discovery.container_discovery import ContainerDiscovery

def check_for_apps(app_conf_file):
    try:
        if DockerStats.get_docker_connection():
            if not os.path.exists(os.path.join(AgentConstants.APPS_FOLDER,AppConstants.docker_app)):
                os.makedirs(os.path.join(AgentConstants.APPS_FOLDER,AppConstants.docker_app))
            status , error = AppUtil.persist_app_conf(AppConstants.docker_app, 0, 1, {AppConstants.docker_app:{"base_url":AppConstants.docker_base_url, "container_discovery_interval": AppConstants.CONTAINER_DISCOVERY_INTERVAL}})
        else:
            AgentLogger.log(AgentLogger.APPS,'application not present :: docker '+'\n')
    except Exception as e:
        traceback.print_exc()

def register_docker(config,app_conf_file,app_conf_object):
    register_status = False
    try:
        request_params = AgentUtil.get_default_reg_params()
        docker_version = DockerStats.get_docker_connection().version()
        os_type = docker_version.get("Os", None)
        arch = docker_version.get("Arch", None)
        request_params["docker"] = "true"
        request_params["OsArch"] =  os_type + "-" + arch if os_type and arch else "None"
        request_params["Version"] = docker_version.get("Version")
        if AppConstants.isPodmanPresent:
            request_params["podman"]="true"

        register_status , app_key = AppUtil.apps_registration(AppConstants.docker_app,request_params)
        config['mid']=app_key
        if app_key!='0':
            register_status = True
            app_conf_object[AppConstants.docker_app]['mid']=app_key
            with AppUtil.writeconf_file(app_conf_file, app_conf_object) as fp:
                _persist_status, _persist_error = fp
    except Exception as e:
        traceback.print_exc()
    finally:
        return register_status

def schedule_container_discovery(request_args):
    try:
        AgentLogger.log(AgentLogger.APPS,'container discovery args :: {}'.format(request_args))
        container_disc_obj = ContainerDiscovery(request_args)
        task=container_disc_obj.discover
        taskName=request_args['CHILD_TYPE']
        callback=container_disc_obj.post_action
        scheduleInfo = AgentScheduler.ScheduleInfo()
        request_id = str(request_args['AGENT_REQUEST_ID'])
        if request_id == "-1":
            scheduleInfo.setIsPeriodic(True)
            scheduleInfo.setInterval(int(AppConstants.CONTAINER_DISCOVERY_INTERVAL))
        else:
            scheduleInfo.setIsPeriodic(False)
            scheduleInfo.setInterval(0)
        scheduleInfo.setSchedulerName('AgentScheduler')
        scheduleInfo.setTaskName(taskName+'_'+request_id)
        scheduleInfo.setTime(time.time())
        scheduleInfo.setTask(task)
        scheduleInfo.setCallback(callback)
        scheduleInfo.setLogger(AgentLogger.APPS)
        AgentScheduler.schedule(scheduleInfo)
    except Exception as e:
        traceback.print_exc()

def schedule_dc(config):
    try:
        stats_obj = DockerStats()
        interval=int(config['interval'])
        task=stats_obj.collect_container_data
        taskArgs=config
        taskName=config['mid']
        callback=data_save
        scheduleInfo=AgentScheduler.ScheduleInfo()
        scheduleInfo.setIsPeriodic(True)
        scheduleInfo.setSchedulerName('AgentScheduler')
        scheduleInfo.setTaskName(taskName)
        scheduleInfo.setTime(time.time())
        scheduleInfo.setTask(task)
        scheduleInfo.setTaskArgs(taskArgs)
        scheduleInfo.setCallback(callback)
        scheduleInfo.setInterval(300)
        scheduleInfo.setLogger(AgentLogger.APPS)
        AgentLogger.log(AgentLogger.APPS, 'dc scheduled for monitor :: '+str(taskName)+'\n')
        AgentScheduler.schedule(scheduleInfo)
    except Exception as e:
        traceback.print_exc()

def data_save(final_dict):
    if final_dict:
        AgentLogger.debug(AgentLogger.APPS,' final dict -- {}'.format(final_dict))
        AppUtil.persist_apps_data(AppConstants.docker_app,final_dict,AgentConstants.AGENT_UPLOAD_PROPERTIES_MAPPER['005'])
    else:
        AgentLogger.log(AgentLogger.APPS,' data empty ')

def unschedule_main_dc():
    try:
        scheduleInfo = AgentScheduler.ScheduleInfo()
        scheduleInfo.setSchedulerName('AgentScheduler')
        scheduleInfo.setTaskName('docker_monitoring')
        AgentScheduler.deleteSchedule(scheduleInfo)
    except Exception as e:
        traceback.print_exc()

def execute_action(app_conf_file,rediscover):
    try:
        with AppUtil.readconf_file(app_conf_file) as fp:
             app_conf_object, status, error_msg = fp
        dc_schedule = False
        if AppConstants.docker_app in app_conf_object:
            config = app_conf_object[AppConstants.docker_app]
            if config['enabled'] == '1' or rediscover:
                if config['mid'] !='0':
                    dc_schedule = True
                else:
                    dc_schedule = register_docker(config,app_conf_file,app_conf_object)
            if dc_schedule:
                request_args = {"MONITOR_ID":config['mid'],"MONITOR_TYPE":"DOCKER","CHILD_TYPE":"SERVER_CONTAINER","AGENT_REQUEST_ID":"-1"}
                schedule_container_discovery(request_args)
                schedule_dc(config)
                unschedule_main_dc()
    except Exception as e:
        traceback.print_exc()
                
def initialize(rediscover=False):
    app = AppConstants.docker_app
    app_conf_file = os.path.join(AgentConstants.APPS_FOLDER,AppConstants.docker_app,AppConstants.app_conf_file_name[app])
    if not os.path.exists(app_conf_file) or rediscover:
        check_for_apps(app_conf_file)
    execute_action(app_conf_file,rediscover)