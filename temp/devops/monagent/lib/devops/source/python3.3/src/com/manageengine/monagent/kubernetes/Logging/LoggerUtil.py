import sys
import logging
import logging.handlers
import traceback
import xml.etree.ElementTree as xml

def initialize_cluster_agent_logging(str_logConfFilePath, str_logDirectory):
    global LOG_DIR
    LOG_DIR = str_logDirectory
    # cleanUpLogs()
    dict_logInfo = loadXml(str_logConfFilePath)
    # print 'dict_logInfo',dict_logInfo
    if dict_logInfo['LoggingConfig']['Attributes']['redirectStd'].lower() == 'true':
        # print 'redirecting std'
        sys.stdout = LogToFile('STDERR')
        sys.stderr = LogToFile('STDERR')
    for dict_logger in dict_logInfo['LoggingConfig']['Details']:
        # print dict_logger
        str_logName = dict_logger['name']
        logInfo = LogInfo()
        logInfo.setLogName(str_logName)
        if 'parent' in dict_logger:
            logInfo.setLogFileName(dict_logger['fileName'], parent=True)
            logInfo.setLogFormat('%(asctime)s  %(message)s')
        else:
            logInfo.setLogFileName(dict_logger['fileName'])
        logInfo.setLogFileCount(dict_logger['fileCount'])
        logInfo.setLogLevel(dict_logger['level'])
        logInfo.setLogFileSize(dict_logger['fileSize'])
        setattr(sys.modules[__name__], logInfo.getLogName(), logInfo.getLogName())  # Setting module level constants.
        createLogger(logInfo)

def createLogger(logInfo):
    logger = logging.getLogger(logInfo.getLogName())
    hdlr = logging.handlers.RotatingFileHandler(logInfo.getLogFilePath(), maxBytes=logInfo.getLogFileSize(),
                                                backupCount=logInfo.getLogFileCount())
    formatter = logging.Formatter(logInfo.getLogFormat())
    hdlr.setFormatter(formatter)
    logger.addHandler(hdlr)
    setLevel(logInfo.getLogName(), logInfo.getLogLevel())

def setLevel(str_logName, int_level):
    int_level *= 10
    logger = logging.getLogger(str_logName)
    if int_level == logging.DEBUG:
        logger.setLevel(logging.DEBUG)
    elif int_level == logging.INFO:
        logger.setLevel(logging.INFO)
    elif int_level == logging.WARN:
        logger.setLevel(logging.WARN)
    elif int_level == logging.ERROR:
        logger.setLevel(logging.ERROR)
    elif int_level == logging.CRITICAL:
        logger.setLevel(logging.CRITICAL)

def log(loggerName, message, encrypt=False):
    try:
        if type(loggerName) is list:
            for logName in loggerName:
                logger = logging.getLogger(logName)
                logger.warning(message)
        else:
            logger = logging.getLogger(loggerName)
            logger.warning(message)
    except Exception as e:
        traceback.print_exc()

def debug(loggerName, message):
    try:
        if type(loggerName) is list:
            for logName in loggerName:
                logger = logging.getLogger(logName)
                logger.debug(message)
        else:
            logger = logging.getLogger(loggerName)
            logger.debug(message)
    except Exception as e:
        traceback.print_exc()

def loadXml(str_fileName):
    dict_toReturn = {}
    try:
        tree = xml.parse(str_fileName)
        str_rootNode = None

        def hasChildTags(node):
            if len(list(node)) > 0:
                return True
            else:
                return False

        def getChildTags(node):
            list_childTags = []
            if len(list(node)) > 0:
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

def shutdown():
    logging.shutdown()

class LogInfo(object):
    def __init__(self):
        self.str_logName = None
        self.str_logFileName = None
        self.str_logFilePath = None
        self.int_logFileSize = 2000000
        self.int_logFileCount = 3
        self.int_logLevel = 3
        self.str_logFormat = '%(asctime)s   %(threadName)s, %(message)s'

    def __str__(self):
        str_logInfo = ''
        str_logInfo += 'LOG NAME : ' + repr(self.str_logName)
        str_logInfo += ' LOG FILE NAME : ' + repr(self.str_logFileName)
        str_logInfo += ' LOG FILE SIZE : ' + repr(self.int_logFileSize)
        str_logInfo += ' LOG FILE COUNT : ' + repr(self.int_logFileCount)
        str_logInfo += ' LOG LEVEL : ' + repr(self.int_logLevel)
        return str_logInfo

    def getLogName(self):
        return self.str_logName

    def setLogName(self, str_logName):
        self.str_logName = str(str_logName)

    def getLogFileName(self):
        return self.str_logFileName

    def setLogFileName(self, str_logFileName, parent=False):
        if parent:
            self.str_logFileName = str(str_logFileName)
            self.str_logFilePath = LOG_DIR + '/' + self.str_logFileName + '.txt'
        else:
            self.str_logFileName = str(str_logFileName)
            self.str_logFilePath = LOG_DIR + '/details/' + self.str_logFileName + '.txt'

    def getLogFilePath(self):
        return self.str_logFilePath

    def setLogFilePath(self, str_logFilePath):
        self.str_logFilePath = str(str_logFilePath)

    def getLogFileSize(self):
        return self.int_logFileSize

    def setLogFileSize(self, int_logFileSize):
        self.int_logFileSize = int(int_logFileSize)

    def getLogFileCount(self):
        return self.int_logFileCount

    def setLogFileCount(self, int_logFileCount):
        self.int_logFileCount = int(int_logFileCount)

    def getLogLevel(self):
        return self.int_logLevel

    def setLogLevel(self, int_logLevel):
        self.int_logLevel = int(int_logLevel)

    def getLogFormat(self):
        return self.str_logFormat

    def setLogFormat(self, str_logFormat):
        self.str_logFormat = str(str_logFormat)

class LogToFile(object):
    def __init__(self, name=None):
        self.loggerName = name

    def write(self, msg):
        log(self.loggerName, repr(msg))

    def flush(self):
        pass