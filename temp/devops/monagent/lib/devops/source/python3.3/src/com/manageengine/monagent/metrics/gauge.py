#$Id$
import logging
import traceback
from com.manageengine.monagent.metrics import metrics_constants
from com.manageengine.monagent.metrics import metrics_util
from com.manageengine.monagent.metrics import metrics_logger

def gauge_storing(unique_key,name,value,sample_rate,tags,self):
	try:
		value=float(value)
		if unique_key in self.gauge_obj:
			if '+' in str(value) or '-' in str(value):
				self.gauge_obj[unique_key]['value']=self.gauge_obj[unique_key]['value']+value
			else:
				self.gauge_obj[unique_key]['value']=value
		else:
			self.gauge_obj[unique_key]={}
			self.gauge_obj[unique_key]['value'] = value
		self.gauge_obj[unique_key]['n'] = name
		if tags:
			self.gauge_obj[unique_key]['dimensions'] = tags
		if 'gauge' not in self.key_data:
			self.key_data['gauge'] = {}
		if unique_key not in self.key_data['gauge']:
			self.key_data['gauge'][unique_key]=dict(self.gauge_obj[unique_key])
			self.key_data['gauge'][unique_key].pop('value')
	except Exception as e:
		metrics_logger.errlog('Exception while processing Gauge metrics : {}'.format(e))	
		