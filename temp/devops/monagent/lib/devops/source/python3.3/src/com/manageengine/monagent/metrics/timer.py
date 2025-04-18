#$Id$
import traceback
from com.manageengine.monagent.metrics import metrics_constants
from com.manageengine.monagent.metrics import metrics_logger

def time_calculation(unique_key,name,value,sample_rate,tags,self):
	try:
		value=float(value)
		multiplier=1/sample_rate
		value=value*multiplier
		if "timer" in self.key_data.keys() and unique_key in self.key_data["timer"].keys():
			self.timer_obj[unique_key]={}
			self.timer_obj[unique_key]['value']=value
			self.timer_obj[unique_key]['total_value']=self.key_data["timer"][unique_key]['total_value']+value
			self.timer_obj[unique_key]['count']=self.key_data["timer"][unique_key]['count']+1
			self.timer_obj[unique_key]['mean'] = self.timer_obj[unique_key]['total_value'] / self.timer_obj[unique_key]['count']
			if (value) > self.key_data["timer"][unique_key]['max']:
				self.timer_obj[unique_key]['max'] = value
			else:
				self.timer_obj[unique_key]['max'] = self.key_data["timer"][unique_key]['max']
			if (value) < self.key_data["timer"][unique_key]['min']:
				self.timer_obj[unique_key]['min'] = value	
			else:
				self.timer_obj[unique_key]['min'] = self.key_data["timer"][unique_key]['min']
		else:
			self.timer_obj[unique_key]={}
			self.timer_obj[unique_key]['value']=value
			self.timer_obj[unique_key]['total_value']=value
			self.timer_obj[unique_key]['mean']=value
			self.timer_obj[unique_key]['count']=int(1)
			self.timer_obj[unique_key]['max']=value
			self.timer_obj[unique_key]['min']=value
		if tags:
			self.timer_obj[unique_key]['dimensions']=tags
		self.timer_obj[unique_key]['n'] = name
		if 'timer' not in self.key_data:
			self.key_data['timer'] = {}
		if unique_key not in self.key_data['timer'].keys():
			self.key_data['timer'][unique_key] = {}
		self.key_data['timer'][unique_key]=self.timer_obj[unique_key]
	except Exception as e:
		metrics_logger.errlog('Exception while processing Timer metrics : {}'.format(e))	
		
