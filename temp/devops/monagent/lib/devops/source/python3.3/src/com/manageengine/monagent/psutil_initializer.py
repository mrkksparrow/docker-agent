from ps_collector import *
import time
i=0
while True and not i==2:
    i+=1
    cpu_vcpu_metrics.CpuVcpuMetrics().collect()
    disk_io_metrics.DiskIOMetrics().collect()
    memory_metrics.MemoryMetrics().collect()
    swap_memory_metrics.SwapMemoryMetrics().collect()
    process_metrics.ProcessMetrics().collect()
    time.sleep(5)
    
