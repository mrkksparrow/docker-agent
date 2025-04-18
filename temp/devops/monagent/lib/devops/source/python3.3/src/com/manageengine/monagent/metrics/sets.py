#$Id$
import traceback
from com.manageengine.monagent.metrics import metrics_constants
from com.manageengine.monagent.metrics import metrics_logger

def sets_storing(unique_key,name,set_value,sample_rate,tags,self):
	try:
		if 'set' not in self.key_data:
			self.key_data['set'] = {}
		if unique_key not in self.sets_obj:
			self.sets_obj[unique_key] = {}
			self.sets_obj[unique_key]['elements']=[]
		self.sets_obj[unique_key]['elements'].append(set_value)
		if tags:
			self.sets_obj[unique_key]['dimensions'] = tags
		self.sets_obj[unique_key]['n']=name
		self.sets_obj[unique_key]['value']=len(set(self.sets_obj[unique_key]['elements']))
		if unique_key not in self.key_data['set']:
			self.key_data['set'][unique_key]=dict(self.sets_obj.get(unique_key))
			self.key_data['set'][unique_key].pop("elements")
			self.key_data['set'][unique_key].pop("value")
	except Exception as e:
		metrics_logger.errlog('Exception while processing Set metrics : {}'.format(e))
