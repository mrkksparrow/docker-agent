#!/bin/sh
#set -x

echoMessage() {
	echo ""
	echo "<<$1>>"	
}

topCommand() {
	echoMessage "top"
    /usr/bin/top -l 2 -s 2 -stats pid,cpu,mem,time,command
}

# Number of reads, writes completed (since the last boot)
diskStats() {
	echoMessage "disk stats"
	top -l 1 | grep "Disks" | awk '{
        split($2,readValues,"/")
        split($4,writeValues,"/")
        
        print "Disk I/O bytes :", readValues[1], " : ", writeValues[1]
    }'
}

diskDetails() {
    echoMessage "disk details"
    df -l | grep -iv "Filesystem" | grep -v "Site24x7Agent" | awk 'BEGIN {
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
                fsys=$1
                ftyp="mount | grep "fsys" | sed 's/,//'"
                ftyp | getline ftype
                split(ftype,filetype," ")
                filetype[4]=substr(filetype[4],2,length(filetype[4]))
                Total_Inodes = $6 + $7
                IUsed = $6
                IFree = $7
                IUsedPer = $8
                if(NF>9)
                {
                        if(NF==10)
                        {
                                printf filetype[4]" -- "$1" -- "$(NF-1) " " $(NF) " -- %.0f -- %.0f \n",(($(3)*1024)+($(4)*1024)/2), ($(4)*1024/2)
                        }
                        else
                        {
                                printf filetype[4]" -- "$1" -- "$(NF-2) " "$(NF-1) " " $(NF) " -- %.0f -- %.0f \n",(($(3)*1024)+($(4)*1024)/2), ($(4)*1024/2)
                        }
                }
                else
                {
                        print filetype[4]" -- "$1" -- "$NF" -- "Total_Inodes" -- "IUsed" -- "IFree" -- "IUsedPer" -- "(($(3)*1024)+($(4)*1024))" -- " $4*1024
                }
            }
        }
    }'
}


rcaDiskDetails() {
	echoMessage "rca disk details"
    df -lh | grep -iv Filesystem | grep -v "Site24x7Agent" | awk 'BEGIN {
        ORS="\n";
        partitionNameArray[0] = 0;
    }
    {       
        #print "Processing Record ",NR,NF, $0;
        stdFieldCount=9
        if ($NF in partitionNameArray == 0)
        {
            partitionNameArray[$stdFieldCount] = $stdFieldCount
            partitionSize = $(stdFieldCount-7)
        	partitionUsed = $(stdFieldCount-6)
        	partitionAvail = $(stdFieldCount-5)
        	partitionUsedPercentage = $(stdFieldCount-4) 
            if (NF > 2)
            {
            	print $NF" -- "partitionSize" -- "partitionUsed" -- "partitionAvail" -- "partitionUsedPercentage      
            }
        }
    }'
}

getMemoryDetails() {
        echoMessage "memory details"
        #Total Physical Memory details
        visibleMemorySize=`/usr/sbin/system_profiler SPHardwareDataType | grep Memory | awk '{print ($2*1024*1024)}'`
        echo "TotalVisibleMemorySize : $visibleMemorySize"

        #Free Physical Memory details
        freeMemoryPercent=`memory_pressure | grep "System-wide memory free percentage" | awk '{free_mem=$5; gsub("%","",free_mem); print free_mem}'`
        freePhysicalMemory=`echo $visibleMemorySize $freeMemoryPercent | awk '{printf "%d", (($1*$2)/100)}'`
        usedPhysicalMemory=`echo $visibleMemorySize $freePhysicalMemory | awk '{printf "%d", ($1-$2)}'`

        echo "FreePhysicalMemory : $freePhysicalMemory"
        echo "UsedPhysicalMemory : $usedPhysicalMemory"

        echo "TotalVirtualMemorySize : `sysctl vm.swapusage | awk '{print $4}' | awk -F'.' '{print ($1*1024)}'`"
        echo "FreeVirtualMemory : `sysctl vm.swapusage | awk '{print $10}' | awk -F'.' '{print ($1*1024)}'`"

        #/usr/bin/env uname -rs | awk 'BEGIN{}{print "Linux Distribution : ",$0}'
		sw_vers -ProductVersion | awk 'BEGIN{}{print "OSX version : macOS",$0}'
}

getLoginCount(){
	echoMessage "login_count"
	who -q
}

getCpuDetails() {
	echoMessage "cpu details"
        topFilteredOutput=`top -l 2 -s 1 | awk 'BEGIN{ORS=" ::: ";} /^%CPU usage|^CPU usage/ '`
        echo $topFilteredOutput | awk 'BEGIN{FS=" ::: "; count=0;}
        {
                for(k=(NF/2+1);k<=NF;k++)
                {
                        split($k,arrBeforeCpuIdleTime," idle")
                        split(arrBeforeCpuIdleTime[1],arrAfterNiceCpuTime,"sys")
                        #print "Substring after use nice cpu time : ",arrAfterNiceCpuTime[2]    
                        awkCpu = substr(arrAfterNiceCpuTime[2],2)
                        #print "Extracted ideal percentage : ",awkCpu
                        gsub(",",".",awkCpu)
                        netSumCpuIdealPercentage+=awkCpu
                        count+=1
                }
                
                if(count != 0)                
					cpu_idle_percentage = netSumCpuIdealPercentage/count
				else
					cpu_idle_percentage = netSumCpuIdealPercentage/(NF/2)
                cpu_util = 100.0 - cpu_idle_percentage
                print "CPU_Name : cpu"
                print "CPU_Idle_Percentage : ",cpu_idle_percentage           
                printf "CPU_Utilization : %.2f\n",cpu_util
        }'
               
}

rcaCpuDetails() {
	echoMessage "rca cpu details"
	topFilteredOutput=`top -l 2 -s 1 | awk 'BEGIN{ORS=" ::: ";} /^%CPU usage|^CPU usage/ '`
        echo $topFilteredOutput | awk 'BEGIN{FS=" ::: "; count=0;}
        {
                for(k=(NF/2+1);k<=NF;k++)
                {
                        split($k,arrBeforeCpuIdleTime," idle")
                        split(arrBeforeCpuIdleTime[1],arrAfterNiceCpuTime,"sys")
                        #print "Substring after use nice cpu time : ",arrAfterNiceCpuTime[2]    
                        awkCpu = substr(arrAfterNiceCpuTime[2],2)
                        #print "Extracted ideal percentage : ",awkCpu
                        gsub(",",".",awkCpu)
                        netSumCpuIdealPercentage+=awkCpu
                        count+=1
                }
                
                if(count != 0)                
					cpu_idle_percentage = netSumCpuIdealPercentage/count
				else
					cpu_idle_percentage = netSumCpuIdealPercentage/(NF/2)
                cpu_util = 100.0 - cpu_idle_percentage
                print "CPU_Name : cpu"
                print "CPU_Idle_Percentage : ",cpu_idle_percentage           
                printf "CPU_Utilization : %.2f\n",cpu_util
        }'
        echo "Interrupts : 0"
		echo "Context Switches : 0"
}

psCommand() {
        echoMessage "ps"
                /bin/ps -eo pid,user,pri,etime,comm,pcpu,pmem,wq,command,args| grep -v -w grep | grep -v -w /bin/ps | grep -v -w awk | grep -v "\[sh] <defunct>" | awk 'BEGIN {
                        ORS="\n";
                }
                {
                        #print length($0)
                        if($6 == ($6+0))
                        {
                                user= $2
                                pri= $3
                                etime=$4
                                processName = $5
                                pcpu = $6
                                pmem = $7
                                wq = $8
                                exePath = $9
                                oldCommandArgs = $10
                        }
                        else if($7 == ($7+0))
                        {
                                user= $2
                                pri= $3
                                etime=$4
                                processName = $5 " " $6
                                pcpu = $7
                                pmem = $8
                                wq = $9
                                exePath = $10 " " $11
                                oldCommandArgs = $12
                        }
                        else if($8 == ($8+0))
                        {
                                user= $2
                                pri= $3
                                etime=$4
                                processName = $5 " " $6 " " $7
                                pcpu = $8
                                pmem = $9
                                wq = $10
                                exePath = $11 " " $12 " " $13
                                oldCommandArgs = $14
                        }
                        else
                        {
                                user= $2
                                pri= $3
                                etime=$4
                                processName = $5 " " $6 " " $7 " " $8
                                pcpu = $9
                                pmem = $10
                                wq = $11
                                exePath = $12 " " $13 " " $14 " " $15
                                oldCommandArgs = $16
                        }
                        if(wq == "-")
                        {
                                wq = 0
                        }
                        commandArgs = substr($0,90,length($0))
                        gsub("\"", "\\\"", processName)
                        gsub("\"", "\\\"", exePath)
                        gsub("\"", "\\\"", commandArgs)
                        if (NR == 1) {
                print "PID USER PRIORITY UPTIME COMMAND  %CPU %MEM NLWP COMMAND                     ARGS"
            }
            if (NR > 1 ) {
                handleCount = 0
                #handleCountCommand = "/usr/sbin/lsof -p "$1" | /usr/bin/wc -l"
                #handleCountStatus = (handleCountCommand | getline handleCount)

                print $1" :: "user" :: "pri" :: "etime" :: "processName" :: "pcpu" :: "pmem" :: "wq" :: "handleCount" :: "exePath" :: "commandArgs
            }
     }'
}

#  page details (since the last boot)
getMemoryStats() {
	echoMessage "memory stats"
#	sysctl vm.stats.vm.v_swappgsin vm.stats.vm.v_swappgsout vm.stats.vm.v_io_faults | awk 'BEGIN{
#		FS=":"
#	}
#	{
#        	if(NR==1) {print"pgpgin",$2}
#       		else if (NR==2) {print"pgpgout",$2}
#        	else if (NR==3) {print"pgfault",$2}
#	}'
	echo "pgpgin `vm_stat | grep Pageins | awk '{print $2}'`"
	echo "pgpgout `vm_stat | grep Pageouts | awk '{print $2}'`"
	echo "pgfault `vm_stat | grep faults | awk '{print $3}'`"
}

osArchitecture() {
	echoMessage "os architecture"
    echo "Architecture : `uname -a | awk '{print $15}'`"
}

getCpuInterrupts() {
	echoMessage "cpu interrupt"
	#vmstat | awk 'BEGIN{FS=" "}{if(NR==3) print "Interrupts :"$(NF-5)}'
	echo "Interrupts : 0"
}

getCpuContextSwitches() {
	echoMessage "cpu context switches"
	#vmstat | awk 'BEGIN{FS=" "}{if(NR==3) print "Context Switches :"$(NF-3)}'
	echo "Context Switches : 0"
}

getProcessorName() {
        echoMessage "processor"
        echo "Processor Name :" `sysctl -n machdep.cpu.brand_string`

}

getCpuCores() {
	echoMessage "cpu cores"
	sysctl hw.physicalcpu | awk '{print "Cpu cores :",$2}'
}

cpuCoreDetails() {
	echoMessage "cpu cores usage"
	echo "cpu0 -- 0 -- 0 -- 0 -- 0 -- 0 -- 0 -- 0 -- 0 -- 0 -- 0"
	echo "cpu1 -- 0 -- 0 -- 0 -- 0 -- 0 -- 0 -- 0 -- 0 -- 0 -- 0"
	echo "cpu2 -- 0 -- 0 -- 0 -- 0 -- 0 -- 0 -- 0 -- 0 -- 0 -- 0"
	echo "cpu3 -- 0 -- 0 -- 0 -- 0 -- 0 -- 0 -- 0 -- 0 -- 0 -- 0"
}

loadProcessQueue(){
	echoMessage "process_queue"
	echo "procs_running `top -l 1 | grep  "Processes" | awk '{print $4}'`"
	echo "procs_blocked `top -l 1 | grep  "Processes" | awk '{print $6}'`"
	
}

cpuCoreDetails_temp() {
	echoMessage "cpu cores usage"
	vmstat -h -P -w 1 -c 2 | awk 'BEGIN{
        cCount=0;
        ctr=0;
	
}
{
        if(NR==1)
        {
                cCount=gsub('/cpu/',"");
        }
        if(NR == 4)
        {
                #print "New iteration"
                while(ctr<cCount){
                        idleIndex = 3*(ctr)*(-1)
                        #sysIndex = 3*(ctr)*(-1) - 1
                        #usedIndex = 3*(ctr)*(-1) - 2                        
			cpuIndex = cCount - ctr - 1
                        print cpuIndex,"--",100 - $(NF + idleIndex);
                        ctr=ctr+1;
                }
                ctr = 0;
        }
}'
}

fetchCpuLoad_temp(){
echoMessage "CPU Load"
uptime | awk 'BEGIN{
FS="load average[s]*[:]*"}
{print $2}
END{}' | awk 'BEGIN{
FS=","}
{print "1 minute --"$1,"\n5 minute --"$2,"\n15 minutes --"$3}'
}

fetchCpuLoad()
{
	echoMessage "CPU Load"
	echo "1 minute -- `sysctl vm.loadavg | awk '{print $3}'`"
	echo "5 minute -- `sysctl vm.loadavg | awk '{print $4}'`"
	echo "15 minutes -- `sysctl vm.loadavg | awk '{print $5}'`"
	echo "total_process -- `top -l 1 | grep  "Processes" | awk '{print $4}'`/`top -l 1 | grep  "Processes" | awk '{print $2}'`"
	netstat | awk '/Active Internet connections/,/Active Multipath Internet connections/' | grep -v 'Active \|Proto' | wc -l | awk '{print "listening sockets -- "$1}'
}

fetchRcaInterfaceStatus() {
	echoMessage "rca interface details"
	networksetup -listallhardwareports | awk 'BEGIN{
        name=""; 
        status="up";
        lc=0;
    }
    {
        if(NR>1)
        {
            iostatOutput = "";
            lc = lc+1
            if(index($1,"Device") == 1)
            {
                name = $2
                split(name, tempName, " ")
                if(tempName[2])
                        name=tempName[2]                        
            }
        
            statcom = "ifconfig "name" 2>/dev/null | grep status"
	    	stat = ( statcom | getline statop )
            if(statop != "")
            {
				split(statop,statopSplitted," ")
				if(statopSplitted[2]!="active")
				{
					status="down";
				}
	    	}
	    
            if(lc%4 == 0)
            {
                print name,"--",status
            }
        }
    }'
}

fetchInterfaceData(){
    echoMessage "interface data"
    ifconfig | grep "UP" | awk 'BEGIN{
        nameReadable="";
        name="";
        mac="";
        inpackets=0;
        inbytes=0;
        outpackets=0;
        outbytes=0;
        outdrop=0;
        error=0;
        status=0;
        lc=0;
    }
    {
        if(NR>1)
        {
        		outdrop=0
        		error=0
                ip6=""
                ip4=""
                ipfour="-"
                ipsix="-"
                iostatOutput = "";
                lc = lc+1
                name = $1
                gsub(":","",name)

                iostatCommand = "netstat -nbid -I "name" | grep -v 'Name'"
                iostatCommandStatus = ( iostatCommand | getline iostatOutput )

                if(iostatOutput != "")
                {
                    split(iostatOutput,iostatOutputSplitted," ")

                    inpackets = iostatOutputSplitted[5]

                    inbytes = iostatOutputSplitted[7]

                    outpackets = iostatOutputSplitted[8]

                    outbytes = iostatOutputSplitted[10]
					
					#some interfaces doesnt give outdrop and error data hence,
					if(iostatOutputSplitted[12] != "")	
                    	outdrop = iostatOutputSplitted[12]
					if(iostatOutputSplitted[6] != "") 
                    	error = iostatOutputSplitted[6]+iostatOutputSplitted[9]
                }
                else
                {
                    inpackets = 0;
                    inbytes = 0;
                    outpackets = 0;
                    outbytes = 0;
                    outdrop = 0;
                    error=0;
                }

                statcom = "ifconfig "name" | grep status"
                stat = ( statcom | getline statop )
                if(statop != "")
                {
                    split(statop,statopSplitted," ")
                    if(statopSplitted[2]=="active")
                    {
                        status=1;
                    }
                    else
                    {
                        status=0;
                    }
                }
                mac = "ifconfig "name" | grep -w ether"
                mac | getline macaddrs
                split(macaddrs,macAddress," ")	
                mac=macAddress[2]
                if(mac=="")
                    mac="00:00:00:00:00:00"

                ipv4 =  "ifconfig "name" | grep -w inet | head -n 1"
                ipv4 | getline ip4
                ipv6 =  "ifconfig "name" | grep -w inet6 | head -n 1"
                ipv6 | getline ip6
                if(ip4 != "")
                {
                    split(ip4,ip4splitted, " ");
                    ipfour = ip4splitted[2];
                }
                if(ip6 !="")
                {
                    split(ip6,ip6splitted, " ");
                    ipsix=substr( ip6splitted[2], 1, length(ip6splitted[2])-(length(name)+1));
                }
                print name,"--",status,"--",mac,"--",inpackets,"--",inbytes,"--",outpackets,"--",outbytes,"--",outdrop,"--",error,"--",ipfour,"--",ipsix
        }
    }'
}

fetchRcaTrafficDetails() {
	echoMessage "rca interface traffic"
		networksetup -listallhardwareports | awk 'BEGIN{
        nameReadable=""; 
        name=""; 
        mac="";
        inpackets=0;
        inbytes=0;
        outpackets=0;
        outbytes=0;
        outdrop=0;
        error=0;
        status=1;
        lc=0;
    }
    {
        if(NR>1)
        {
            iostatOutput = "";
            lc = lc+1
            if(index($1,"Device") == 1)
            {
                name = $2
                split(name, tempName, " ")
                if(tempName[2])
                        name=tempName[2]
                        
                iostatCommand = "netstat -nbid -I "name" | grep -v 'Name'"
                iostatCommandStatus = ( iostatCommand | getline iostatOutput )
                
                if(iostatOutput != "")
                {
                    split(iostatOutput,iostatOutputSplitted," ")
               
                    inpackets = iostatOutputSplitted[5]
                
                    inbytes = iostatOutputSplitted[7]
            
                    outpackets = iostatOutputSplitted[8]
            
                    outbytes = iostatOutputSplitted[10]
            
                    outdrop = iostatOutputSplitted[12]
                    
                    error = iostatOutputSplitted[6]+iostatOutputSplitted[9]
                }
                else
                {
                    inpackets = 0;
                    inbytes = 0;
                    outpackets = 0;
                    outbytes = 0;
                    outdrop = 0;
                    error=0;
                }
            }
        
            if(index($1,"Hardware") == 1)
            {
                nameReadable = $3
                split(nameReadable, tempNameReadable, " ")
                if(tempNameReadable[2])
                        nameReadable=tempNameReadable[2]
            }
        
            if(index($1,"Ethernet") == 1)
            {
                mac = $3
                split(mac, tempMac, " ")
                if(tempMac[2])
                        mac=tempName[2]
            }
            
            if(lc%4 == 0)
            {
                print name,"--",inbytes,"--",inpackets,"--",outbytes,"--",outpackets,"--",outdrop,"--",error
            }
        }
    }'
}

userSessions(){
	echoMessage "user sessions"
        last | head -n 20 | awk 'BEGIN {
                ORS="\n";
        }
        {
                column1=$1
                column2=$2
                column3="'`hostname`'"
                column4=substr($0,41)
                gsub(/^[ \t]+|[ \t]+$/,"",column1)
                gsub(/^[ \t]+|[ \t]+$/,"",column2)
                gsub(/^[ \t]+|[ \t]+$/,"",column3)
                gsub(/^[ \t]+|[ \t]+$/,"",column4)
                if (column1  !~ /^ *$/ && column1 !~ /^utx/ && column2 !~ /^ *$/ && column3  !~ /^ *$/ )
                {
                        print column1 " ::: "column2" ::: "column3" ::: "column4
                }

        }'
}

diskErrors() {
	echoMessage "disk errors"
	sudo dmesg | grep -w "I/O error\|EXT2-fs error\|EXT3-fs error\|EXT4-fs error\|UncorrectableError\|DriveReady SeekComplete Error\|I/O Error Detected" | sort -u	
}

dmesgErrors() {
	echoMessage "dmesg errors"
	sudo dmesg | grep -i 'error' | tail -n 10	
}

uptimeDetails() {
	echoMessage "uptime details"
	uptime	| cut -d , -f 1,2,3
}

parseInput() {
	if [ "$1" != "" ]; then
		IFS=","
		for PARAM in $1; do
			#echo "PARAM : $PARAM"
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
			elif [ "${PARAM}" = "login_count" ]; then
				getLoginCount
			elif [ "${PARAM}" = "inst_soft" ]; then
				installedSoftware
			elif [ "${PARAM}" = "topCommand" ]; then
				topCommand
			elif [ "${PARAM}" = "psCommand" ]; then
				psCommand
			elif [ "${PARAM}" = "process_queue" ]; then
				loadProcessQueue
			elif [ "${PARAM}" = "core_usage" ]; then
				cpuCoreDetails
			elif [ "${PARAM}" = "load_data" ]; then
				fetchCpuLoad			
			fi
		done
	fi
}

main() {
	echo "TIME : "+`date`
	#setUserSessionsCommand
	parseInput $1
	#detectOSAndDistro
}

main $1
