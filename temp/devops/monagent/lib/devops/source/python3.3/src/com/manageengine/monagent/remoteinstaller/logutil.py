'''
Created on 25-Oct-2016
@author: giri
'''
import logging
import os
import time

from com.manageengine.monagent.remoteinstaller import Constant
import logging.handlers as handlers


class SizedTimedRotatingFileHandler(handlers.TimedRotatingFileHandler):
    """
    Handler for logging to a set of files, which switches from one file
    to the next when the current file reaches a certain size, or at certain
    timed intervals
    """
    def __init__(self, filename, mode='a', maxBytes=0, backupCount=0, encoding=None,
                 delay=0, when='h', interval=1, utc=False):
        # If rotation/rollover is wanted, it doesn't make sense to use another
        # mode. If for example 'w' were specified, then if there were multiple
        # runs of the calling application, the logs from previous runs would be
        # lost if the 'w' is respected, because the log file would be truncated
        # on each run.
        if maxBytes > 0:
            mode = 'a'
        handlers.TimedRotatingFileHandler.__init__(
            self, filename, when, interval, backupCount, encoding, delay, utc)
        self.maxBytes = maxBytes
    def shouldRollover(self, record):
        """
        Determine if rollover should occur.
        Basically, see if the supplied record would cause the file to exceed
        the size limit we have.
        """
        if self.stream is None:                 # delay was set...
            self.stream = self._open()
        if self.maxBytes > 0:                   # are we rolling over?
            msg = "%s\n" % self.format(record)
            self.stream.seek(0, 2)  #due to non-posix-compliant Windows feature
            if self.stream.tell() + len(msg) >= self.maxBytes:
                return 1
        t = int(time.time())
        if t >= self.rolloverAt:
            return 1
        return 0

def register(name, logfile):
    if 'name' in Constant.LOGGER_DICT:
        print(logfile+" logger is already registered")
        return
    log_filename=logfile
    logger=logging.getLogger(name)
    logger.setLevel(logging.INFO)
    handler=SizedTimedRotatingFileHandler(
        log_filename, maxBytes=1048576000, backupCount=10
        )
    handler.suffix = '%Y-%m-%d_%H-%M-%S'
    formatter = logging.Formatter('%(asctime)s %(threadName)s, %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    needRoll = os.path.isfile(logfile)
    if needRoll and os.stat(logfile).st_size > 0:
        logger.handlers[0].doRollover()
    Constant.LOGGER_DICT[name] = logger
    return logger

def Logger(name):
    return Constant.LOGGER_DICT[name] if name in Constant.LOGGER_DICT else None
    

