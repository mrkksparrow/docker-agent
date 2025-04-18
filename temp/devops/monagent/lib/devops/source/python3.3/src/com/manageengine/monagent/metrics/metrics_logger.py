# $Id$
import sys 
import os
import traceback
import logging
import logging.handlers as handlers
import xml.etree.ElementTree as xml

from com.manageengine.monagent.metrics import metrics_constants

def initialize():
    logInfo = {}
    dict_logInfo = loadXml(metrics_constants.AGENT_LOGGING_CONF_FILE)
    for dict_logger in dict_logInfo['LoggingConfig']['Details']:
        if (dict_logger['name'].upper()) == "METRICS":
            logInfo = dict_logger
    create_logger(logInfo)

def loadXml(str_fileName):
    dict_toReturn = {}
    try:         
        tree = xml.parse(str_fileName)
        str_rootNode = None
        def hasChildTags(node):
            if len(list(node))>0:
                return True
            else:
                return False
        def getChildTags(node):
            list_childTags = []
            if len(list(node))>0:
                for elem in list(node):                    
                    list_childTags.append(elem.tag)
            return list_childTags
        str_parentTag = None    
        for node in tree.iter():            
            if 'RootTag' not in dict_toReturn:
                str_rootNode = node.tag
                dict_toReturn['RootTag'] = str_rootNode
                dict_toReturn['RootAttributes'] = node.attrib
                dict_toReturn['ChildTags'] = getChildTags(node)                
            else:
                list_childTags = dict_toReturn['ChildTags']
                if node.tag in list_childTags and node.tag not in dict_toReturn:
                    dict_toReturn[node.tag] = {}
                    dict_toReturn[node.tag]['Attributes'] = node.attrib
                    dict_toReturn[node.tag]['Details'] = []
                    str_parentTag = node.tag
                elif node.attrib:
                    dict_toReturn[str_parentTag]['Details'].append(node.attrib)            
    except Exception as e:
        traceback.print_exc()
        dict_toReturn = None
    return dict_toReturn

def create_logger(logInfo):
	logger = None
	try:
		logpath=metrics_constants.METRICS_LOG_PATH
		if not os.path.exists(logpath):
			os.makedirs(logpath)
		sys.stdout = LogToFile(metrics_constants.METRICS_LOGGER_NAME)
		sys.stderr = LogToFile(metrics_constants.METRICS_LOGGER_NAME)
		logger=logging.getLogger(metrics_constants.METRICS_LOGGER_NAME)
		logger.setLevel(logging.INFO)
		loghandler = handlers.RotatingFileHandler(logpath+'/'+metrics_constants.METRICS_FILE,maxBytes=int(logInfo['fileSize']), backupCount=int(logInfo['fileCount']))
		loghandler.setLevel(logging.INFO)
		formatter=logging.Formatter('%(asctime)s  -%(name)s  - %(levelname)s  -  %(message)s ','%Y-%m-%d %I:%M:%S %p')
		loghandler.setFormatter(formatter)
		logger.addHandler(loghandler)
		if str(logInfo['level']) == "1":
			metrics_constants.DEBUG_MODE = True
	except Exception as e:
		traceback.print_exc()
		
def log(message):
    try:
        logger = logging.getLogger(metrics_constants.METRICS_LOGGER_NAME)
        logger.info(message)
    except Exception as e:        
        traceback.print_exc()

def debug(message):
    try:
        if metrics_constants.DEBUG_MODE:
            logger = logging.getLogger(metrics_constants.METRICS_LOGGER_NAME)
            logger.info(message)
    except Exception as e:        
        traceback.print_exc()

def errlog(message):
	try:
		logger = logging.getLogger(metrics_constants.METRICS_LOGGER_NAME)
		logger.error(message)
	except Exception as e:
		traceback.print_exc()

def warnlog(message):
	try:
		logger = logging.getLogger(metrics_constants.METRICS_LOGGER_NAME)
		logger.warning(message)
	except Exception as e:
		traceback.print_exc()
      
class LogToFile(object):    
    def __init__(self, name=None):        
        self.loggerName = name

    def write(self, msg):
        log(repr(msg))

    def flush(self):
        pass
