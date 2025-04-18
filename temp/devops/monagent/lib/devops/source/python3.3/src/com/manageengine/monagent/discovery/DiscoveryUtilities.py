# $Id$
import AgentUtil

def getHostDetails():
    dict_hostDetails = {}
    str_macAddress = None
    str_ipAddress = None
    str_diskDetailsCommand = '/sbin/ifconfig -a'
    (bool_isSuccess,str_Output) = AgentUtil.executeCommand(str_diskDetailsCommand)
    AgentLogger.log(AgentLogger.STDOUT,'Is Success : '+str(bool_isSuccess))
    AgentLogger.log(AgentLogger.STDOUT,'output : '+str_Output)
    if bool_isSuccess:
        list_OutputLines = str_Output.split('\n')
        #print 'list_OutputLines : ',list_OutputLines
        for str_OutputLine in list_OutputLines:
            if str_macAddress == None:
                int_ethernet0Index = str_OutputLine.find('eth0')
                if not int_ethernet0Index == -1:
                    str_macAddress = str_OutputLine[str_OutputLine.find('HWaddr')+6 :].strip()                            
                    AgentLogger.log(AgentLogger.STDOUT,'Mac address : '+str_macAddress)
                    dict_hostDetails['macAddress'] = str_macAddress
                    continue
            if not str_macAddress == None and str_ipAddress == None:                
                int_inetAddrIndex = str_OutputLine.find('inet addr:')
                if not int_inetAddrIndex == -1:
                    str_ipAddress = str_OutputLine[int_inetAddrIndex+10 :].split()[0]
                    AgentLogger.log(AgentLogger.STDOUT,'Ip Address : '+ str_ipAddress)
                    dict_hostDetails['ipAddress'] = str_ipAddress
                    break                
    else:
        AgentLogger.log(AgentLogger.STDOUT,'Error While Executing Command For Fetching Mac Address And IpAddress')
    return dict_hostDetails

