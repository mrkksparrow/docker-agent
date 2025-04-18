'''
Created on 09-Nov-2016
@author: giri
'''
import re, time, json, os

import os, sys, tempfile


class SingleInstance:
    def __init__(self):
        self.lockfile = os.path.normpath(tempfile.gettempdir() + '/' +
                                         os.path.splitext(os.path.abspath(__file__))[0].replace("/", "-").replace(":",
                                                                                                                  "").replace(
                                             "\\", "-") + '.lock')
        if sys.platform == 'win32':
            try:
                global single
                if os.path.exists(self.lockfile):
                    os.unlink(self.lockfile)
                self.fd = os.open(self.lockfile, os.O_CREAT | os.O_EXCL | os.O_RDWR)
            except OSError as e:
                if e.errno == 13:
                    raise e
        else:
            import fcntl
            self.fp = open(self.lockfile, 'w')
            try:
                fcntl.lockf(self.fp, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except IOError as e:
                raise e

    '''def __del__(self):
        if sys.platform == 'win32':
            if hasattr(self, 'fd'):
                os.close(self.fd)
                os.unlink(self.lockfile)'''