#!/bin/bash
#set -x
SUCCESS=0
FAILURE=1
LINUX_DIST='Lin_dist'
OS_NAME=`uname -s`
USER_SESSIONS_COMMAND='last -F -n 50'
export LC_NUMERIC="en_US"

setUserSessionsCommand()
{
	$USER_SESSIONS_COMMAND > /dev/null 2>&1
    RET_VAL=$?
    if [ $RET_VAL == $FAILURE ]; then
    	USER_SESSIONS_COMMAND='last'
    fi
}

echoMessage() {
	echo ""
	echo "<<$1>>"	
}

loadSystemStats(){
	echoMessage "system_stats"
	echo $(cat /proc/loadavg) $(ps aux | wc -l) $(netstat -lntu | wc -l)
}

loadSystemUptime(){
	echoMessage "system_uptime"
	cat /proc/uptime
}

loadProcessQueue(){
	echoMessage "process_queue"
	cat /proc/stat | grep "procs_running"
	cat /proc/stat | grep "procs_blocked"
}

loadMemoryStats(){
	echoMessage "memory_stats"
	cat /proc/meminfo | grep -i 'MemTotal'
	cat /proc/meminfo | grep -i 'MemFree'
	cat /proc/meminfo | grep -i 'Buffers'
	cat /proc/meminfo | grep -w 'Cached'
	cat /proc/meminfo | grep 'SwapCached'
	cat /proc/meminfo | grep -i 'SwapTotal'
	cat /proc/meminfo | grep -i 'SwapFree'
	cat /proc/meminfo | grep -i 'CommitLimit'
	cat /proc/meminfo | grep -i 'Committed_AS'
	cat /proc/meminfo | grep -i 'Dirty'
	cat /proc/meminfo | grep -i 'Slab'
	cat /proc/meminfo | grep -wi 'WriteBack'
	cat /proc/meminfo | grep -i 'AnonPages'
	cat /proc/meminfo | grep -i 'Mapped'
	cat /proc/meminfo | grep -i 'PageTables'
	cat /proc/vmstat | grep -i 'pgmajfault'
	cat /proc/vmstat | grep -i 'pswpin'
	cat /proc/vmstat | grep -i 'pswpout'
	cat /proc/meminfo | grep 'Active:'
	cat /proc/meminfo | grep 'Inactive:'
}

getUdpStats()
{
	echoMessage "udp_stats"
	cat /proc/net/snmp | grep -w "Udp"
}

getTcpStats()
{
	echoMessage "tcp_stats"
	cat /proc/net/snmp | grep -w "Tcp"
}

getLoginCount(){
	echoMessage "login_count"
	who -q
}

getIpStats(){
	echoMessage "ip_stats"
	cat /proc/net/snmp | grep -w "Ip"
}

getIcmpStats(){
	echoMessage "icmp_stats"
	cat /proc/net/snmp | grep -w "Icmp"
}

detectOSAndDistro() {
	#os rename
	if [ "${OS_NAME}" = "SunOS" ]; then
		OS_NAME=Solaris
	fi

	#distro detection
	if [ "${OS_NAME}" = "Linux" ]; then
		if [ -f /etc/os-release ]; then				
			DISTRO=$(cat /etc/os-release | grep 'PRETTY_NAME=' | awk -F\" '{print $2}')
		else
			if [ -f /etc/redhat-release ]; then
				strcmd="/bin/cat /etc/redhat-release"
			elif [ -f /etc/centos-release ]; then
				strcmd="/bin/cat /etc/centos-release"
			else
				strcmd="/bin/cat /etc/issue"			
			fi
			
			DISTRO=$($strcmd  | awk 'BEGIN {  
			ORS="\n";
			LINUX_DIST="";
			}
			{
				if (NR==1 && $0 != "") {
					LINUX_DIST=LINUX_DIST""$0
					gsub(/\\n/,"",LINUX_DIST)
					gsub(/\\l/,"",LINUX_DIST)
					gsub(/\\r/,"",LINUX_DIST)
					gsub(/\\m/,"",LINUX_DIST)	                
				}       
			}END {print LINUX_DIST}')
		fi
	fi
	echo $DISTRO
}

osArchitecture() {
	echoMessage "os architecture"
	uname -m | awk 'BEGIN {
		ORS="\n";
	}
	{	
		#print "Processing Record ",NR,NF,$NF;
		print "Architecture : "$NF
	}'	
}

topCommand() {
	echoMessage "top"
	/usr/bin/top -b -d2 -n2
}

processor() {
	echoMessage "Processor"
	grep -E 'model name' /proc/cpuinfo | awk -F':' 'NR==1{print $2}'	
}

getCpuStats() {
	echoMessage "cpu_stats"
	topOutput=`top -b -d1 -n2 | grep -w Cpu | grep -v grep | tail -1`
	IFS=":" read -ra NAMES <<< "$topOutput"
	cpu_values=${NAMES[1]}
	echo ${cpu_values}   
}

getCpuDetails() {
	echoMessage "cpu details"
        topFilteredOutput=`top -b -d1 -n2 | awk 'BEGIN{ORS=" ::: ";} /^%Cpu|^Cpu/ '`
        #echo $topFilteredOutput        
        echo $topFilteredOutput | awk 'BEGIN{FS=" ::: ";}
        {
                #print NF
                #print $1
                #print $2
                for(k=(NF/2+1);k<=NF;k++)
                {
                        split($k,arrBeforeCpuIdleTime,"wa")
                        #print "Substring before cpu idle time : ",arrBeforeCpuIdleTime[1]
                        split(arrBeforeCpuIdleTime[1],arrAfterNiceCpuTime,"ni")
			split(arrBeforeCpuIdleTime[1],arrAfterWaitTime,"id")
                        #print "Substring after use nice cpu time : ",arrAfterNiceCpuTime[2]
			#print "wait :" , arrAfterWaitTime[2]    
                        awkCpu = substr(arrAfterNiceCpuTime[2],2)
			awkWait = substr(arrAfterWaitTime[2],2)
                        #print "wait time :",awkWait
                        #print "Extracted ideal percentage : ",awkCpu
                        gsub(",",".",awkCpu)
                        gsub(",",".",awkWait)
                        netSumCpuIdealPercentage+=awkCpu
                }
                #print "Net sum  Cpu ideal percentage : ",netSumCpuIdealPercentage
                #print "wait time percentage :",awkWait
                cpu_idle_percentage = netSumCpuIdealPercentage/(NF/2)
                #print "cpu_idle_percentage: ",cpu_idle_percentage
                cpu_util = 100.0 - cpu_idle_percentage
                print "CPU_Name : cpu"
                print "CPU_Idle_Percentage : ",cpu_idle_percentage           
                printf "CPU_Utilization : %.2f\n",cpu_util
		printf "CPU_Wait_Time : %.2f\n",awkWait
        }'
               
}

getTopCommandData(){
  echoMessage "top $1 process"
    if [ "$1" = "CPU" ]; then
        top_output=$(top -n 2 -d 2 -b -o \%$1 | awk 'BEGIN{ORS="\n"}{print}')
        #echo "${top_output}"
        cpu_util=$(echo "${top_output}" | awk 'BEGIN { found=0 } /^$/ { found++ } found==2 { print }')
        cpu_util=$(echo "${cpu_util}" | awk '/^%Cpu|^Cpu/ ')
        #echo "${cpu_util}"
        echo $cpu_util | awk 'BEGIN{FS=","}{
            for(k=0;k<=NF;k++)
            {
                #print $k
                if ($k ~ /id/)
                    cpu_idle_percentage=$k
                if ($k ~ /wa/)
                    awkWait = $k
            }
            cpu_utilized = 100.0 - cpu_idle_percentage
            #print "CPU_Name : cpu"
            #print "CPU_Idle_Percentage : ",cpu_idle_percentage
            #printf "CPU_Utilization : %.2f\n",cpu_utilized
            #printf "CPU_Wait_Time : %.2f\n",awkWait
            printf "CPU_UTIL::cpu::%.2f::%.2f::%.2f::xxx::xxx::%s\n",cpu_idle_percentage,cpu_utilized,awkWait,$0
        }'
    else
        top_output=$(top -n 2 -d 2 -b -o \%$1 | awk 'BEGIN{ORS="\n"}{print}')
    fi

    top_process=$(echo "${top_output}" | awk 'BEGIN { found=0 } /^$/ { found++ } found==3 { print }')
    #echo "${top_process}"
    top_process=$(echo "${top_process}" | awk 'NR>=3 && NR <=30')
    #echo "${top_process}"
    top_pids=$(echo "$top_process" | awk '{printf $1"::"$9"::"$10"\n"}')
    #echo "PID  NAME  PATH  CPU%  MEM%  HC  TC  CMD"
    processes_count=5
    for process in $top_pids; do
        process_array=(${process//'::'/ })
        process_deleted=0
        pid=${process_array[0]}
        cpu=${process_array[1]}
        mem=${process_array[2]}
        process_name=$(ps -p $pid -o comm= --no-headers)
        [ -z "$process_name" ] && process_deleted=1
        cmd_line_args=$(ps -p $pid -o command= --no-headers)
        [ -z "$cmd_line_args" ] && process_deleted=1
        thread_count=$(ps -p $pid -o nlwp= --no-headers | sed 's/ //g')
        [ -z "$thread_count" ] && thread_count=0
        handle_count=$(ls /proc/$pid/fd 2>/dev/null | wc -l)
        [ -z "$handle_count" ] && handle_count=0
        process_path=(${cmd_line_args//' '/ })
        process_path=${process_path[0]}
        if [ ! "$process_deleted" == "1"  ]; then
          echo "$pid::$process_name::$process_path::$cpu::$mem::$handle_count::$thread_count::$cmd_line_args"
          ((processes_count--))
          if [ "$processes_count" == "0" ];then
            break
          fi
        fi
    done
}

rcaCpuDetails() {
	echoMessage "rca cpu details"
        rcaTopFilteredOutput=`top -b -d1 -n2 | awk 'BEGIN{ORS=" ::: ";} /^%Cpu|^Cpu/ '`
        #echo $rcaTopFilteredOutput        
        echo $rcaTopFilteredOutput | awk 'BEGIN{FS=" ::: ";}
        {
                #print NF
                #print $1
                #print $2
        		for(k=(NF/2+1);k<=NF;k++)
                {
                        split($k,arrBeforeCpuIdleTime,"id|un")
                        #print "Substring before cpu idle time : ",arrBeforeCpuIdleTime[1]
                        split(arrBeforeCpuIdleTime[1],arrAfterNiceCpuTime,"ni")
                        #print "Substring after use nice cpu time : ",arrAfterNiceCpuTime[2]    
                        awkCpu = substr(arrAfterNiceCpuTime[2],2)
                        #print "Extracted ideal percentage : ",awkCpu
                        gsub(",",".",awkCpu)
                        netSumCpuIdealPercentage+=awkCpu
                }
                #print "Net sum  Cpu ideal percentage : ",netSumCpuIdealPercentage
                cpu_idle_percentage = netSumCpuIdealPercentage/(NF/2)
                #print "cpu_idle_percentage: ",cpu_idle_percentage
                cpu_util = 100.0 - cpu_idle_percentage
                print "CPU_Name : cpu"
                print "CPU_Idle_Percentage : ",cpu_idle_percentage           
                printf "CPU_Utilization : %.2f\n",cpu_util
        }'               

    cat /proc/stat | grep -i 'intr ' | awk '{ print "Interrupts :",$2 }'
    cat /proc/stat | grep -i 'ctxt ' | awk '{ print "Context Switches :",$2 }'

}

cpuCoreDetails() {
	echoMessage "cpu cores usage"
		procStatCpuData=` awk 'BEGIN{ORS=" ::: ";} /^cpu[0-9]/' /proc/stat`
        echo $procStatCpuData | awk 'BEGIN{FS=" ::: ";}
        {
                for (i=1;i<=NF;i++)
                {
                        split($i,array," ")
                        printf "%s -- %d -- %d -- %d -- %d -- %d -- %d -- %d -- %d -- %d -- %d \n",array[1],array[2],array[3],array[4],array[5],array[6],array[7],array[8],array[9],array[10],array[11]
                }
        }'	
}

getCpuCores() {
	echoMessage "cpu cores"
	cat /proc/cpuinfo | awk 'BEGIN {
		FS=":";
		cpu_count = 0;
	}
	{
		split($1, temp_arr, "%")
		name = temp_arr[1]
		sub(/[ \t]+$/,"",name) #remove leading and trailing spaces.
		#print ":"name":"
		#print cpu_count
		if (name == "processor")
		{
			cpu_count+=1
		}
	}
	END {
		print "Cpu cores :",cpu_count
	}'
}

getProcessorName() {
	echoMessage "processor"
	grep -E 'model name' /proc/cpuinfo | awk 'BEGIN {
			FS=":";
			ORS="\n";			
		}
		{
			if (NR == 1) {
				print "Processor Name :",$2
			}
		}'
	
}
# Number of interrupts (since the last boot)
getCpuInterrupts() {
	echoMessage "cpu interrupt"
	cat /proc/stat | grep -i 'intr ' | awk '{ print "Interrupts :",$2 }'
}
# Number of context switches (since the last boot)
getCpuContextSwitches() {
	echoMessage "cpu context switches"
	cat /proc/stat | grep -i 'ctxt ' | awk '{ print "Context Switches :",$2 }'
}

diskDetails() {
	echoMessage "disk details"
    df -l -T | grep -ivE 'Filesystem|overlay' | awk 'BEGIN {
        ORS="\n";
        partitionNameArray[0] = 0;
    }
    {       
        #print "Processing Record ",NR,NF,$NF;
        if ($NF in partitionNameArray == 0)
        {
            partitionNameArray[$NF] = $NF
            if (NF > 2)
            {
				printf $NF" :: "$(NF-6)" :: "$(NF-5)" :: %.0f :: %.0f \n",(($(NF-3)*1024)+($(NF-2)*1024)), $(NF-2)*1024      
            }
        }
    }'
}

#cant get both disk and inode details so having seperate method unlike osx
diskInodeDetails() {
	echoMessage "disk inode details"
	df -il | grep -ivE 'Filesystem|overlay' | awk 'BEGIN {
	 	ors="\n";
	}
	{
		name =$NF
		Total_Inodes = $2
		IUsed = $3
		IFree = $4
		IUsedPer = $5
		print name" :: "Total_Inodes" :: "IUsed" :: "IFree" :: "IUsedPer
	}'
}
rcaDiskDetails() {
	echoMessage "rca disk details"
    df -l -Th | grep -ivE 'Filesystem|overlay' | awk 'BEGIN {
        ORS="\n";
        partitionNameArray[0] = 0;
    }
    {       
        #print "Processing Record ",NR,NF, $0;
        stdFieldCount=7
        if ($NF in partitionNameArray == 0)
        {
            partitionNameArray[$stdFieldCount] = $stdFieldCount
            partitionSize = $(stdFieldCount-4)
        	partitionUsed = $(stdFieldCount-3)
        	partitionAvail = $(stdFieldCount-2)
        	partitionUsedPercentage = $(stdFieldCount-1) 
            if (NF > 2)
            {
            	print $NF" -- "partitionSize" -- "partitionUsed" -- "partitionAvail" -- "partitionUsedPercentage      
            }
        }
    }'
}

# Number of reads, writes completed (since the last boot)
diskStats() {
	echoMessage "disk stats"
	PARTITIONS=(`awk 'NR > 1 && $0 !~ /dm-|loop|drbd|ram/ {ORS=" "; print $4}' /proc/partitions`)
	if [ "${#PARTITIONS[@]}" -eq 0 ]; then
	    PARTITIONS=(`awk 'NR > 1 && $0 !~ /dm-|loop|drbd/ {ORS=" "; print $4}' /proc/partitions`)
	fi
	BYTES_PER_SECTOR=512
	PARTITION_NAME=''
	for (( i = 0; i < ${#PARTITIONS[@]} ; i++ )); do
    	STATS_ARR=(`awk -v dev=${PARTITIONS[$i]} '$3 == dev' /proc/diskstats`)
    	PARTITION_NAME=${STATS_ARR[2]}
		READS=$((512 * STATS_ARR[5]))
    	WRITES=$((512 * STATS_ARR[9]))
		echo "$PARTITION_NAME : $READS : $WRITES"
	done
}

diskErrors() {
	echoMessage "disk errors"
	dmesg | grep -w "I/O error\|EXT2-fs error\|EXT3-fs error\|EXT4-fs error\|UncorrectableError\|DriveReady SeekComplete Error\|I/O Error Detected" | sort -u	
}

dmesgErrors() {
	echoMessage "dmesg errors"
	dmesg | grep -i 'error' | tail -n 10	
}

uptimeDetails() {
	echoMessage "uptime details"
	uptime	
}

getMemoryDetails() {
	echoMessage "memory details"
	free -k | awk 'BEGIN {  
        ORS="\n";
	virtTrue=0;
	avail = 0;
	}
	{
        #print "Processing Record ",NR;
	mem = match($1,"Mem")
	swap = match($1,"Swap")
	if(NR == 1)
	{
		avail = match($0,"available")
		#print "Setting available to :",avail	
	}
        if (mem == 1)
            { 
		print "TotalVisibleMemorySize :",$2
		if( avail != 0 )
		{
			print "AvailablePhysicalMemory :"$7
			print "FreePhysicalMemory :"$4
			print "UsedPhysicalMemory :"$3
			print "BufferMemory :"$6
			print "CacheMemory : -1"
		}
		else
		{
			print "AvailablePhysicalMemory : -1"
			print "FreePhysicalMemory :"$4
			print "UsedPhysicalMemory :"$3
			print "BufferMemory :"$6
			print "CacheMemory :"$7
		}
	    }	
        else if (swap == 1)
             {print "TotalVirtualMemorySize :",$2,"\nFreeVirtualMemory :",$4
	    virtTrue = 1
	    }       
	}END{if(virtTrue == 0) print "TotalVirtualMemorySize :",0,"\nFreeVirtualMemory :",0}'
    echo "Linux Distribution : "$(detectOSAndDistro)
}

getRcaMemoryDetails() {
	echoMessage "rca memory details"
	free -km | awk 'BEGIN {  
        ORS="\n";
	}
	{
        #print "Processing Record ",NR;
        if (NR == 2)
        {
            print "Total Memory :",$2,"MB"
            print "Used Memory :",$3,"MB"
            print "Free Memory :",$4,"MB"
        }
        else if (NR == 3)
        {
        	print "Buffer Free Memory :",$4,"MB"
            print "Buffer Used Memory :",$3,"MB"
        }
        else if (NR == 4)
        {
            print "Total Virtual Memory :",$2,"MB"
            print "Free Virtual Memory :",$4,"MB"
        }          
	}'
}

# Number of pagein, pageout and pgfault (since the last boot)
getMemoryStats() {
	echoMessage "memory stats"
	cat /proc/vmstat | grep -i 'pgpgin\|pgpgout\|pgfault'
}

fetchTrafficDetails() {
	echoMessage "interface traffic"
	cat /proc/net/dev | awk 'BEGIN {
		ORS="\n";
	}
	{	
		#print "Processing Record ",NR,NF;
		if_name = ""
		rx_bytes = 0
		if (NR > 2) {
			split($1, temp_arr, ":")
			if_name = temp_arr[1]	
			if_speed = ""	
			sub(/[ \t]+$/,"",temp_arr[2])
			#print ":"temp_arr[2]":"
			if (temp_arr[2] == "")
			{
				rx_bytes = $2
				ifSpeed_command = "/bin/cat /sys/class/net/"if_name"/speed"
				isStateCommandSuccess = (ifSpeed_command | getline if_speed)
				print if_name,rx_bytes,$3,$10,$11,$12,$13,"speed : ",if_speed;
			}
			else
			{
				rx_bytes = temp_arr[2]
				ifSpeed_command = "/bin/cat /sys/class/net/"if_name"/speed"
				isStateCommandSuccess = (ifSpeed_command | getline if_speed)
				print if_name,rx_bytes,$2,$9,$10,$11,$12,"speed : ",if_speed;
			}
		}		
	}'
}

fetchRcaTrafficDetails() {
	echoMessage "rca interface traffic"
	cat /proc/net/dev | awk 'BEGIN {
		ORS="\n";
	}
	{	
		#print "Processing Record ",NR,NF;
		if_name = ""
		rx_bytes = 0
		if (NR > 2) {
			split($1, temp_arr, ":")
			if_name = temp_arr[1]	
			if_speed = ""	
			sub(/[ \t]+$/,"",temp_arr[2])
			#print ":"temp_arr[2]":"
			if (temp_arr[2] == "")
			{
				rx_bytes = $2
				ifSpeed_command = "/bin/cat /sys/class/net/"if_name"/speed"
				isStateCommandSuccess = (ifSpeed_command | getline if_speed)
				print if_name,rx_bytes,$3,$10,$11,$12,$13,"speed : ",if_speed;
			}
			else
			{
				rx_bytes = temp_arr[2]
				ifSpeed_command = "/bin/cat /sys/class/net/"if_name"/speed"
				isStateCommandSuccess = (ifSpeed_command | getline if_speed)
				print if_name,rx_bytes,$2,$9,$10,$11,$12,"speed : ",if_speed;
			}
		}		
	}'
}


fetchInterfaceStatus() {
	echoMessage "interface details"
	cat /proc/net/dev | awk 'BEGIN {
		ORS="\n";
	}
	{	
		#print "Processing Record ",NR,NF;
		if_name = ""
		rx_bytes = 0
		if (NR > 2) {
			split($1, temp_arr, ":")
			if_name = temp_arr[1]
			#print if_name
			if_status = 7
			if_address = "N/A-" if_name	
			state_command = "/bin/cat /sys/class/net/"if_name"/operstate"
			macAddr_command = "/bin/cat /sys/class/net/"if_name"/address"
			isStateCommandSuccess = (state_command | getline if_state) 
			isMacAddrCommandSuccess = (macAddr_command | getline if_address)
			#print isStateCommandSuccess isMacAddrCommandSuccess
			#print "State : "if_state" Address : "if_address
			if (if_state == "up")
			{
				if_status = 2
			}
			print if_name" -- "if_status" -- "if_address
		}
	}'
}


fetchInterfaceData(){
	echoMessage "interface data"
	if [ -f /sys/class/net/bonding_masters ]; then
		bonding_masters=$( cat /sys/class/net/bonding_masters )
	fi
	cat /proc/net/dev | awk -v awk_bonding_masters="${bonding_masters[*]}" 'BEGIN {
		ORS="\n";
	}
	{	
		#print "Processing Record ",NR,NF;
		if_name = ""
		rx_bytes = 0
		if (NR > 2) {
			split($1, temp_arr, ":")
			if_name = temp_arr[1]
			#print if_name
			int_match = match(if_name,"veth")
			if (int_match != 1)
			{
			if_valid = 1
			if_status = 0
			if_address = "N/A-" if_name	
			state_command = "/bin/cat /sys/class/net/"if_name"/operstate"
			macAddr_command = "/bin/cat /sys/class/net/"if_name"/address"
			rxbytes_command = "/bin/cat /sys/class/net/"if_name"/statistics/rx_bytes"
			rxpackets_command = "/bin/cat /sys/class/net/"if_name"/statistics/rx_packets"
			txbytes_command = "/bin/cat /sys/class/net/"if_name"/statistics/tx_bytes"
			txpackets_command = "/bin/cat /sys/class/net/"if_name"/statistics/tx_packets"
			txerrors_command = "/bin/cat /sys/class/net/"if_name"/statistics/tx_errors"
			txdrops_command = "/bin/cat /sys/class/net/"if_name"/statistics/tx_dropped"
			rxmulticastpackets_command = "/bin/cat /sys/class/net/"if_name"/statistics/multicast"
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

fetchBondInterfaceData(){
	echoMessage "interface data"
	if [ -f /sys/class/net/bonding_masters ]; then
		bonding_masters=$( cat /sys/class/net/bonding_masters )
	fi
	cat /proc/net/dev | awk -v awk_bonding_masters="${bonding_masters[*]}" 'BEGIN {
		ORS="\n";
	}
	{	
		#print "Processing Record ",NR,NF;
		if_name = ""
		rx_bytes = 0
		if (NR > 2) {
			split($1, temp_arr, ":")
			if_name = temp_arr[1]
			#print if_name
			int_match = match(if_name,"veth")
			if (int_match != 1)
			{
			if_valid = 1
			if_status = 0
			if_address = "N/A-" if_name	
			state_command = "/bin/cat /sys/class/net/"if_name"/operstate"
			macAddr_command = "/bin/cat /sys/class/net/"if_name"/address"
			rxbytes_command = "/bin/cat /sys/class/net/"if_name"/statistics/rx_bytes"
			rxpackets_command = "/bin/cat /sys/class/net/"if_name"/statistics/rx_packets"
			txbytes_command = "/bin/cat /sys/class/net/"if_name"/statistics/tx_bytes"
			txpackets_command = "/bin/cat /sys/class/net/"if_name"/statistics/tx_packets"
			txerrors_command = "/bin/cat /sys/class/net/"if_name"/statistics/tx_errors"
			txdrops_command = "/bin/cat /sys/class/net/"if_name"/statistics/tx_dropped"
			rxmulticastpackets_command = "/bin/cat /sys/class/net/"if_name"/statistics/multicast"
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
			for (i in awk_bonding_masters_array){if (awk_bonding_masters_array[i] == if_name){ if_address = if_address"_"if_name}};
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


fetchBondInterfaceData(){
	echoMessage "interface data"
	if [ -f /sys/class/net/bonding_masters ]; then
		bonding_masters=$( cat /sys/class/net/bonding_masters )
	fi
	cat /proc/net/dev | awk -v awk_bonding_masters="${bonding_masters[*]}" 'BEGIN {
		ORS="\n";
	}
	{	
		#print "Processing Record ",NR,NF;
		if_name = ""
		rx_bytes = 0
		if (NR > 2) {
			split($1, temp_arr, ":")
			if_name = temp_arr[1]
			#print if_name
			int_match = match(if_name,"veth")
			if (int_match != 1)
			{
			if_status = 0
			if_address = "N/A-" if_name	
			state_command = "/bin/cat /sys/class/net/"if_name"/operstate"
			macAddr_command = "/bin/cat /sys/class/net/"if_name"/address"
			rxbytes_command = "/bin/cat /sys/class/net/"if_name"/statistics/rx_bytes"
			rxpackets_command = "/bin/cat /sys/class/net/"if_name"/statistics/rx_packets"
			txbytes_command = "/bin/cat /sys/class/net/"if_name"/statistics/tx_bytes"
			txpackets_command = "/bin/cat /sys/class/net/"if_name"/statistics/tx_packets"
			txerrors_command = "/bin/cat /sys/class/net/"if_name"/statistics/tx_errors"
			txdrops_command = "/bin/cat /sys/class/net/"if_name"/statistics/tx_dropped"
			rxmulticastpackets_command = "/bin/cat /sys/class/net/"if_name"/statistics/multicast"
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
			for (i in awk_bonding_masters_array){if (awk_bonding_masters_array[i] == if_name){ if_address = if_address"_"if_name}};
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
			print if_name" -- "if_status" -- "if_address" -- "rx_bytes" -- "rx_packets" -- "tx_bytes" -- "tx_packets" -- "tx_errors" -- "tx_drops" -- "rx_multicastPackets
			}
		}
	}'
}

fetchRcaInterfaceStatus() {
	echoMessage "rca interface details"
	cat /proc/net/dev | awk 'BEGIN {
		ORS="\n";
	}
	{	
		#print "Processing Record ",NR,NF;
		if_name = ""
		rx_bytes = 0
		if (NR > 2) {
			split($1, temp_arr, ":")
			if_name = temp_arr[1]
			if_status = 7
			if_address = "N/A-" if_name		
			state_command = "/bin/cat /sys/class/net/"if_name"/operstate"
			macAddr_command = "/bin/cat /sys/class/net/"if_name"/address"
			isStateCommandSuccess = (state_command | getline if_state) 
			isMacAddrCommandSuccess = (macAddr_command | getline if_address)
			#print isStateCommandSuccess isMacAddrCommandSuccess
			#print "State : "if_state" Address : "if_address
			if (if_state == "up")
			{
				if_status = 2
			}
			else
			{
				if_state = "down"
			}
			print if_name" -- "if_state
		}
	}'
}

installedSoftware() {
	echoMessage "installed software"
	dpkg --list | awk 'BEGIN {
		ORS="\n";
	}
	{
		if (NR > 5)	{
			description = "" 
			for(i=4;i<=NF;i++){description=description" "$i}; 
			print $2 " ::: " $3 " ::: "description
		}
	}'
}

listUsers() {
	echoMessage "list users"
	who -uH | awk 'BEGIN {
		ORS="\n";
	}
	{
		if (NR > 1)	{
			timeField = "" 
			for(i=4;i<=NF;i++){timeField=timeField" "$i}; 
			print $1 " ::: "$2" ::: "$3" "$4" ::: "$7
		}
	}'
}

userSessions() {
	setUserSessionsCommand
	echoMessage "user sessions"
	$USER_SESSIONS_COMMAND | head -n 20 | awk 'BEGIN {
		ORS="\n";
	}
	{
		column1=substr($0,1,8)
		column2=substr($0,10,11)
		column3=substr($0,21,18)
		column4=substr($0,39)
		gsub(/^[ \t]+|[ \t]+$/,"",column1)
		gsub(/^[ \t]+|[ \t]+$/,"",column2)
		gsub(/^[ \t]+|[ \t]+$/,"",column3)
		gsub(/^[ \t]+|[ \t]+$/,"",column4)
		if (column1  !~ /^ *$/ && column1 !~ /^wtmp/ && column2 !~ /^ *$/ && column3  !~ /^ *$/ )
		{
			print column1 " ::: "column2" ::: "column3" ::: "column4
		}   
		
	}'
}

# ProcessUptime(){
# 	VER="(Santiago)" #redhat 6.10 only supports etime
# 	if [[ "$(detectOSAndDistro)" == *"$VER"* ]]; then
# 		uptime='etime'
# 	else
# 		uptime='etimes'
# 	fi
# 	echo $uptime
# }
processMonitoring(){
	processes=`echo $1 | awk -F "::" '{print $2}'`
	echoMessage "process_monitoring"
	#uptime=$(ProcessUptime)
	/bin/ps -eo pid,user,pri,etime,rss,fname,pcpu,pmem,nlwp,command,args | grep -v "\[sh] <defunct>" | grep -E ${processes} | grep -v grep | awk 'BEGIN {
	ORS="\n";
	}
	{
		processName = $6
		exePath = $10
		oldCommandArgs = $11
		commandArgs = substr($0,90,length($0))
		size = $5 		#in KB
        gsub("\"", "\\\"", processName)
        gsub("\"", "\\\"", exePath)
        gsub("\"", "\\\"", commandArgs)
        awkProcessIndex = index(commandArgs,"ishandleCountCommandSuccess")
        if (awkProcessIndex == 0) {
			if (NR == 1) {
					print "  PID USER PRIORITY UPTIME SIZE NAME %CPU %MEM NLWP HANDLE COMMAND                     ARGS"
			}
			if (NR >= 1) {
				fd_cmd = "ls /proc/"$1"/fd 2>/dev/null | /usr/bin/wc -l "
				fd_cmd | getline fd
				close(fd_cmd)
				print $1" :: "$2" :: "$3" :: "$4" :: "size" :: "processName" :: "$7" :: "$8" :: "$9" :: "fd" :: "exePath" :: "commandArgs" :: "oldCommandArgs
			}
        }
	}'
}

psCommand() {
	echoMessage "ps"
	#uptime=$(ProcessUptime)
	/bin/ps -eo pid,user,pri,etime,fname,pcpu,pmem,nlwp,command,args| grep -v "\[sh] <defunct>" | awk 'BEGIN {
	ORS="\n";
	}	
	{	
		processName = $5
		exePath = $9
		oldCommandArgs = $10
		commandArgs = substr($0,84,length($0))
		gsub("\"", "\\\"", processName)
		gsub("\"", "\\\"", exePath)
		gsub("\"", "\\\"", commandArgs)
		awkProcessIndex = index(commandArgs,"ishandleCountCommandSuccess")
		if (awkProcessIndex == 0) {
			if (NR == 1) {
					print "PID  USER   PRI      UPTIME  COMMAND  %CPU %MEM NLWP COMMAND                     ARGS"
			} 
			if (NR > 1) {
				fd_cmd = "ls /proc/"$1"/fd 2>/dev/null | /usr/bin/wc -l "
				fd_cmd | getline fd
				close(fd_cmd)
				print $1" :: "$2" :: "$3" :: "$4" :: "processName" :: "$6" :: "$7" :: "$8" :: "fd" :: "exePath" :: "commandArgs" :: "oldCommandArgs
			}
		}
	}'
}

parseInput() {
	if [ "$1" != "" ]; then
		for PARAM in ${1//,/ }; do
			#echo "PARAM : $PARAM"
			if [ "${PARAM}" = "cpu_util" ]; then
				getCpuDetails
			elif [ "${PARAM}" = "top_cpu" ]; then
				getTopCommandData "CPU"
			elif [ "${PARAM}" = "top_mem" ]; then
				getTopCommandData "MEM"
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
			elif [ "${PARAM}" = "disk_inode" ]; then
				diskInodeDetails
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
			elif [ "${PARAM}" = "cpu_stats" ]; then
				getCpuStats
			fi
		done
	fi
}

main() {
	echo "TIME : "+`date`
	parseInput $1
}

main $1
