import traceback
import sys,os,atexit
import signal,time
import logging
from com.manageengine.monagent.metrics import metrics_constants
from com.manageengine.monagent.metrics import metrics_logger


class Daemon:
	"""
	A generic daemon class.

	Usage: subclass the Daemon class and override the run() method
	"""

	def __init__(self, pidfile):
		self.pidfile = pidfile
	

	def daemonize(self):
		try:
			pid = os.fork()
			if pid > 0:
				sys.exit(0)
		except Exception as e:
			sys.exit(1)

		os.chdir("/")
		os.setsid()
		os.umask(0)
	
        # do second fork
		try:
			pid = os.fork()
			if pid > 0:
                # exit from second parent
				sys.exit(0)
		except Exception as e:
            #sys.stderr.write("fork #2 failed: %d (%s)\n" %(err.errno, err.strerror))
			sys.exit(1)

		atexit.register(self.delpid)
		pid = str(os.getpid())
		with open(self.pidfile, 'w') as fp:
			fp.write(pid)
		return pid

	def delpid(self):
		os.remove(self.pidfile)

	def start(self, *args, **kw):
		try:
			with open(self.pidfile,'r') as r:
				pid=r.read()
				pid=int(pid.strip())
			r.close()
		except IOError:
			pid = None
	
	
		if pid:
			message = "pidfile %s already exist. Site24x7 Metrics Agent already running\n"
			metrics_logger.log(message)
			sys.stderr.write(message % self.pidfile)
			sys.exit(1)

		pid_value = self.daemonize()
		metrics_logger.log('Site24x7 Metrics Agent started Successfully (process id : {})'.format(pid_value))
		sys.stdout.write('\n Site24x7 Metrics Agent started Successfully (process id : {})'.format(pid_value)+'\n')
		self.run(*args, **kw)
	
	def status(self):
		try:
			if os.path.exists(self.pidfile):
				metrics_logger.log('\n Site24x7 Metrics Agent Running (process id : {})'.format(self.get_pid()) +'\n')
				sys.stdout.write('\n Site24x7 Metrics Agent Running (process id : {})'.format(self.get_pid()) +'\n')
			else:
				sys.stdout.write('\n Site24x7 Metrics Agent is down \n')
		except Exception as e:
			traceback.print_exc()
	
	def get_pid(self):
		pid_val = None
		try:
			with open(self.pidfile,'r') as r:
				pid_val=r.read()
				pid_val=int(pid_val.strip())
			r.close()
		except Exception as e:
			traceback.print_exc()
		return pid_val
	
	def stop(self):
		try:
			with open(self.pidfile,'r') as r:
				pid=r.read()
				pid=int(pid.strip())
			r.close()
		except IOError:
			pid = None

		if not pid:
			message = "pidfile %s does not exist. Site24x7 Metrics Agent not running\n"
			sys.stderr.write(message % self.pidfile)
			return
		try:
			while 1:
					os.kill(pid,signal.SIGTERM)
					time.sleep(0.1)
		except Exception as e:
			err = str(e)
			if err.find("No such process") > 0:
				if os.path.exists(self.pidfile):
					os.remove(self.pidfile)
					metrics_logger.log('Site24x7 Metrics Agent Stopped Successfully \n')
					sys.stdout.write('\n Site24x7 Metrics Agent Stopped Successfully \n')
				else:
					metrics_logger.errlog(str(err))
					sys.exit(1)			