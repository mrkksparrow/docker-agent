#!/bin/sh
#set -x

echoMessage() {
	echo ""
	echo "<<$1>>"	
}

topCommand() {
	echoMessage "top"
        /usr/bin/top -b -s 2 -d 2 all	
}

diskStats() {
	echoMessage "disk stats"
	#in kb/sec
	iostat -x | awk 'BEGIN {
	totalWrites=0
	totalReads=0
	}
	{
		if(NR>2)
		{
			totalReads = totalReads+$4
			totalWrites=totalWrites+$5
		}
	}
	END{ print "Disk I/O bytes : "totalReads" : "totalWrites }'
}

diskDetails() {
	echoMessage "disk details"
    df -lTi | grep -iv Filesystem | awk 'BEGIN {
        ORS="\n";
        partitionNameArray[0] = 0;
    }
    {       
        #print "Processing Record ",NR,NF,$NF;
        Total_Inodes = $7 + $8
        IUsed = $7
        IFree = $8
        IUsedPer = $9
        if ($NF in partitionNameArray == 0)
        {
            partitionNameArray[$NF] = $NF
            if (NF > 2)
            {
				print $2" -- "$1" -- "$NF" -- "Total_Inodes" -- "IUsed" -- "IFree" -- "IUsedPer" -- "(($(4)*1024)+($(5)*1024))" -- "$(5)*1024      
            }
        }
    }'
}

rcaDiskDetails() {
	echoMessage "rca disk details"
    df -l -Th | grep -iv Filesystem | awk 'BEGIN {
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

getMemoryDetails() {
	echoMessage "memory details"
	#Total Physical Memory details
	TotalVisibleMemorySize=`echo $(sysctl -n hw.physmem | awk '{ print int($1/1024) }')`
	
	#Free Physical Memory details	
	FreePhysicalMemory=$(vmstat -H | awk 'BEGIN{
	freePhy=0
	ORS="\n"
	}
	{
	if (NR == 3)
	{       print $5
			freephy = $5
	}
	}
	END{if(freePhy==0) print $freephy}')
	usedPhysicalMemory=`echo $TotalVisibleMemorySize $FreePhysicalMemory | awk '{printf "%d", ($1-$2)}'`
	echo "TotalVisibleMemorySize : $TotalVisibleMemorySize"
	echo "FreePhysicalMemory : $FreePhysicalMemory"
	echo "UsedPhysicalMemory : $usedPhysicalMemory"

	#Virtual Memory Details
	swapinfo -k | awk 'BEGIN{
	ORS="\n";
	FS=" ";
	virtTotal=0
	virtFree=0
	}
	{
	if(NR > 1)
	{       
		virtTotal=virtTotal + $(NF-3);
		virtFree=virtFree + $(NF-1);
	}
	}END{print "TotalVirtualMemorySize :",virtTotal,"\nFreeVirtualMemory :",virtFree}'
	       
	/usr/bin/env uname -rs | awk 'BEGIN{}{print "FreeBSD Version : ",$0}'
}

getCpuDetails() {
	echoMessage "cpu details"
        topFilteredOutput=`/usr/bin/top -b -s 3 -d 3 | awk 'BEGIN{ORS=" ::: ";} /^CPU:|^Cpu/ '`
        #echo $topFilteredOutput        
        echo $topFilteredOutput | awk 'BEGIN{FS=" ::: "; count=0;}
        {
                #print NF
                #print $1
                #print $2
                for(k=(NF/2+1);k<=NF;k++)
                {
                        split($k,arrBeforeCpuIdleTime,"id|un")
                        #print "Substring before cpu idle time : ",arrBeforeCpuIdleTime[1]
                        split(arrBeforeCpuIdleTime[1],arrAfterNiceCpuTime,"interrupt")
                        #print "Substring after use nice cpu time : ",arrAfterNiceCpuTime[2]    
                        awkCpu = substr(arrAfterNiceCpuTime[2],2)
                        #print "Extracted ideal percentage : ",awkCpu
                        gsub(",",".",awkCpu)
                        netSumCpuIdealPercentage+=awkCpu
			count+=1
                }
                #print "Net sum  Cpu ideal percentage : ",netSumCpuIdealPercentage
		if(count != 0)                
		cpu_idle_percentage = netSumCpuIdealPercentage/count
		else
		cpu_idle_percentage = netSumCpuIdealPercentage/(NF/2)
                #print "cpu_idle_percentage: ",cpu_idle_percentage
                cpu_util = 100.0 - cpu_idle_percentage
                print "CPU_Name : cpu"
                print "CPU_Idle_Percentage : ",cpu_idle_percentage           
                printf "CPU_Utilization : %.2f\n",cpu_util
        }'
               
}

rcaCpuDetails() {
	echoMessage "rca cpu details"
	rcaTopFilteredOutput=`/usr/bin/top -b -s 3 -d 3 | awk 'BEGIN{ORS=" ::: ";} /^CPU:|^Cpu/ '`
        #echo $topFilteredOutput        
        echo $rcaTopFilteredOutput | awk 'BEGIN{FS=" ::: "; count=0;}
        {
                #print NF
                #print $1
                #print $2
                for(k=(NF/2+1);k<=NF;k++)
                {
                        split($k,arrBeforeCpuIdleTime,"id|un")
                        #print "Substring before cpu idle time : ",arrBeforeCpuIdleTime[1]
                        split(arrBeforeCpuIdleTime[1],arrAfterNiceCpuTime,"interrupt")
                        #print "Substring after use nice cpu time : ",arrAfterNiceCpuTime[2]    
                        awkCpu = substr(arrAfterNiceCpuTime[2],2)
                        #print "Extracted ideal percentage : ",awkCpu
                        gsub(",",".",awkCpu)
                        netSumCpuIdealPercentage+=awkCpu
			count+=1
                }
                #print "Net sum  Cpu ideal percentage : ",netSumCpuIdealPercentage
		if(count != 0)                
		cpu_idle_percentage = netSumCpuIdealPercentage/count
		else
		cpu_idle_percentage = netSumCpuIdealPercentage/(NF/2)
                #print "cpu_idle_percentage: ",cpu_idle_percentage
                cpu_util = 100.0 - cpu_idle_percentage
                print "CPU_Name : cpu"
                print "CPU_Idle_Percentage : ",cpu_idle_percentage           
                printf "CPU_Utilization : %.2f\n",cpu_util
        }'
	
	# vmstat per second
    vmstat 1 2 | awk 'BEGIN{FS=" "}{if(NR==4) print "Interrupts :"$(NF-5)}'
    vmstat 1 2 | awk 'BEGIN{FS=" "}{if(NR==4) print "Context Switches :"$(NF-3)}'
    #cat /proc/stat | grep -i 'intr ' | awk '{ print "Interrupts :",$2 }'
    #cat /proc/stat | grep -i 'ctxt ' | awk '{ print "Context Switches :",$2 }'

}


psCommand() {
		echoMessage "ps"
        /bin/ps a -wx -c -eo pid,user,pri,etimes,comm,pcpu,pmem,nlwp,command,args| grep -v -w grep | grep -v -w /bin/ps | grep -v -w awk | grep -v "\[sh] <defunct>" | awk 'BEGIN {
        ORS="\n";
        }
        {
	        #print length($0)
			user = $2
			pri = $3
			uptime=$4
			processName = $5
			exePath = $9
			oldCommandArgs = $10
			commandArgs = substr($0,60,length($0))
			gsub("\"", "\\\"", processName)
			gsub("\"", "\\\"", exePath)
			gsub("\"", "\\\"", commandArgs)
			awkProcessIndex = index(commandArgs,"ishandleCountCommandSuccess")
			if (awkProcessIndex == 0) {
					if (NR == 1) {
							print "PID USER PRIORITY  UPTIME  COMMAND  %CPU %MEM NLWP COMMAND                     ARGS"
					}
					if (NR > 1) {
							fd = 0
							lastField = ""
							#handleCountCommand = "ls /proc/"$1"/fd | /usr/bin/wc -l"
							#ishandleCountCommandSuccess = (handleCountCommand | getline fd)
							#print "error: "ishandleCountCommandSuccess
							for(i=10;i<=NF;i++)
							{
									lastField=lastField" "$i
							}

							print $1" :: "user" :: "pri" :: "uptime" :: "processName" :: "$6" :: "$7" :: "$8" :: "fd" :: "oldCommandArgs" :: "commandArgs
					}
		}
		}'
}

getMemoryStats() {
	echoMessage "memory stats"
	sysctl vm.stats.vm.v_swappgsin vm.stats.vm.v_swappgsout vm.stats.vm.v_io_faults | awk 'BEGIN{
		FS=":"
	}
	{
        	if(NR==1) {print"pgpgin",$2}
       		else if (NR==2) {print"pgpgout",$2}
        	else if (NR==3) {print"pgfault",$2}
	}'
}

osArchitecture() {
	echoMessage "os architecture"
	uname -p | awk 'BEGIN {
		ORS="\n";
	}
	{	
		#print "Processing Record ",NR,NF,$NF;
		print "Architecture : "$NF
	}'	
}

getCpuInterrupts() {
	echoMessage "cpu interrupt"
	#vmstat per sec 
	vmstat 1 2 | awk 'BEGIN{FS=" "}{if(NR==4) print "Interrupts :"$(NF-5)}'
}

getCpuContextSwitches() {
	echoMessage "cpu context switches"
	#vmstat per sec
	vmstat 1 2 | awk 'BEGIN{FS=" "}{if(NR==4) print "Context Switches :"$(NF-3)}'
}

getProcessorName() {
	echoMessage "processor"
	sysctl hw.model  | awk 'BEGIN {
			FS=":";			
		}
		{
			if (NR == 1) {
				print "Processor Name :",$2
			}
		}'
	
}

getCpuCores() {
	echoMessage "cpu cores"
	sysctl hw.ncpu | awk 'BEGIN {
			FS=":";
			cores=0;
		}
		{
			if(NF==2) cores=$2
		}END{print "Cpu cores :",cores}'
}

cpuCoreDetails() {
	echoMessage "cpu cores usage"
    top -P | grep -w "CPU" | awk 'BEGIN{
	    core=0;
	    outputCount="top -P | grep -w CPU | wc -l"
	    outputCount | getline outputCounts
    }
    {
		gsub("%","")
		if(outputCounts==1) #for single core machine
		        print "cpu"core,"--",$2,"--",$4,"--",$6,"--",$10,"--",0,"--",$8,"--",0,"--",0,"--",0,"--",0
		else
		        print "cpu"core,"--",$3,"--",$5,"--",$7,"--",$11,"--",0,"--",$9,"--",0,"--",0,"--",0,"--",0
		core=core+1
    }'
}

fetchCpuLoad(){
echoMessage "CPU Load"
uptime | awk 'BEGIN{
FS="load average[s]*[:]*"}
{print $2}
END{}' | awk 'BEGIN{
FS=","}
{print "1 minute --"$1,"\n5 minute --"$2,"\n15 minutes --"$3}'
netstat | awk '/Active Internet connections/,/UNIX/' | grep -v 'Active \|Proto' | wc -l | awk '{print "listening sockets -- "$1}'
}

fetchInterfaceData() {
	echoMessage "interface data"
	netstat -nbid | awk 'BEGIN{
    prevIf="None";
    name="";
    mac="";
    inpackets=0;
    inbytes=0;
    outpackets=0;
    outbytes=0;
    outdrop=0;
	status=1;
	ipfour="-";
	ipsix="-";
}
{
if(NR>1)
{
	sameIf = match($1,prevIf)
	if(sameIf == 0 && prevIf != "None")
        {
                print name,"--",status,"--",mac,"--",inpackets,"--",inbytes,"--",outpackets,"--",outbytes,"--",outdrop,"--",ipfour,"--",ipsix
                prevIf=name;
                name="";
                mac="";
                inpackets=0;
                inbytes=0;
                outpackets=0;
                outbytes=0;
                outdrop=0;
				status=1;
				ipfour="-";
				ipsix="-";
        }

        #print "Name "$1
        name=$1
        macAddr = "ifconfig "$1" | grep \"ether \""
        macAddrCommandOutput = ( macAddr | getline macAddress )
        split( macAddress,a," ")
        if(a[2])
                mac=a[2]
        else
                mac="00:00:00:00:00:00"
		
		ip6=""
		ip4=""
		ipv4 =  "ifconfig "name" | grep -w inet | head -n 1"
		ipv4 | getline ip4
		ipv6 =  "ifconfig "name" | grep -w inet6"
		ipv6 | getline ip6
		if(ip4 != "")
		{
			split(ip4,ip4splitted, " ");
			ipfour = ip4splitted[2];
		}
		
		if(ip6 !="")
		{
			split(ip6,ip6splitted, " ");
			ipsix=substr( ip6splitted[2], 1, length(ip6splitted[2])-4);
		}

        if(int($(NF-8)))
        inpackets += $(NF-8)

        if(int($(NF-5)))
        inbytes += $(NF-5)

        if(int($(NF-4)))
        outpackets += $(NF-4)

        if(int($(NF-2)))
        outbytes += $(NF-2)

        if(int($(NF)))
        outdrop += $(NF)

        prevIf = $1
}
}END{
print name,"--",status,"--",mac,"--",inpackets,"--",inbytes,"--",outpackets,"--",outbytes,"--",outdrop,"--",ipfour,"--",ipsix
}'
}

fetchRcaTrafficDetails() {
	echoMessage "rca interface traffic"
	netstat -nbid | awk 'BEGIN{
        prevIf="None";
        name="";
        mac="";
        inpackets=0;
        inbytes=0;
        outpackets=0;
        outbytes=0;
        outdrop=0;
	status=1;
}
{
if(NR>1)
{
       	sameIf = match($1,prevIf)
	if(sameIf == 0 && prevIf != "None")
        {
                print name,"--",inbytes,"--",inpackets,"--",outbytes,"--",outpackets,"--",outdrop
                prevIf=name;
                name="";
                mac="";
                inpackets=0;
                inbytes=0;
                outpackets=0;
                outbytes=0;
                outdrop=0;
		status=1;
        }

        #print "Name%%"$1
        name=$1
        macAddr = "ifconfig "$1" | grep \"ether \""
        macAddrCommandOutput = ( macAddr | getline macAddress )
        split( macAddress,a," ")
        if(a[2])
                mac=a[2]
        else
                mac="NA:"$1
        if(int($(NF-8)))
        inpackets += $(NF-8)

        if(int($(NF-5)))
        inbytes += $(NF-5)

        if(int($(NF-4)))
        outpackets += $(NF-4)

        if(int($(NF-2)))
        outbytes += $(NF-2)

        if(int($(NF)))
        outdrop += $(NF)

        prevIf = $1
}
}END{
print name,"--",inbytes,"--",inpackets,"--",outbytes,"--",outpackets,"--",outdrop
}'
}

userSessions(){
	echoMessage "user sessions"
	last -y | head -n 20 | awk 'BEGIN {
                ORS="\n";
        }
        {
                column1=substr($0,1,8)
                column2=substr($0,10,11)
                column3=substr($0,21,22)
                column4=substr($0,43)
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
			elif [ "${PARAM}" = "inst_soft" ]; then
				installedSoftware
			elif [ "${PARAM}" = "topCommand" ]; then
				topCommand
			elif [ "${PARAM}" = "psCommand" ]; then
				psCommand
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
