#!/bin/bash
check(){
        path=$1
	ipaddr=$(mount -l -t nfs,nfs4,nfs2,nfs3 | grep -w "$path" | awk -F'[(|,|=|)]' '{ for(i=1;i<=NF;i++) if ($i == "addr") print $(i+1) }')
        if [ "$ipaddr" ]; then
                while read line
                do
                        output=$(rpcinfo -u "$line" nfs 2>/dev/null | egrep -i "ready|waiting")
                        if [ $? == 0 ]; then
                                status="$line%%1"
                                df_out=$(df | grep -w "$path")
                        else
                                status="$line%%0"
                        fi
                done <<< $ipaddr
        else
                status=-1
        fi
	echo $status"|"$df_out
}
main(){
        check $@
}
main $@