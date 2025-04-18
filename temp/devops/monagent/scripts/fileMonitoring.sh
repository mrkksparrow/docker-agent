#!/bin/bash

searchOnlyContent(){
	keyword=$1
	filename=$2
	case=$3
	lineno=$4
	result=''
	max_value=$5
	if [ "$case" = "True" ]; then
		output=$(tail -n +"$4" "$filename" | grep -cE "$keyword" | awk 'BEGIN {
				ORS="\n";
			}
			{
				print $1
			}')
		if [ "$output" -ge $max_value ]
		then
			result=$(tail -n +"$4" "$filename" | grep -nE "$keyword" | tail -1 )
		fi
	else
		output=$(tail -n +"$4" "$filename" | grep -c -iE "$keyword" | awk 'BEGIN {
				ORS="\n";
			}
			{
				print $1
			}')
		if [ "$output" -ge $max_value ]
		then
			result=$(tail -n +"$4" "$filename" | grep -niE "$keyword" | tail -1 )
		fi
	fi
	if [ "$result" ]
	then
		total_line=$(wc -l < "$filename")
		if [ "$total_line" ]
		then
			echo "$result"
			echo "$total_line"
		fi
	elif [ "$output" ]
	then
		total_line=$(wc -l < "$filename")
		if [ "$total_line" ]
		then
			echo "None"
			echo "$total_line"
		fi
	else
		echo "-1"
	fi
	}

fileSize(){
	fileName=$1
	output=$(du -s "$fileName" | awk 'BEGIN {
				ORS="\n";
		}
		{
			print $1
		}')
	if [ "$output" ]
	then
		echo "$output"
	else
		echo "-1"
	fi
	}
modification(){
	filename=$1
	output=$(stat -c %Y "$filename" | awk 'BEGIN{
				ORS="\n";
		}
		{
			print $1;
		}')
	if [ "$output" ]
	then
		echo "$output"
	else
		echo "-1"
	fi
	}

lastModification(){
	filename=$1
	time=$(echo "$2" | bc)
	output=$(find "$filename" -mmin +$time | awk 'BEGIN {
			}
			{
				print $0
			}')
	echo $output 
	}

fileCount(){
	dirName=$1
	searchLevel=$2
	output=$(find $dirName -maxdepth $searchLevel -type f | wc -l)
	echo $output
}

dirCount(){
	dirName=$1
	searchLevel=$2
	output=$(find $dirName -maxdepth $searchLevel -type d | wc -l)
	echo $output
}

main(){
	if [ "$1" = "content_check" ];	then
		searchOnlyContent "$3" "$2" $4 $5 $6
	elif [ "$1" = "fileSize_check" ];	then		
		fileSize "$2"
	elif [ "$1" = "modification" ] ; then
		modification $2
	elif [ "$1" = "lastModification_check" ];	then
		lastModification "$2" $3
	elif [ "$1" = "fc" ]; then
	    fileCount $2 $3
	elif [ "$1" = "dc" ]; then
	    dirCount $2 $3
	fi
	}

main $1 "$2" "$3" $4 $5 $6





