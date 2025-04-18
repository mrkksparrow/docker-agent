'''
Created on 03-Nov-2016
@author: giri
'''
import traceback, sys
from functools import wraps

def helper(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
       try:
           func_call = func(*args, **kwargs)
       except Exception as e:
           traceback.print_exc()
    return wrapper
