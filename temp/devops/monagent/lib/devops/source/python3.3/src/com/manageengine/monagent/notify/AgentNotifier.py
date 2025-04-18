# $Id$
import threading
import traceback

from com.manageengine.monagent import AgentConstants
from com.manageengine.monagent.logger import AgentLogger
from com.manageengine.monagent.util import DesignUtils


# Pending : Synchronize methods which iterate self._listeners

class NotificationUtil(DesignUtils.Singleton):
    __notifiers = {}
    @classmethod
    def addNotifier(cls, key, value):
        if key and key not in cls.__notifiers:
            cls.__notifiers[key] = value
    @classmethod
    def getNotifier(cls, key):
        if key and key in cls.__notifiers:
            return cls.__notifiers[key]
    @classmethod
    def getNotifierList(self):
        return cls.__notifiers

class Notifier:

    def __init__(self, name=AgentConstants.NOTIFIER):
        self._notifierName = name
        self._listeners = []
        NotificationUtil.addNotifier(self._notifierName, self)
        
    def __eq__(self, obj): 
        return self._notifierName == obj.notifierName
    
    def __hash__(self): 
        return hash(id(self))
    
    @property
    def notifierName(self):
        return self._notifierName
    
    @property
    def listeners(self):
        return self._listeners
        
    def addListener(self, listener):
        if listener and listener not in self._listeners:
            self._listeners.append(listener)

    def deleteListener(self, listener):
        try:
            self._listeners.remove(listener)
        except ValueError:
            pass
    
    def notify(self, obj):
        for listener in self._listeners:
            AgentLogger.log( str(self._notifierName)+' notifying '+str(listener))
            listener.update(obj)
    
    def notify(self):
        for listener in self._listeners:
            AgentLogger.log( str(self._notifierName)+' notifying '+str(listener))
            listener.update()
            
    def getListenerCount(self):
        return len(self._listeners)

class Listener:
    def __init__(self, name, notifier):
        self._listenerName = name
        self._notifier = notifier
        notifier.addListener(self)
        
    def __eq__(self, obj):
        return self._listenerName == obj.listenerName
    
    def __hash__(self): 
        return hash(id(self))
    
    @property
    def listenerName(self):
        return self._listenerName
    
    def update(self, notifier, arg):
        raise NotImplementedError(self._listenerName + ' should implement update()')

    def update(self):
        raise NotImplementedError(self._listenerName + ' should implement update()')
    
class ShutdownNotifier(DesignUtils.Singleton, Notifier):
    def __init__(self):
        Notifier.__init__(self,AgentConstants.SHUTDOWN_NOTIFIER)
        
    def register(self):
        AgentLogger.log([AgentLogger.STDOUT],'Registering for shutdown notification')
        signal.signal(signal.SIGTERM, AgentUtil.shutdownAgent)
        signal.signal(signal.SIGINT, AgentUtil.shutdownAgent)
         
        
class ShutdownListener(Listener):
    def __init__(self):
        self._shutdown = False
        Listener.__init__(self,AgentConstants.SHUTDOWN_LISTENER, NotificationUtil.getNotifier(AgentConstants.SHUTDOWN_NOTIFIER))
        
    def update(self):
        self._shutdown = True
        

class AgentShutdownListener(ShutdownListener):
    def __init__(self):
        pass
        
class UdpPacketListener(Listener):
    def __init__(self):
        Listener.__init__(self,AgentConstants.UDP_PACKET_LISTENER, NotificationUtil.getNotifier(AgentConstants.UDP_NOTIFIER))
        
    def update(self):
        self.processPacket()
        
    def processPacket(self):
        try:
            AgentLogger.log(AgentLogger.UDP, 'Processing UDP packet')
        except Exception as e:
            AgentLogger.log([AgentLogger.UDP,AgentLogger.STDERR], ' *************************** Exception while processing UDP packet *************************** '+ repr(e))
            traceback.print_exc()
            
    def onServerStarted(self, udpServerObj):
        raise NotImplementedError
    
    def onServerStopped(self, udpServerObj):
        raise NotImplementedError
    
    def onReceivedPacket(self, udpServerObj, datagramPkt):
        raise NotImplementedError
    
    def onSentPacket(self, udpServerObj, datagramPkt):
        raise NotImplementedError
    
    def onException(self, udpServerObj, exceptionObj):
        raise NotImplementedError
        
#def main():
#    pass
            
#main()
