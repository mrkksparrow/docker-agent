'''
Created on 08-May-2017
@author: giri
'''

from com.manageengine.monagent.remoteinstaller import Constant
import time
import sys

def spinning_cursor():
  while True:
    if Constant.PRINT_DOWNLOAD_DATA:
        time.sleep(1)
        continue
    
    if Constant.PRINT_SSH_DATA:
        sys.stdout.write("\r  ")
        sys.stdout.write("\r")
        sys.stdout.flush()
        print(Constant.PRINT_SSH_DATA[0])
        del Constant.PRINT_SSH_DATA[0]
        time.sleep(0.5)
        continue
    else:
        for cursor in '\\|/-':
        #for cursor in ['.', '..', '...' '....', '.....']:
          time.sleep(0.5)
          sys.stdout.write("\r {}" .format(cursor))
          sys.stdout.flush()