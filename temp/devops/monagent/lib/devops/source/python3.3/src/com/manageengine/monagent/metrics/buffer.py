# $Id$

import logging
from collections import deque

from com.manageengine.monagent.metrics import metrics_constants
from com.manageengine.monagent.metrics import metrics_logger

BUFFERS = {}

def get_buffer(str_bufferName, maxlength=None):
    if str_bufferName in BUFFERS:
        return BUFFERS[str_bufferName]
    else:
        return __createBuffer(str_bufferName, maxlength)
    
def __createBuffer(str_bufferName, maxlength=None):
    var_buffer = DequeBuffer(maxlen=maxlength)
    BUFFERS[str_bufferName] = var_buffer
    return var_buffer

class DequeBuffer(deque):
    def __init__(self, iterable=(), maxlen=None):     
        deque.__init__(self, iterable, maxlen)
        
    def add(self, value):
        if len(self) ==self.maxlen:
            metrics_logger.log('=========MAX BUFFER LENGTH REACHED!!!DISCARDING... {}'.format(str(self.popleft())))
            #discarded element to be processed here. FIFO verified by above log.
        self.append(value)
    
    def size(self):
        return len(self)
    
    def isEmpty(self):
        return len(self) == 0

def cleanUp():
    for buffer_key in list(BUFFERS.keys()):
        BUFFERS[buffer_key].clear()