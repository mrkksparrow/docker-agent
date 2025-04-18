# $Id$
import threading
class Singleton:
    _instance = None
    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = object.__new__(cls, *args, **kwargs)
        return cls._instance
    
    
def synchronized(func):    
    func.__lock__ = threading.Lock()        
    def synced_func(*args, **kws):
        with func.__lock__:
            return func(*args, **kws)
    return synced_func
    
# class A(Singleton):
#     def __init__(self):
#         pass
#     
# class B(Singleton):
#     def __init__(self):
#         pass
#     
# def main():
#     a = A()
#     b = B()
#     a1 = A()
#     print (id(a),a)
#     print (id(b),b)
#     print (id(a1),a1)
#     
#     
# main()
