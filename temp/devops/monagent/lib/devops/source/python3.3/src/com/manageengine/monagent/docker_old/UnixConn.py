#$Id$
'''
Created on 21-Jan-2015

@author: root
'''

import os
import socket
try:
    from http.client import HTTPConnection
except Exception as e:
    from httplib import HTTPConnection

from six.moves.urllib.request import Request

try:
    from urllib.request import AbstractHTTPHandler
except Exception as e:
    from urllib2 import AbstractHTTPHandler

from six.moves.urllib.parse import urlsplit

DEFAULT_TIME_OUT = 5

class UnixHTTPConnection(HTTPConnection):
    sock_timeout = DEFAULT_TIME_OUT
    def __init__(self, unix_sock):
        self._unix_sock = unix_sock
        
    def connect(self):
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.connect(self._unix_sock)
        sock.settimeout(self.sock_timeout)
        self.sock = sock
        
    def __call__(self, *args, **kwargs):
        HTTPConnection.__init__(self, *args, **kwargs)
        return self
    
class UnixConnectionHandler(AbstractHTTPHandler):
  
    def unix_open(self, req):
        try:
            full_url = req.get_full_url()
            url_path = "%s%s" % urlsplit(full_url)[1:3] 
            path = os.sep
            for part in url_path.split("/"):
                path = os.path.join(path,part)
                if not os.path.exists(path) :
                    break
                unix_sock = path
            
            new_req = Request(full_url.replace(unix_sock, "/localhost"), req.data, dict(req.header_items()))
            new_req.method = req.method
            new_req.timeout = req.timeout
            resp = self.do_open(UnixHTTPConnection(unix_sock), new_req)
        except Exception:
            #print("Exception in unix_open")
            return None
        return resp
