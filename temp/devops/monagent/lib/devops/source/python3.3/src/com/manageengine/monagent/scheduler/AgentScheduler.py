# $Id$
import threading
from datetime import datetime
import time
import traceback

from com.manageengine.monagent import AgentConstants
from com.manageengine.monagent.logger import AgentLogger
from com.manageengine.monagent.util import AgentUtil


SCHEDULERS = {}

SCHEDULER_DEFAULT_WORKERS = 3
SCHEDULER_SLEEP_INTERVAL = .10 # In Seconds
WORKER_WAIT_INTERVAL = 1000 # In Seconds

def initialize():
    AgentLogger.log(AgentLogger.COLLECTOR,'=============================== INITIALIZING SCHEDULER ===============================')
    AgentLogger.log(AgentLogger.COLLECTOR,'Workers : '+repr(AgentConstants.AGENT_SCHEDULER_NO_OF_WORKERS))
    if AgentConstants.IS_DOCKER_AGENT == '1':
        AgentConstants.AGENT_SCHEDULER_NO_OF_WORKERS = 3
        AgentConstants.AGENT_SCHEDULER_NO_OF_PLUGIN_WORKERS = 3
    Scheduler.startScheduler('AgentScheduler', AgentConstants.AGENT_SCHEDULER_NO_OF_WORKERS)
    Scheduler.startScheduler('PluginScheduler', AgentConstants.AGENT_SCHEDULER_NO_OF_PLUGIN_WORKERS)
    Scheduler.startScheduler('K8sScheduler', AgentConstants.AGENT_SCHEDULER_NO_OF_K8s_WORKERS)

def getScheduler(str_schedulerName):
    if str_schedulerName in SCHEDULERS:
        return SCHEDULERS[str_schedulerName]

def getSchedulerTasks(str_schedulerName='AgentScheduler'):
    if str_schedulerName in SCHEDULERS:
        return SCHEDULERS[str_schedulerName].getAvailableTasks()
    
def stopSchedulers():
    for str_schedulerName in SCHEDULERS.keys():
        SCHEDULERS[str_schedulerName].stopScheduler()
        
def synchronized(func):    
    func.__lock__ = threading.Lock()
    def synced_func(*args, **kwargs):
        with func.__lock__:
            func(*args, **kwargs)
    return synced_func

class UnknownSchedulerException(Exception):
    def __init__(self):
        self.message = 'Unknown Scheduler Exception'
    def __str__(self):
        return self.message

@synchronized
def schedule(scheduleInfo):
    if scheduleInfo.getSchedulerName() in SCHEDULERS:
        SCHEDULERS[scheduleInfo.getSchedulerName()].scheduleTask(scheduleInfo)
    else:
        AgentLogger.log([AgentLogger.COLLECTOR,AgentLogger.STDERR],' ************************* Unable to find the scheduler : '+str(scheduleInfo.getSchedulerName())+' for scheduling : '+repr(scheduleInfo)+' ************************* ')
        raise UnknownSchedulerException

@synchronized
def deleteSchedule(scheduleInfo):
    if scheduleInfo.getSchedulerName() in SCHEDULERS:
        SCHEDULERS[scheduleInfo.getSchedulerName()].deleteScheduledTask(scheduleInfo)
    else:
        AgentLogger.log([AgentLogger.COLLECTOR,AgentLogger.STDERR],' ************************* Unable to find the scheduler : '+str(scheduleInfo.getSchedulerName())+' while deleting the scheduled info : '+repr(scheduleInfo)+' ************************* ')
        raise UnknownSchedulerException
    
class ScheduleInfo(object):
    def __init__(self):
        self.schedulerName = None
        self.taskName = None
        self.createdTime = time.time()
        self.time = None
        self.task = None
        self.taskArgs = None
        self.callback = None
        self.callbackArgs = None
        self.bool_isPeriodic = False
        self.interval = None
        self.logger = AgentLogger.STDOUT
        self.props = None
        
    def __str__(self):
        str_scheduleInfo = ''
        str_scheduleInfo += 'SCHEDULER NAME : '+repr(self.schedulerName)
        str_scheduleInfo += ' TASK NAME : '+repr(self.taskName)
        str_scheduleInfo += ' TIME : '+repr(datetime.fromtimestamp(self.time).strftime("%Y-%m-%d %H:%M:%S"))
        # This check avoids function address being printed.
        if self.task and hasattr(self.task, '__call__'):
            str_scheduleInfo += ' TASK : '+repr(self.task.__name__)
        else:
            str_scheduleInfo += ' TASK : '+repr(self.task)
        str_scheduleInfo += ' IS PERIODIC : '+repr(self.bool_isPeriodic)
        str_scheduleInfo += ' INTERVAL : '+repr(self.interval)
        str_scheduleInfo += ' TASK ARGS : '+repr(self.taskArgs)
        if self.callback and hasattr(self.callback, '__call__'):
            str_scheduleInfo += ' CALLBACK : '+repr(self.callback.__name__)
        else:
            str_scheduleInfo += ' CALLBACK : '+repr(self.callback)
        str_scheduleInfo += ' CALLBACK ARGS : '+repr(self.callbackArgs)
        str_scheduleInfo += ' LOGGER : '+repr(self.logger)
        str_scheduleInfo += ' PROPS : '+repr(self.props)
        return str_scheduleInfo
    
    def __repr__(self):
        return repr(self.taskName)
    
    def getSchedulerName(self):
        return self.schedulerName
    
    def setSchedulerName(self, str_schedulerName):
        self.schedulerName = str_schedulerName
        
    def getTaskName(self):
        return self.taskName
    
    def setTaskName(self, taskName):
        self.taskName = taskName
        
    def getTime(self):
        return self.time
    
    def setTime(self, time):
        self.time = time
        
    def getTask(self):
        return self.task
    
    def setTask(self, task):
        self.task = task
        
    def getTaskArgs(self):
        return self.taskArgs
    
    def setTaskArgs(self, taskArgs):
        self.taskArgs = taskArgs
        
    def getCallback(self):
        return self.callback
    
    def setCallback(self, callback):
        self.callback = callback
        
    def getCallbackArgs(self):
        return self.callbackArgs
    
    def setCallbackArgs(self, callbackArgs):
        self.callbackArgs = callbackArgs
        
    def getIsPeriodic(self):
        return self.bool_isPeriodic
    
    def setIsPeriodic(self, bool_isPeriodic):
        self.bool_isPeriodic = bool_isPeriodic
        
    def getInterval(self):
        return self.interval
    
    def setInterval(self,interval):
        self.interval = interval
        
    def getLogger(self):
        return self.logger
    
    def setLogger(self,logger):
        self.logger = logger
        
    def getProps(self):
        return self.props
    
    def setProps(self,props):
        self.props = props
        

class Scheduler(threading.Thread): 
    def __init__(self, name, noOfWorkers):
        threading.Thread.__init__(self)
        self.name = name
        self.kill = False
        self.event = threading.Event()
        self.taskListLock = threading.Lock()
        self.readyTasksLock = threading.Lock()
        self.__list_workers = []
        self.__list_tasks = []#this list is a tuple containing (time, scheduleInfo)
        self.__list_readyTasks = []#this list is a tuple containing (time, scheduleInfo)
        self.__noOfWorkers = noOfWorkers
        self.__startWorkers()
        self.list_activeWorkers = []# mainly used to track whether there are any free workers before notifying. 
        self.schedulesToDelete = []
        self.activeSchedules = []
        
    @staticmethod
    def startScheduler(str_schedulerName, int_noOfWorkers=SCHEDULER_DEFAULT_WORKERS):
        global SCHEDULERS
        if str_schedulerName in SCHEDULERS:
            schdedulerObj = SCHEDULERS[str_schedulerName]
            schdedulerObj.stopScheduler()
            AgentLogger.log(AgentLogger.COLLECTOR,'stopping existing scheduler  --- {0}'.format(str_schedulerName))
        schedulerThreadObj = Scheduler(str_schedulerName, int_noOfWorkers)
        schedulerThreadObj.start()
        SCHEDULERS[str_schedulerName] = schedulerThreadObj
        #AgentLogger.log(AgentLogger.PLUGINS,'scheduler obj --- {0}'.format(SCHEDULERS))
        
    def __startWorkers(self):
        for i in range(self.__noOfWorkers):
            str_workerName = 'Worker '+str(i)
            worker = WorkerThread(self, str_workerName)
            worker.start()
            self.__list_workers.append(worker)      
            
    #Always removes duplicate schedule based on task name.     
    def scheduleTask(self, scheduleInfo):
        bool_deleteSchedule = False
        with self.taskListLock:
            int_duplicateScheduleIndex = None
            for index, (time, schInfo) in enumerate(self.__list_tasks):
                if schInfo.getTaskName() == scheduleInfo.getTaskName():
                    if scheduleInfo.createdTime > schInfo.createdTime:
                        int_duplicateScheduleIndex = index
                    else:
                        bool_deleteSchedule = True
            if not int_duplicateScheduleIndex == None:
                self.__list_tasks.pop(int_duplicateScheduleIndex)
            if not bool_deleteSchedule:
                self.__list_tasks.append((scheduleInfo.getTime(), scheduleInfo))      
                self.__list_tasks = sorted(self.__list_tasks,key=lambda x: x[0])#Sorting list based on the first item.
            else:
                AgentLogger.debug(AgentLogger.COLLECTOR,'Deleting the old schedule : '+str(scheduleInfo))
            AgentLogger.debug(AgentLogger.COLLECTOR,'List of tasks : '+repr(self.__list_tasks))
            
    def deleteScheduledTask(self, scheduleInfo):
        AgentLogger.log([ AgentLogger.COLLECTOR],'Deleting the schedule : '+repr(scheduleInfo))
        deletedSchedule = None
        with self.taskListLock:
           int_deleteScheduleIndex = None
           for index, (time, schInfo) in enumerate(self.__list_tasks):
               if schInfo.getTaskName() == scheduleInfo.getTaskName():
                   int_deleteScheduleIndex = index
           if not int_deleteScheduleIndex == None:
               AgentLogger.log(AgentLogger.COLLECTOR,'Schedule deleted successfully : '+repr(scheduleInfo))
               self.__list_tasks.pop(int_deleteScheduleIndex)
           else:
               AgentLogger.log(AgentLogger.COLLECTOR,'Unable to delete the schedule : '+repr(scheduleInfo))
               if (scheduleInfo.getTaskName() in self.activeSchedules) and (scheduleInfo.getTaskName() not in self.schedulesToDelete):
                   AgentLogger.log(AgentLogger.COLLECTOR,'Appending the schedule : '+repr(scheduleInfo)+' to schedules to be deleted list.')
                   self.schedulesToDelete.append(scheduleInfo.getTaskName())
               else:
                   AgentLogger.log(AgentLogger.COLLECTOR,repr(scheduleInfo.getTaskName())+' task is not present in active schedule list. Hence not including it in schedules to delete list')
               
    def getAvailableTasks(self):
        return self.__list_tasks[:]#Making a copy of the list
    
    def getTaskToExecute(self):        
        with self.readyTasksLock:
            #AgentLogger.log(AgentLogger.STDOUT,' ------------------------- self.__list_readyTasks : '+repr(self.__list_readyTasks))
            if self.__list_readyTasks:
                tuple_scheduleTask = self.__list_readyTasks.pop(0)
                if tuple_scheduleTask:                    
                    (taskTime, scheduleInfo) = tuple_scheduleTask
                    self.activeSchedules.append(scheduleInfo.getTaskName())
                return tuple_scheduleTask
            
    def run(self):
        while not self.kill:
            try:
                with self.taskListLock:
                    #print 'sch loop with lock '
                    if self.__list_tasks:
                        tuple_task = self.__list_tasks[0]  
                        if tuple_task[0] < time.time() and len(self.list_activeWorkers) < self.__noOfWorkers:
                            #print 'Current Time : '+str(time.time())+' Notify Worker For The Task :'+str(tuple_task)
                            with self.readyTasksLock:
                                tuple_readyTask = self.__list_tasks.pop(0)
                                #AgentLogger.log(AgentLogger.COLLECTOR,' Ready Task : '+str(tuple_readyTask[0])+'    '+str(tuple_readyTask[1]))
                                self.__list_readyTasks.append(tuple_readyTask)
                            self.event.set()
                            #AgentLogger.log(AgentLogger.STDOUT,' ============= EVENT CLEAR IS INVOKED ============= ')                            
                            self.event.clear()
            except Exception as e:
                AgentLogger.log([AgentLogger.COLLECTOR,AgentLogger.STDERR],' ************************* Exception while executing scheduler ************************* '+repr(e))
                traceback.print_exc()
            time.sleep(SCHEDULER_SLEEP_INTERVAL)
            
    def stopScheduler(self):
        self.kill = True
        self.event.set()    
    
    # Must be called only by worker threads
    @synchronized
    def validateAndReschedule(self, worker, taskTime, scheduleInfo):
        isPresentInDeleteList = scheduleInfo.getTaskName() in self.schedulesToDelete
        try:      
            if (worker in self.__list_workers) and not isPresentInDeleteList and (scheduleInfo.getIsPeriodic()):
                float_taskScheduleTime = taskTime + scheduleInfo.getInterval()
                scheduleInfo.setTime(float_taskScheduleTime)
                schedule(scheduleInfo)
            else:
                if isPresentInDeleteList:
                    AgentLogger.log(AgentLogger.COLLECTOR,'Schedules to delete : '+repr(self.schedulesToDelete))
                    AgentLogger.log(AgentLogger.COLLECTOR,'Not rescheduling the task : '+str(scheduleInfo.getTaskName())+' as it is present in schedules to delete.')
                    try:
                        self.schedulesToDelete.remove(scheduleInfo.getTaskName())
                    except ValueError:
                        pass
        except Exception as e:
            AgentLogger.log([scheduleInfo.getLogger(),AgentLogger.COLLECTOR,AgentLogger.STDERR],'************************* Exception while validating and rescheduling the task : '+repr(scheduleInfo)+' ************************* '+repr(e))
            traceback.print_exc()
        finally:
            try:
                self.activeSchedules.remove(scheduleInfo.getTaskName())
            except ValueError:
                pass
            

class WorkerThread(threading.Thread):    
    def __init__(self, scheduler, name):
        threading.Thread.__init__(self)
        self.__scheduler = scheduler
        self.name = name  
        
    def run(self):        
        while not self.__scheduler.kill:
            taskTime = None
            task = None
            taskArgs = None
            callback = None
            callbackArgs = None
            isPeriodic = None
            intervalInSec = None
            scheduleInfo = None
            try:
                self.__scheduler.event.wait(WORKER_WAIT_INTERVAL)
                self.__scheduler.list_activeWorkers.append(self.name)
                tuple_scheduleTask = self.__scheduler.getTaskToExecute()
                if tuple_scheduleTask:                    
                    (taskTime, scheduleInfo) = tuple_scheduleTask
                    taskTime = time.time()
                    props = scheduleInfo.getProps()
                    task = scheduleInfo.getTask()
                    taskArgs = scheduleInfo.getTaskArgs()
                    callback = scheduleInfo.getCallback()
                    callbackArgs = scheduleInfo.getCallbackArgs()
                    isPeriodic = scheduleInfo.getIsPeriodic()
                    intervalInSec = scheduleInfo.getInterval()
                    AgentLogger.debug([scheduleInfo.getLogger(),AgentLogger.COLLECTOR],'Executing scheduled task : '+str(scheduleInfo.getTaskName()))
                    # If there's nothing to do, just sleep                    
                    if task is None:
                        #print self.name+' No Action To Execute For The Task : '+repr(taskToExecute)
                        continue
                    elif callback is None:                        
                        if taskArgs is None:
                            task()
                        else:
                            task(taskArgs)
                        #print ' ========================= Task Completed By : ',self.name,' At : ',time.time(),' ========================= '
                    else:
                        if taskArgs is None:
                            if callbackArgs:
                                callback(callbackArgs, task())
                            else:
                                callback(task())
                        else:
                            callback(task(taskArgs))
                        AgentLogger.debug([scheduleInfo.getLogger(),AgentLogger.COLLECTOR],'Task : '+str(scheduleInfo.getTaskName())+' completed at : '+repr(time.time()))
                else:
                    pass
                    #print self.name+' No task to execute after notification'
            except Exception as e:
                AgentLogger.log([scheduleInfo.getLogger(),AgentLogger.COLLECTOR,AgentLogger.STDERR],'************************* Exception while executing the scheduled task : '+str(scheduleInfo)+' In The Worker Thread '+repr(self.name)+' ************************* '+repr(e))
                traceback.print_exc()
            finally:
                if scheduleInfo:
                    self.__scheduler.validateAndReschedule(self, taskTime, scheduleInfo)
                self.free()
                
    def free(self):
        # Informing scheduler that worker is free
        try:
            self.__scheduler.list_activeWorkers.remove(self.name)
        except ValueError:
            pass