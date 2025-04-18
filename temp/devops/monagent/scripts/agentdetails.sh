#!/bin/bash
agentdetails()
{

/bin/ps -eo pid,fname,pcpu,pmem,nlwp,command,args | grep -iw 'monagent' | grep -v "<defunct>\|grep" | grep -iw "Site24x7Agent\|MonitoringAgent.py" | awk 'BEGIN{
}
{ print $1,$2,$3,$4,$5,$6,$7,"Site24x7Agent"
}
END{
}'
}
agentdetails
