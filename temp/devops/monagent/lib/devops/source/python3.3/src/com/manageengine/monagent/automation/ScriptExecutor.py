
'''
@author: Sriram VS

Script Executor - schedules one time or periodic execution of scripts

'''
#$Id$
import json
import os
import time
import traceback
from com.manageengine.monagent.logger import AgentLogger
from com.manageengine.monagent import AgentConstants
from com.manageengine.monagent.automation.ScriptHandler import scriptHandler
from com.manageengine.monagent.automation.ScriptDeployer import scriptDeployer
from com.manageengine.monagent.scheduler import AgentScheduler
from com.manageengine.monagent.scheduler.AgentScheduler import Scheduler
from com.manageengine.monagent.util import AgentUtil

ID_VS_TASK = {}

#TODO - Edit Update action - Store a map with [ script id vs scheduler object ]
def scriptExecutor(task_list=None):
    global ID_VS_TASK
    try:
        for dict_task in task_list:
            interval=0
            key=dict_task['SCRIPT_ID']
            if key in ID_VS_TASK:
                if dict_task['REQUEST_TYPE']==AgentConstants.SCRIPT_DEPLOY:
                    AgentLogger.log(AgentLogger.STDOUT,'task already running :: {} id vs task :: {}'.format(key,ID_VS_TASK))
                    schedule_info = ID_VS_TASK[key]
                    dict_response = scriptDeployer.get_default_response(dict_task,AgentUtil.getTimeInMillis(),True,'Task already running')
                    scriptDeployer.uploadResponse(dict_response)
                    return
                else:
                    removeSchedule(key)
            scheduleInfo = AgentScheduler.ScheduleInfo()
            if 'schedule' in dict_task and dict_task['schedule']=='true':
                scheduleInfo.setIsPeriodic(True)
                interval = dict_task['interval']
            else:
                scheduleInfo.setIsPeriodic(False)
            task = executeScripts 
            taskArgs = dict_task
            scheduleInfo.setSchedulerName('AgentScheduler')
            scheduleInfo.setTaskName(key)
            scheduleInfo.setTime(time.time())
            scheduleInfo.setTask(task)
            scheduleInfo.setTaskArgs(taskArgs)
            scheduleInfo.setInterval(interval)
            scheduleInfo.setLogger(AgentLogger.STDOUT)
            AgentScheduler.schedule(scheduleInfo)
            ID_VS_TASK[key]=scheduleInfo
            AgentLogger.log(AgentLogger.STDOUT,'========= ID VS TASK ========'+repr(ID_VS_TASK))
    except Exception as e:
        traceback.print_exc()
            
def executeScripts(dict_task):
    if AgentUtil.is_module_enabled(AgentConstants.AUTOMATION_SETTING):
        AgentLogger.log(AgentLogger.STDOUT,'========= Task Invoked ========')
        if dict_task['REQUEST_TYPE']==AgentConstants.SCRIPT_DEPLOY:
            sh = scriptDeployer(dict_task)
        else:
            sh = scriptHandler(dict_task)
        sh.run()
    else:
        AgentLogger.log(AgentLogger.MAIN,'========= Automation / Deployment disabled ========')
    
def removeSchedule(key):
    if key in ID_VS_TASK:
        AgentLogger.log(AgentLogger.STDOUT,'========= Deleting the Existing Task ========')
        ID_VS_TASK.pop(key)
        scheduleInfo = AgentScheduler.ScheduleInfo()
        scheduleInfo.setSchedulerName('AgentScheduler')
        scheduleInfo.setTaskName(key)
        AgentScheduler.deleteSchedule(scheduleInfo)