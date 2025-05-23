#!/bin/bash

# NOTE :
#	 Please do not edit this file, as it will be replaced during upgrade.

# Top command - The top command calculates Cpu(s) by looking at the change in CPU time values between samples. 
#				When you first run it, it has no previous sample to compare to, so these initial values are the percentages 
#				since boot

WORKING_DIR=`pwd`

PROCESSOR_NAME=`grep -E 'model name' /proc/cpuinfo | awk -F':' 'NR==1{print $2}'`


getCpuDetails1() {
    awk 'BEGIN {
    }
    {
        #print "Processing Record ",NR,NF;
        if (NR == 2) {
        	#print "parsed value : "$0
        	niceCpuIndex = index($0,"ni,")+3
        	idleCpuIndex = index($0,"id,")
        	idleContentLength = idleCpuIndex - niceCpuIndex
        	#print "idleCpuIndex : "idleCpuIndex
        	#print "niceCpuIndex : "niceCpuIndex
        	cpu_idle_percentage = substr($0,niceCpuIndex,idleContentLength)
			gsub(",", ".", cpu_idle_percentage)
			#print "cpu_idle_percentage : "cpu_idle_percentage
            cpu_util = 100.0 - cpu_idle_percentage
            print "CPU_Name : cpu"
            print "CPU_Idle_Percentage : ",cpu_idle_percentage           
            printf "CPU_Utilization : %.2f\n",cpu_util 
        }
    }' $WORKING_DIR/customer_data.txt
}


getCpuDetails_original() {
	awk 'BEGIN {
		FS=",";
	}
	{
		#print "Processing Record ",NR,NF;
		if (NR == 2) {
			split($4, temp_arr, "%")
			cpu_idle_percentage = temp_arr[1]
			cpu_util = 100 - cpu_idle_percentage
			print "CPU_Name : cpu"
			print "CPU_Idle_Percentage : ",cpu_idle_percentage			
			printf "CPU_Utilization : %.2f\n",cpu_util       
        }
	}' $WORKING_DIR/customer_data.txt
}

getCpuDetails_top() {
    top -b -d1 -n2 | grep -i "Cpu(s)" | awk 'BEGIN {
    }
    {
        print "Processing Record ",NR,NF;
        if (NR == 2) {
        	#print "parsed value : "$0
        	niceCpuIndex = index($0,"ni,")+3
        	idleCpuIndex = index($0,"id,")
        	idleContentLength = idleCpuIndex - niceCpuIndex
        	#print "idleCpuIndex : "idleCpuIndex
        	#print "niceCpuIndex : "niceCpuIndex
        	cpu_idle_percentage = substr($0,niceCpuIndex,idleContentLength)
			gsub(",", ".", cpu_idle_percentage)
			#print "cpu_idle_percentage : "cpu_idle_percentage
            cpu_util = 100.0 - cpu_idle_percentage
            print "CPU_Name : cpu"
            print "CPU_Idle_Percentage : ",cpu_idle_percentage           
            printf "CPU_Utilization : %.2f\n",cpu_util 
        }
    }'
}

getCpuDetails_cust() {
    top -b -d1 -n2 | grep -i "Cpu(s)" | awk 'BEGIN {
        FS="[ %][a-z][a-z],";
    }
    {
        print "Processing Record ",NR,NF;
        if (NR == 2) {
        	#print "Parsing line : "$0
        	#print "Parsed value : "$4
            cpu_idle_percentage = $4
            gsub(",", ".", cpu_idle_percentage)
            cpu_util = 100.0 - cpu_idle_percentage
            print "CPU_Name : cpu"
            print "CPU_Idle_Percentage : ",cpu_idle_percentage           
            printf "CPU_Utilization : %.2f\n",cpu_util 
        }
    }' $WORKING_DIR/echo_text.txt
}

getCpuDetails() {
        topFilteredOutput=`cat $WORKING_DIR/echo_text.txt | awk 'BEGIN{ORS=" ::: ";} /^%Cpu|^Cpu/ '`
        echo $topFilteredOutput        
        echo $topFilteredOutput | awk 'BEGIN{FS=" ::: ";}
        {
                print "NF :",NF
                print "1 : ",$1
                print "2 : ",$2
                for(k=(NF/2+1);k<=NF;k++)
                {
                        split($k,arrBeforeCpuIdleTime,"id|un")
                        print "Substring before cpu idle time : ",arrBeforeCpuIdleTime[1]
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
               
}


main() {
	if [ "$1" == "cpu_util" ]; then
		getCpuDetails
	elif [ "$1" == "cpu_util_original" ]; then
		getCpuDetails_original
	elif [ "$1" == "cpu_util_top" ]; then
		getCpuDetails_top
	elif [ "$1" == "cpu_util_cust" ]; then
		getCpuDetails_cust
	fi
	
}

main $1
