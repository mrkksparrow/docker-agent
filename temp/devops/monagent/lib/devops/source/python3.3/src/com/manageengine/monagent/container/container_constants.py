# $Id$

BLKIO_PERF_METRICS = ["sectors_recursive", "io_service_bytes_recursive", "io_serviced_recursive", "io_queue_recursive",\
                             "io_service_time_recursive", "io_wait_time_recursive", "io_merged_recursive", "io_time_recursive"]
NET_PERF_METRICS = ['rx_bytes','tx_bytes','traffic']
CPU_PERF_METRICS = ['cpu_percent']
MEM_PERF_METRICS = ['active_anon','inactive_anon','active_file','inactive_file','cache','pgpgin','pgpgout','rss','unevictable']
PERF_METRICS = ["NetworkPerf", "CpuPerf", "MemoryPerf", "BlkioPerf"]