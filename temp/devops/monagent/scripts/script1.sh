#!/bin/bash

getCpuInterrupts(){
	echoMessage "cpu interrupt"
	cat /proc/stat | grep -i 'intr ' | awk '{ print "Interrupts :",$2 }'
}

getProcessorName(){
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

parseInput(){
	if [ "$1" == "cpu_intr" ]; then
		getCpuInterrupts
	elif [ "$1" == "processor" ]; then
		getProcessorName
	fi
}

main(){
	parseInput $1
}

main $1
