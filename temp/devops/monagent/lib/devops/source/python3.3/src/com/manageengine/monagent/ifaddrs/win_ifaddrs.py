#$Id$
import winreg
from ctypes import Structure, windll, sizeof
from ctypes import POINTER, byref
from ctypes import c_ulong, c_uint, c_ubyte, c_char


MAX_ADAPTER_DESCRIPTION_LENGTH = 128
MAX_ADAPTER_NAME_LENGTH = 256
MAX_ADAPTER_ADDRESS_LENGTH = 8


class IP_ADDR_STRING(Structure):
    pass
IP_ADDR_STRING._fields_ = [
        ( "next",        POINTER(IP_ADDR_STRING) ),
        ( "ipAddress",   c_char * 16             ),
        ( "ipMask",      c_char * 16             ),
        ( "context",     c_ulong                 ),
    ]
LP_IP_ADDR_STRING = POINTER(IP_ADDR_STRING)


class IP_ADAPTER_INFO(Structure):
    pass
IP_ADAPTER_INFO._fields_ = [
        ("next",            POINTER(IP_ADAPTER_INFO)),
        ("comboIndex",      c_ulong),
        ("adapterName",     c_char * (MAX_ADAPTER_NAME_LENGTH + 4)),
        ("description",     c_char * (MAX_ADAPTER_DESCRIPTION_LENGTH + 4)),
        ("addressLength",   c_uint),
        ("address",         c_ubyte * MAX_ADAPTER_ADDRESS_LENGTH),
        ("index",           c_ulong),
        ("type",            c_uint),
        ("dhcpEnabled",     c_uint),
        ("currentIpAddress",    LP_IP_ADDR_STRING),
        ("ipAddressList",   IP_ADDR_STRING),
        ("gatewayList",     IP_ADDR_STRING),
        ("dhcpServer",      IP_ADDR_STRING),
        ("haveWins",        c_uint),
        ("primaryWinsServer",   IP_ADDR_STRING),
        ("secondaryWinsServer", IP_ADDR_STRING),
        ("leaseObtained",   c_ulong),
        ("leaseExpires",    c_ulong),]
LP_IP_ADAPTER_INFO = POINTER(IP_ADAPTER_INFO)



def getifaddrs():
    GetAdaptersInfo = windll.iphlpapi.GetAdaptersInfo
    GetAdaptersInfo.restype = c_ulong
    GetAdaptersInfo.argtypes = [LP_IP_ADAPTER_INFO, POINTER(c_ulong)]
    adapterList = (IP_ADAPTER_INFO * 10)()
    buflen = c_ulong(sizeof(adapterList))
    rc = GetAdaptersInfo(byref(adapterList[0]), byref(buflen))
    macs = {}
    if rc != 0:
        raise Exception('Winapi return code : '+str(rc))
    def decode_string(string):
        if isinstance(string, bytes):
            return string.decode()
        return string
    for a in adapterList:
        if not a.adapterName:
            continue
        name = decode_string(a.adapterName)
        desc = decode_string(a.description)
        macs[name] = data = {}
        data['desc'] = desc
        data['addr'] = ':'.join('%02x'%a.address[i] for i in range(a.addressLength))
        data['iplist'] = ips = []
        adNode = a.ipAddressList
        while True:
            ipAddr = adNode.ipAddress
            if ipAddr:
                ips.append(decode_string(ipAddr))
            adNode = adNode.__next__
            if not adNode:
                break
    # connection_key = "SYSTEM\\CurrentControlSet\\Control\\Network\\{4D36E972-E325-11CE-BFC1-08002BE10318}\\%s\\Connection"
    # access = winreg.KEY_QUERY_VALUE | winreg.KEY_WOW64_64KEY
    # for guid in list(macs):
    #     with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, connection_key%guid, access=access) as key:
    #         pnp_id, vtype = winreg.QueryValueEx(key, "PnpInstanceID")
    #         if not (isinstance(pnp_id, str) and pnp_id.lower().startswith('pci\\')):
    #             del(macs[guid])
    return macs

def filter_valid(macs):
    rv = []
    for v in list(macs.values()):
        if 'virtual' not in v['desc'].lower():
            rv.append(v['addr'])
    return rv


if __name__ == '__main__':
    print((getifaddrs()))
