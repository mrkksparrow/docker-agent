#!/bin/bash

SUCCESS=0
FAILURE=1
# PROC_FOLDER="/host/proc"
# SYS_FOLDER="/host/sys"
# Number of pagein, pageout and pgfault (since the last boot)
getMemoryStats() {
	cat $PROC_FOLDER/vmstat | grep -i 'pgpgin\|pgpgout\|pgfault'
}

loadSystemUptime(){
	cat $PROC_FOLDER/uptime
}

loadSystemStats(){
	cat $PROC_FOLDER/loadavg
}

getProcessorName() {
	grep -E 'model name' $PROC_FOLDER/cpuinfo | awk 'BEGIN {
			FS=":";
			ORS="\n";			
		}
		{
			if (NR == 1) {
				print $2
			}
		}'
	
}

osArchitecture() {
	uname -i | awk 'BEGIN {
		ORS="\n";
	}
	{	
		print $NF
	}'	
}	

loadProcessQueue(){
	cat $PROC_FOLDER/stat | grep "procs_running"
	cat $PROC_FOLDER/stat | grep "procs_blocked"
}

fetchInterfaceData(){
	if [ -f $SYS_FOLDER/class/net/bonding_masters ]; then
		bonding_masters=$( cat $SYS_FOLDER/class/net/bonding_masters )
	fi
	ls $SYS_FOLDER/class/net | awk -v sys_folder="$SYS_FOLDER" -v awk_bonding_masters="${bonding_masters[*]}" 'BEGIN {
		ORS="\n";
	}
	{	
		#print "Processing Record ",NR,NF;
		if_name = ""
		rx_bytes = 0
		if (NR > 0) {
			split($1, temp_arr, ":")
			if_name = temp_arr[1]
			#print if_name
			int_match = match(if_name,"veth")
			if (int_match != 1)
			{
			if_valid = 1
			if_status = 0
			if_address = "N/A-" if_name	
			state_command = "/bin/cat "sys_folder"/class/net/"if_name"/operstate"
			macAddr_command = "/bin/cat "sys_folder"/class/net/"if_name"/address"
			rxbytes_command = "/bin/cat "sys_folder"/class/net/"if_name"/statistics/rx_bytes"
			rxpackets_command = "/bin/cat "sys_folder"/class/net/"if_name"/statistics/rx_packets"
			txbytes_command = "/bin/cat "sys_folder"/class/net/"if_name"/statistics/tx_bytes"
			txpackets_command = "/bin/cat "sys_folder"/class/net/"if_name"/statistics/tx_packets"
			txerrors_command = "/bin/cat "sys_folder"/class/net/"if_name"/statistics/tx_errors"
			txdrops_command = "/bin/cat "sys_folder"/class/net/"if_name"/statistics/tx_dropped"
			rxmulticastpackets_command = "/bin/cat "sys_folder"/class/net/"if_name"/statistics/multicast"
			isStateCommandSuccess = (state_command | getline if_state) 
			isMacAddrCommandSuccess = (macAddr_command | getline if_address)
			rxbytesCommandSuccess = (rxbytes_command | getline rx_bytes)
			rxpacketsCommandSuccess = (rxpackets_command | getline rx_packets)
			txbytesCommandSuccess = (txbytes_command | getline tx_bytes)
			txpacketsCommandSuccess = (txpackets_command | getline tx_packets)
			txerrorsCommandSuccess = (txerrors_command | getline tx_errors)
			txdropsCommandSuccess = (txdrops_command | getline tx_drops)
			rxmulticastpacketsCommandSuccess = (rxmulticastpackets_command | getline rx_multicastPackets)
			{split(awk_bonding_masters, awk_bonding_masters_array, / /)}
			for (i in awk_bonding_masters_array){if (awk_bonding_masters_array[i] == if_name){ if_valid = 0; if_address = if_address"_"if_name}};
			#print isStateCommandSuccess isMacAddrCommandSuccess
			#print "State : "if_state" Address : "if_address
			if (if_state == "up")
			{
				if_status = 1
			}
			if (if_state == "unknown")
			{
				if_status = 2
			}
			if(if_valid == 1){
			print if_name" -- "if_status" -- "if_address" -- "rx_bytes" -- "rx_packets" -- "tx_bytes" -- "tx_packets" -- "tx_errors" -- "tx_drops" -- "rx_multicastPackets
			}
		}
		}
	}'

}

diskDetails() {
    df -l -T | grep -i '/host' |grep -ivE 'Filesystem|overlay|/proc' | awk 'BEGIN {
        ORS="\n";
        partitionNameArray[0] = 0;
    }
    {       
        #print "Processing Record ",NR,NF,$NF;
        if ($NF in partitionNameArray == 0)
        {
			$NF = substr($0, index($0," /")+1, length($0))
			#gsub("/host/","/",$NF)
			#gsub("/host","/",$NF)
			partitionNameArray[$NF] = $NF
			if (NF > 2)
			{
				printf $NF" :: "$1" :: "$2" :: %.0f :: %.0f \n",(($4*1024)+($5*1024)), $5*1024
			}
        }
    }'
}

parseInput() {
	if [ "$1" != "" ]; then
		for PARAM in ${1//,/ }; do
			if [ "${PARAM}" = "mem_stats" ]; then
				getMemoryStats
			elif [ "${PARAM}" = "system_uptime" ]; then
				loadSystemUptime
			elif [ "${PARAM}" = "system_stats" ]; then
				loadSystemStats
			elif [ "${PARAM}" = "processor" ]; then
				getProcessorName
			elif [ "${PARAM}" = "os_arch" ]; then
				osArchitecture	
			elif [ "${PARAM}" = "process_queue" ]; then
				loadProcessQueue
			elif [ "${PARAM}" = "if_data" ]; then
				fetchInterfaceData
			elif [ "${PARAM}" = "disk_details" ]; then
				diskDetails
			fi
		done
	fi
}

main() {
	parseInput $1
	#detectOSAndDistro
}

main $1
