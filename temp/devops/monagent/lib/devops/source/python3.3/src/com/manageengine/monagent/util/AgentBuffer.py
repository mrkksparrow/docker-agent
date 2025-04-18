# $Id$
from com.manageengine.monagent.logger import AgentLogger
from collections import deque

BUFFERS = {}

def getBuffer(str_bufferName, maxlength=None):
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
            AgentLogger.log(AgentLogger.STDOUT,'=========MAX BUFFER LENGTH REACHED!!!DISCARDING...'+str(self.popleft()))
            #discarded element to be processed here. FIFO verified by above log.
        self.append(value)
    
    def size(self):
        return len(self)
    
    def isEmpty(self):
        return len(self) == 0

def cleanUp():
    for buffer_key in list(BUFFERS.keys()):
        BUFFERS[buffer_key].clear()
      
def main():
    buff = __createBuffer('test', 2)
    buff1 = __createBuffer('test1')
    buff.add('a')
    buff.add('b')
    buff.add('c')
    if 'a' in buff:        
        print('Buffer : ',buff)
    for i in range(1,10):
        buff.add(i)
        print('Buffer : ',buff)
    print('Buffer length : ',len(buff))
    print('Buffer pop : ',buff.pop())
    print('Buffer size : ',buff1.size())
    print('Buffer is empty : ',buff1.isEmpty())
    
        
#main()