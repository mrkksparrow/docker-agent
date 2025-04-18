#$Id$
from ctypes import (
    Structure, Union, CDLL, pointer,
    c_ushort, c_char, c_void_p, c_char_p,
    c_uint, c_uint8, c_uint16, c_uint32
)
from ctypes.util import find_library
from socket import AF_INET, inet_ntop

try:
    from socket import AF_PACKET
except ImportError:
    AF_PACKET = 18


class ifaddrs(Structure):
    _fields_ = [
        ( "ifa_next",    c_void_p  ),
        ( "ifa_name",    c_char_p  ),
        ( "ifa_flags",   c_uint    ),
        ( "ifa_addr",    c_void_p  ),
        ( "ifa_netmask", c_void_p  ),
        ( "ifa_dstaddr", c_void_p  ),
        ( "ifa_data",    c_void_p  ),
    ]


# AF_UNKNOWN / generic
class sockaddr(Structure):
    _fields_ = [
        ( "sa_len",     c_uint8 ),
        ( "sa_family",  c_uint8 ),
        ( "sa_data",    (c_uint8 * 14) ),
    ]


# AF_INET / IPv4
class in_addr(Union):
    _fields_ = [
        ("s_addr", c_uint32),
    ]

class sockaddr_in(Structure):
    _fields_ = [
        ("sin_len",    c_uint8),
        ("sin_family", c_uint8),
        ("sin_port",   c_ushort),
        ("sin_addr",   in_addr),
        ("sin_zero",   (c_char * 8) ), # padding
    ]


# AF_INET6 / IPv6
class in6_u(Union):
    _fields_ = [
        ("u6_addr8",  (c_uint8 * 16) ),
        ("u6_addr16", (c_uint16 * 8) ),
        ("u6_addr32", (c_uint32 * 4) ),
    ]

class in6_addr(Union):
    _fields_ = [
        ("in6_u", in6_u),
    ]

class sockaddr_in6(Structure):
    _fields_ = [
        ("sin6_len",      c_uint8  ),
        ("sin6_family",   c_uint8  ),
        ("sin6_port",     c_ushort ),
        ("sin6_flowinfo", c_uint32 ),
        ("sin6_addr",     in6_addr ),
        ("sin6_scope_id", c_uint32 ),
    ]


# AF_PACKET / OSX
class sockaddr_dl(Structure):
    _fields_ = [
        ("sdl_len",      c_uint8  ),
        ("sdl_family",   c_uint8  ),
        ("sdl_index",    c_uint16 ),
        ("sdl_type",     c_uint8  ),
        ("sdl_nlen",     c_uint8  ),
        ("sdl_alen",     c_uint8  ),
        ("sdl_slen",     c_uint8  ),
        ("sdl_data",     (c_uint8 * 12)), 
    ]


def getifaddrs():
    _libc = CDLL(find_library('c'))
    ptr = c_void_p(None)
    result = _libc.getifaddrs(pointer(ptr))
    if result:
        return {}
    ifa = ifaddrs.from_address(ptr.value)
    macs = {}
 
    while True:
        name = ifa.ifa_name.decode('UTF-8') # use this for python3
 
        if name not in macs:
            macs[name] = {}
            macs[name]['iplist'] = []
        data = macs[name]
        ips  = data['iplist']
 
        sa = sockaddr.from_address(ifa.ifa_addr)
 
        if sa.sa_family == AF_INET:
            if ifa.ifa_addr is not None:
                si = sockaddr_in.from_address(ifa.ifa_addr)
                ips.append(inet_ntop(si.sin_family, si.sin_addr))
            #if ifa.ifa_netmask is not None:
            #    si = sockaddr_in.from_address(ifa.ifa_netmask)
            #    data['netmask'] = inet_ntop(si.sin_family, si.sin_addr)
 
        #if sa.sa_family == AF_INET6:
        #    if ifa.ifa_addr is not None:
        #        si = sockaddr_in6.from_address(ifa.ifa_addr)
        #        ips.append(inet_ntop(si.sin6_family, si.sin6_addr))
        #        if data['addr'].startswith('fe80:'):
        #            data['scope'] = si.sin6_scope_id
        #    if ifa.ifa_netmask is not None:
        #        si = sockaddr_in6.from_address(ifa.ifa_netmask)
        #        data['netmask'] = inet_ntop(si.sin6_family, si.sin6_addr)
 
        if sa.sa_family == AF_PACKET:
            if ifa.ifa_addr is not None:
                si = sockaddr_dl.from_address(ifa.ifa_addr)
                data['addr'] = ":".join('%02x'%(si.sdl_data[i])
                                        for i in range(si.sdl_nlen, si.sdl_nlen+si.sdl_alen))
 
        #if len(data) > 0:
        #    macs[name][sa.sa_family].append(data)
 
        if ifa.ifa_next:
            ifa = ifaddrs.from_address(ifa.ifa_next)
        else:
            break
 
    _libc.freeifaddrs(ptr)
    return macs

def filter_valid(macs):
    rv = []
    for k, v in list(macs.items()):
        if k.startswith('en'):
            rv.append(v['addr'])
    return rv

if __name__ == '__main__':
    print((getifaddrs()))

# ref links
# http://web.mit.edu/macdev/Development/MITSupportLib/SocketsLib/Documentation/structures.html
