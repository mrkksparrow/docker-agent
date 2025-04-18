agentwatchdogdetails()
{

/bin/ps -eo pid,pcpu,pmem,comm,args| grep -v "\[sh] <defunct>" | grep -v grep | grep "MonitoringAgentWatchdog" | grep -v "awk" | awk 'BEGIN{
}
{ print $1,$2,$3,$4,$5,"Site24x7AgentWatchdog"
}
END{
}'

}

agentwatchdogdetails
