#$Id$
import traceback
from ctypes import (
    Structure, Union, CDLL, pointer,
    c_ushort, c_char, c_void_p, c_char_p, c_uint, c_uint8, c_uint16, c_uint32, c_short
)
from ctypes.util import find_library
from socket import AF_INET, AF_INET6, AF_PACKET, inet_ntop


class ifa_ifu_u(Union):
    _fields_ = [ 
        ( "ifu_broadaddr", c_void_p ),
        ( "ifu_dstaddr",   c_void_p )  
    ]

class ifaddrs(Structure):
    _fields_ = [
        ( "ifa_next",    c_void_p  ),
        ( "ifa_name",    c_char_p  ),
        ( "ifa_flags",   c_uint    ),
        ( "ifa_addr",    c_void_p  ),
        ( "ifa_netmask", c_void_p  ),
        ( "ifa_ifu",     ifa_ifu_u ),
        ( "ifa_data",    c_void_p  ) 
    ]


# AF_UNKNOWN / generic
class sockaddr(Structure):
    _fields_ = [
        ( "sa_family", c_uint16 ),
        ( "sa_data",   (c_uint8 * 14) ) 
    ]


# AF_INET / IPv4
class in_addr(Union):
    _fields_ = [
        ("s_addr", c_uint32),
    ]

class sockaddr_in(Structure):
    _fields_ = [
        ("sin_family", c_short),
        ("sin_port",   c_ushort),
        ("sin_addr",   in_addr),
        ("sin_zero",   (c_char * 8) ), # padding
    ]


# AF_INET6 / IPv6
class in6_u(Union):
    _fields_ = [
        ("u6_addr8",  (c_uint8 * 16) ),
        ("u6_addr16", (c_uint16 * 8) ),
        ("u6_addr32", (c_uint32 * 4) )
    ]

class in6_addr(Union):
    _fields_ = [
        ("in6_u", in6_u),
    ]

class sockaddr_in6(Structure):
    _fields_ = [
        ("sin6_family",      c_short),
        ("sin6_port",     c_ushort),
        ("sin6_flowinfo", c_uint32),
        ("sin6_addr",     in6_addr),
        ("sin6_scope_id", c_uint32),
    ]


# AF_PACKET / Linux
class sockaddr_ll(Structure):
    _fields_ = [
        ("sll_family",   c_uint16 ),
        ("sll_protocol", c_uint16 ),
        ("sll_ifindex",  c_uint32 ),
        ("sll_hatype",   c_uint16 ),
        ("sll_pktype",   c_uint8  ),
        ("sll_halen",    c_uint8  ),
        ("sll_addr",     (c_uint8 * 8) ) 
    ]


def getifaddrs():
    result = {}
    try:
        _libc = CDLL('libc.so.6')
        ptr = c_void_p(None)
        result = _libc.getifaddrs(pointer(ptr))
        if result:
            return {}
        ifa = ifaddrs.from_address(ptr.value)
        #macs = {}
        result = {}
        while True:
            name = ifa.ifa_name.decode('UTF-8') # use this for python3
            
            
            if name not in result:
                result[name] = {} 
            try:
                sa = sockaddr.from_address(ifa.ifa_addr)
         
                if sa.sa_family not in result[name]:
                    result[name][sa.sa_family] = {}
         
                data = {}
                
                
                '''if name not in macs:
                    macs[name] = {}
                    macs[name]['iplist'] = []
                data = macs[name]
                ips  = data['iplist']
         
                sa = sockaddr.from_address(ifa.ifa_addr)'''
         
                if sa.sa_family == AF_INET:
                    if ifa.ifa_addr is not None:
                        si = sockaddr_in.from_address(ifa.ifa_addr)
                        data['addr'] = inet_ntop(si.sin_family, si.sin_addr)
                    #if ifa.ifa_netmask is not None:
                    #    si = sockaddr_in.from_address(ifa.ifa_netmask)
                    #    data['netmask'] = inet_ntop(si.sin_family, si.sin_addr)
         
                if sa.sa_family == AF_INET6:
                    if ifa.ifa_addr is not None:
                        si = sockaddr_in6.from_address(ifa.ifa_addr)
                        data['addr'] = inet_ntop(si.sin6_family, si.sin6_addr)
                        if data['addr'].startswith('fe80:'):
                            data['scope'] = si.sin6_scope_id
                #    if ifa.ifa_netmask is not None:
                #        si = sockaddr_in6.from_address(ifa.ifa_netmask)
                #        data['netmask'] = inet_ntop(si.sin6_family, si.sin6_addr)
         
                if sa.sa_family == AF_PACKET:
                    if ifa.ifa_addr is not None:
                        si = sockaddr_ll.from_address(ifa.ifa_addr)
                        data['addr'] = ":".join('%02x'%si.sll_addr[i] for i in range(si.sll_halen))
         
                if len(data) > 0:
                    result[name][sa.sa_family] = data
            except Exception as e:
                traceback.print_exc()
            if ifa.ifa_next:
                ifa = ifaddrs.from_address(ifa.ifa_next)
            else:
                break
     
        _libc.freeifaddrs(ptr)
        #return result
    
    except Exception as e:
        traceback.print_exc()
        
    
    return result

def filter_valid(macs):
    rv = []
    for k, v in list(macs.items()):
        if k.startswith('eth') or k.startswith('wlan'):
            rv.append(v['addr'])
    return rv

if __name__ == '__main__':
    print((getifaddrs()))

