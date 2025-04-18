import json
import time
import sys,random
import traceback , os
    
from com.manageengine.monagent.util import AgentUtil,AppUtil
from com.manageengine.monagent.logger import AgentLogger
from com.manageengine.monagent import AgentConstants,AppConstants
from com.manageengine.monagent.scheduler import AgentScheduler
from com.manageengine.monagent.communication import CommunicationHandler
from six.moves.urllib.parse import urlencode

from com.manageengine.monagent.hadoop.data_parser import collect_data

from com.manageengine.monagent.hadoop import zk

def check_for_apps(app_conf_file):
    try:
        zookeeper_list = [AgentConstants.HOST_NAME+':2181']
        xml_content = AppUtil.read_hadoop_xml_file(AppConstants.hadoop_zk_locate_xml)
        hostname , port = AppUtil.check_for_apps(AppConstants.zookeeper_app)
        if xml_content or port:
            if 'ha.zookeeper.quorum' in xml_content:
                zookeeper_quorum = xml_content['ha.zookeeper.quorum']
                zookeeper_list = zookeeper_quorum.split(',')
            if not os.path.exists(app_conf_file):
                f = open(app_conf_file,"w+")
                f.close()
            for each_zk in zookeeper_list:
                host , port = each_zk.split(':')
                host = host.split('.')[0]
                each_zk = host
                conf_dict = {}
                conf_dict[each_zk] = {}
                conf_dict[each_zk]["mid"] = 0
                conf_dict[each_zk]["enabled"] = 1
                conf_dict[each_zk]["interval"] = 300
                conf_dict[each_zk]["host"] = host
                conf_dict[each_zk]["port"] = port
                with AppUtil.writeconf_file(app_conf_file, conf_dict) as fp:
                    _persist_status, _persist_error = fp
        else:
            AgentLogger.log(AgentLogger.APPS,'application not present :: zookeeper '+'\n')             
    except Exception as e:
        traceback.print_exc()

def zk_app_regisration(request_params):
    app_key='0'
    try:
        if request_params:
            str_requestParameters = urlencode(request_params)
            str_url = AgentConstants.APPLICATION_DISCOVERY_SERVLET + str_requestParameters
            AgentLogger.log(AgentLogger.APPS, "application registration call :: {}".format(str_url)+'\n')
            requestInfo = CommunicationHandler.RequestInfo()
            requestInfo.set_loggerName(AgentLogger.STDOUT)
            requestInfo.set_method(AgentConstants.HTTP_GET)
            requestInfo.set_url(str_url)
            requestInfo.set_dataType('application/json')
            requestInfo.add_header("Content-Type", 'application/json')
            requestInfo.add_header("Accept", "text/plain")
            requestInfo.add_header("Connection", 'close')
            (bool_isSuccess, errorCode, dict_responseHeaders, dict_responseData) = CommunicationHandler.sendRequest(requestInfo)
            AgentLogger.log(AgentLogger.APPS, "application {} :: response headers {}".format(AppConstants.zookeeper_app,dict_responseHeaders)+'\n')
            if dict_responseHeaders and "zookeeper_key" in dict_responseHeaders:
                app_key = dict_responseHeaders['zookeeper_key']
    except Exception as e:
        traceback.print_exc()
    finally:
        return app_key
    
def register_zk(config,app_conf_file,app_conf_object):
    register_status = False
    AgentLogger.debug(AgentLogger.APPS,'app conf object :: {}'.format(app_conf_object)+'\n')
    try:
        request_params = AgentUtil.get_default_reg_params()
        result = zk.main(config)
        if result:
            request_params['app'] = AppConstants.zookeeper_app.upper()
            cluster_id = AppUtil.read_a_content(AgentConstants.HDFS_CLUSTER_ID_FILE)
            if cluster_id:
                request_params['cluster_id'] = cluster_id 
            request_params['zk_config'] = {'host':str(config['host']),'port':str(config['port'])}
            request_params['ip'] = AgentConstants.HOST_NAME
            app_key = zk_app_regisration(request_params)
            config['mid']=app_key
            if app_key!='0':
                register_status = True
                app_conf_object[str(config['host'])]['mid']=app_key
                with AppUtil.writeconf_file(app_conf_file, app_conf_object) as fp:
                    _persist_status, _persist_error = fp
        else:
            AgentLogger.log(AgentLogger.APPS,'application discovery failed :: {}'.format(result)+'\n')
    except Exception as e:
        traceback.print_exc()
    finally:
        return register_status

def schedule_dc(config):
    try:
        interval=int(config['interval'])
        task=collect_zk_data
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
        scheduleInfo.setInterval(interval)
        scheduleInfo.setLogger(AgentLogger.APPS)
        AgentLogger.log(AgentLogger.APPS, 'dc scheduled for monitor :: '+str(taskName)+'\n')
        AgentScheduler.schedule(scheduleInfo)
        if AppConstants.zookeeper_app in AppConstants.app_vs_mids:
            AppConstants.app_vs_mids[AppConstants.zookeeper_app].append(config['mid'])
        else:
            AppConstants.app_vs_mids[AppConstants.zookeeper_app] = [config['mid']]
        AgentLogger.log(AgentLogger.APPS, 'app vs mid :: '+str(AppConstants.app_vs_mids)+'\n')
    except Exception as e:
        traceback.print_exc()

def data_save(final_dict):
    if final_dict:
        #AgentLogger.log(AgentLogger.APPS, 'zoo keeper data :: '+json.dumps(final_dict)+'\n')
        AppUtil.persist_apps_data(AppConstants.zookeeper_app, final_dict, AgentConstants.AGENT_UPLOAD_PROPERTIES_MAPPER['006'])
    else:
        AgentLogger.debug(AgentLogger.APPS, 'no data obtained for zoo keeper'+'\n')

def collect_zk_data(config):
    result = zk.main(config)
    return result

def execute_action(app_conf_file,rediscover):
    try:
        with AppUtil.readconf_file(app_conf_file) as fp:
             app_conf_object, status, error_msg = fp
        if app_conf_object:
            for each in app_conf_object:
                dc_schedule = False
                config = app_conf_object[each]
                if config['enabled'] == '1' or rediscover:
                    if config['mid'] !='0':
                        dc_schedule = True
                    else:
                        dc_schedule = register_zk(config,app_conf_file,app_conf_object)
                if dc_schedule:
                    schedule_dc(config)
    except Exception as e:
        traceback.print_exc()
                
def initialize(rediscover=False):
    app = AppConstants.zookeeper_app
    parent_folder = 'hadoop'
    app_conf_file = os.path.join(AgentConstants.APPS_FOLDER,parent_folder, AppConstants.app_conf_file_name[app])
    if not os.path.exists(app_conf_file) or rediscover:
        check_for_apps(app_conf_file)
    execute_action(app_conf_file,rediscover)