#$Id$
import socket

from sys import platform
if platform.startswith('win'):
    from com.manageengine.monagent.ifaddrs.win_ifaddrs import getifaddrs as _getifaddrs, filter_valid
elif platform.startswith('linux'):
    from com.manageengine.monagent.ifaddrs.linux_ifaddrs import getifaddrs as _getifaddrs, filter_valid
else:
    from com.manageengine.monagent.ifaddrs.osx_ifaddrs import getifaddrs as _getifaddrs, filter_valid


def getifaddrs():
    try:
        return _getifaddrs()
    except Exception:
        return {}


def get_active_ifaddr():
    current_ip = socket.gethostbyname(socket.getfqdn())
    ifaddrs = getifaddrs()
    for _, info in list(ifaddrs.items()):
        if current_ip in info['iplist']:
            return info['addr']
    return None

def format_ifaddr(mac):
    return mac and str(int(mac.replace(':',''), 16))

def get_all_macs():
    try:
        macs = _getifaddrs()
    except Exception as e:
        print(' ************************* Exception While executing get_all_macs ************************* '+repr(e))
        traceback.print_exc()        
        return []
    return list(map(format_ifaddr, filter_valid(macs)))
