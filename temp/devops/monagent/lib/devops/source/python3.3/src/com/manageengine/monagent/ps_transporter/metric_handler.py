'''
Created on 28-Dec-2016

@author: giri
'''
TOTAL_CPU = ['user', 'nice', 'system', 'idle', 'nice', 'irq', 'softirq', 'iowait', 'steal', 'guest', 'nice']
TOTAL_IDLE = ['idle', 'iowait']
SUB_SWAP_MEM = ['sin', 'sout']
SWAP_MEM = ['used', 'free']
PROC_CPU_METRICS = ['cpu_user', 'cpu_system']
PROC_MEM_METRICS = ['reads', 'writes', 'bytes_read', 'bytes_write']
PROC_METRICS=['fds', 'rss', 'vms', 'total']
INTERVAL = 5