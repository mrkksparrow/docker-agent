'''
Created on 03-Nov-2016
@author: giri
'''
class StreamToLogger(object):
   """
   Fake file-like stream object that redirects writes to a logger instance.
   """
   def __init__(self, logger):
       self.logger = logger

   def write(self, buf):
       self.logger.warning(buf.strip())

   def flush(self):
       pass