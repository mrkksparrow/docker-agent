#!/bin/bash
#set -x
#set path to avoid prepending path
SUCCESS=0
FAILURE=1
#LINUX_DIST='Lin_dist'
OS_NAME=`uname -s`
#USER_SESSIONS_COMMAND='last -F -n 50'
export LC_NUMERIC="en_US"

echoMessage() {
	echo ""
	echo "<<$1>>"	
}

loadSystemStats(){
	echoMessage "system_stats"
}

loadSystemUptime(){
	echoMessage "system_uptime"
}

loadProcessQueue(){
	echoMessage "process_queue"
}

loadMemoryStats(){
	echoMessage "memory_stats"
}

getUdpStats()
{
	echoMessage "udp_stats"
}

getTcpStats()
{
	echoMessage "tcp_stats"
}

getLoginCount(){
	echoMessage "login_count"
}

getIpStats(){
	echoMessage "ip_stats"
}

getIcmpStats(){
	echoMessage "icmp_stats"
}

detectOSAndDistro() {
	echoMessage "OS"
}

osArchitecture() {
	echoMessage "os architecture"
}

topCommand() {
	echoMessage "top"
}

processor() {
	echoMessage "Processor"
}

getCpuDetails() {
	echoMessage "cpu details"           
}

rcaCpuDetails() {
	echoMessage "rca cpu details"
}

cpuCoreDetails() {
	echoMessage "cpu cores usage"	
}

getCpuCores() {
	echoMessage "cpu cores"
}

getProcessorName() {
	echoMessage "processor"
}
# Number of interrupts (since the last boot)
getCpuInterrupts() {
	echoMessage "cpu interrupt"
}
# Number of context switches (since the last boot)
getCpuContextSwitches() {
	echoMessage "cpu context switches"
}

diskDetails() {
	echoMessage "disk details"
}

rcaDiskDetails() {
	echoMessage "rca disk details"
}

# Number of reads, writes completed (since the last boot)
diskStats() {
	echoMessage "disk stats"
}

diskErrors() {
	echoMessage "disk errors"
}

dmesgErrors() {
	echoMessage "dmesg errors"
}

uptimeDetails() {
	echoMessage "uptime details"
}

getMemoryDetails() {
	echoMessage "memory details"
}

getRcaMemoryDetails() {
	echoMessage "rca memory details"
}

# Number of pagein, pageout and pgfault (since the last boot)
getMemoryStats() {
	echoMessage "memory stats"
}

fetchTrafficDetails() {
	echoMessage "interface traffic"
}

fetchRcaTrafficDetails() {
	echoMessage "rca interface traffic"
}


fetchInterfaceStatus() {
	echoMessage "interface details"
}


fetchInterfaceData(){
	echoMessage "interface data"
}

fetchBondInterfaceData(){
	echoMessage "interface data"
}


fetchBondInterfaceData(){
	echoMessage "interface data"
}

fetchRcaInterfaceStatus() {
	echoMessage "rca interface details"
}

installedSoftware() {
	echoMessage "installed software"
}

listUsers() {
	echoMessage "list users"
}

userSessions() {
	echoMessage "user sessions"
}

processMonitoring(){
	echoMessage "process_monitoring"
}

psCommand() {
		echoMessage "ps"
}

parseInput() {
	if [ "$1" != "" ]; then
		for PARAM in ${1//,/ }; do
			echo "PARAM : $PARAM"
			if [ "${PARAM}" = "cpu_util" ]; then
				getCpuDetails
			elif [ "${PARAM}" = "rca_cpu_details" ]; then
				rcaCpuDetails
			elif [ "${PARAM}" = "cpu_cores" ]; then
				getCpuCores
			elif [ "${PARAM}" = "cpu_intr" ]; then
				getCpuInterrupts
			elif [ "${PARAM}" = "cpu_cs" ]; then
				getCpuContextSwitches
			elif [ "${PARAM}" = "processor" ]; then
				getProcessorName
			elif [ "${PARAM}" = "os_arch" ]; then
				osArchitecture					
			elif [ "${PARAM}" = "disk_details" ]; then
				diskDetails
			elif [ "${PARAM}" = "rca_disk_details" ]; then
				rcaDiskDetails
			elif [ "${PARAM}" = "disk_stats" ]; then
				diskStats
			elif [ "${PARAM}" = "disk_err" ]; then
				diskErrors
			elif [ "${PARAM}" = "mem_details" ]; then
				getMemoryDetails
			elif [ "${PARAM}" = "rca_mem_details" ]; then
				getRcaMemoryDetails
			elif [ "${PARAM}" = "mem_stats" ]; then
				getMemoryStats
			elif [ "${PARAM}" = "if_details" ]; then
				fetchInterfaceStatus
			elif [ "${PARAM}" = "if_data" ]; then
				fetchInterfaceData
			elif [ "${PARAM}" = "rca_if_details" ]; then
				fetchRcaInterfaceStatus
			elif [ "${PARAM}" = "if_traffic" ]; then
				fetchTrafficDetails
			elif [ "${PARAM}" = "rca_if_traffic" ]; then
				fetchRcaTrafficDetails
			elif [ "${PARAM}" = "dmesg_err" ]; then
				dmesgErrors
			elif [ "${PARAM}" = "uptime_details" ]; then
				uptimeDetails
			elif [ "${PARAM}" = "user_sessions" ]; then
				userSessions
			elif [ "${PARAM}" = "inst_soft" ]; then
				installedSoftware
			elif [ "${PARAM}" = "topCommand" ]; then
				topCommand
			elif [ "${PARAM}" = "psCommand" ]; then
				psCommand
			elif [[ "${PARAM}" == *"pcheck"* ]];then
				processMonitoring $PARAM
			elif [ "${PARAM}" = "core_usage" ]; then
				cpuCoreDetails				
			elif [ "${PARAM}" = "system_stats" ]; then
				loadSystemStats
			elif [ "${PARAM}" = "system_uptime" ]; then
				loadSystemUptime
			elif [ "${PARAM}" = "process_queue" ]; then
				loadProcessQueue
			elif [ "${PARAM}" = "memory_stats" ]; then
				loadMemoryStats
			elif [ "${PARAM}" = "login_count" ]; then
				getLoginCount
			elif [ "${PARAM}" = "udp_stats" ]; then
				getUdpStats
			elif [ "${PARAM}" = "tcp_stats" ]; then
				getTcpStats
			elif [ "${PARAM}" = "ip_stats" ]; then
				getIpStats
			elif [ "${PARAM}" = "icmp_stats" ]; then
				getIcmpStats
			elif [ "${PARAM}" = "if_bond_data" ]; then
				fetchBondInterfaceData
			fi

		done
	fi
}

main() {
	echo "TIME : "+`date`
	parseInput $1
}

main $1