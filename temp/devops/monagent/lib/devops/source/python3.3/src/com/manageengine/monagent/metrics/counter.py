#$Id$
import logging
import traceback
import json
from com.manageengine.monagent.metrics import metrics_constants
from com.manageengine.monagent.metrics import metrics_logger

def counting(unique_key,name,value,sample_rate,tags,self):
	try:	
		multiplier=1/float(sample_rate)
		value=float(value)
		value=value*multiplier
		if unique_key in self.counter_obj:
			self.counter_obj[unique_key]['value']=self.counter_obj[unique_key]['value']+(value)	
		else:
			self.counter_obj[unique_key]={}
			self.counter_obj[unique_key]['value'] = value
		if tags:
			self.counter_obj[unique_key]['dimensions'] = tags
		self.counter_obj[unique_key]['n'] = name
		if 'counter' not in self.key_data:
			self.key_data['counter'] = {}
		if unique_key not in self.key_data['counter']:
			self.key_data['counter'][unique_key]=dict(self.counter_obj.get(unique_key))
			self.key_data['counter'][unique_key].pop('value')
	except Exception as e:
			metrics_logger.errlog('Exception while processing counter metrics : {}'.format(e))