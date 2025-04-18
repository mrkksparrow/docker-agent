#!/bin/bash
#set -x
SUCCESS=0
FAILURE=1
export LC_NUMERIC="en_US"


echoMessage() {
	echo ""
	echo "<<$1>>"	
}

getdiskDetails() {
    echoMessage "disk details"
    df -kl | grep -iv Filesystem | /usr/xpg4/bin/awk 'BEGIN {
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
		        printf $NF" -- "$(NF-5)" -- %.0f -- %.0f -- %.0f \n",($(NF-1)),($(NF-3)),($(NF-4))      
            }
        }
    }'
}

getCpuDetails() {
	echoMessage "cpu_util"
    /usr/bin/vmstat 1 3
}

getMemoryDetails() {
        echoMessage "mem_util"
        /usr/sbin/swap -l|awk '{TOT+=$4} {FREE+=$5} END {print "total: "TOT "  used: " TOT-FREE}';/usr/sbin/prtconf|grep Memory;vmstat 1 3;kstat zfs:0:arcstats:size | grep size|tr -s ' ' ''|tr -s '\t' '^'
}

parseInput() {
	if [ "$1" != "" ]; then
		for PARAM in ${1//,/ }; do
			#echo "PARAM : $PARAM"
			if [ "${PARAM}" = "cpu_util" ]; then
				getCpuDetails
			elif [ "${PARAM}" = "disk_details" ]; then
				getdiskDetails
			elif [ "${PARAM}" = "mem_util" ]; then
				getMemoryDetails
			fi
		done
	fi
}

main() {
	echo "TIME : "+`date`
	parseInput $1
}

main $1
