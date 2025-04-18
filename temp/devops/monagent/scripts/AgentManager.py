import json
import os, sys, zipfile
try:
	import requests
except:
	pass
try:
    import configparser
except Exception as e:
    import ConfigParser as configparser
import traceback
import collections

MONAGENT_DIR = os.path.dirname(os.path.dirname(os.path.realpath(sys.argv[0])))
MONAGENT_CONF = MONAGENT_DIR + '/conf'
METRICS_DIR = MONAGENT_DIR + '/metrics'
MONAGENT_CONF_FILE = MONAGENT_CONF + '/monagent.cfg'
PLUGIN_CONF_FILE = MONAGENT_CONF + '/pl_id_mapper'
PROMETHEUS_CONF_FILE = METRICS_DIR + '/prometheus/prometheus.cfg'
STATSD_CONF_FILE = METRICS_DIR + '/statsd/statsd.cfg'

STATSD_CONFIG=configparser.RawConfigParser()
PROMETHEUS_CONFIG=configparser.RawConfigParser()
MONAGENT_CONFIG=configparser.RawConfigParser()

STATSD_CONFIG.read(STATSD_CONF_FILE)
PROMETHEUS_CONFIG.read(PROMETHEUS_CONF_FILE)
MONAGENT_CONFIG.read(MONAGENT_CONF_FILE)

def check_prometheus():
	result = ""
	try:
		result += "\n                   Prometheus - {}\n                 -------------------------\n\n".format({True: "Enabled", False: "Disabled"} [ (str(PROMETHEUS_CONFIG.get('PROMETHEUS','enabled')) == "true" or str(PROMETHEUS_CONFIG.get('PROMETHEUS','enabled')) == "1") ])
		for section in PROMETHEUS_CONFIG.sections():
			if section != "PROMETHEUS":
				result = result + "[" + str(section) +"]" + " "*(18-len(str(section))) + "url              : " + str(PROMETHEUS_CONFIG.get(section,'prometheus_url')) + "\n"
				result = result + " "*(20) +"pattern          : " + str(PROMETHEUS_CONFIG.get(section,'include_pattern')) + "\n"
				if PROMETHEUS_CONFIG.has_option(section, "timeout"):
					timeout = PROMETHEUS_CONFIG.get(section,'timeout')
				else:
					timeout = PROMETHEUS_CONFIG.get('PROMETHEUS','timeout')
				result = result + " "*(20) +"timeout          : " + str(timeout) + "\n"
				if PROMETHEUS_CONFIG.has_option(section, "scrape_interval"):
					scrap_interval = PROMETHEUS_CONFIG.get(section,'scrape_interval')
				else:
					scrap_interval = PROMETHEUS_CONFIG.get('PROMETHEUS','scrape_interval')
				result = result + " "*(20) +"scrape interval  : " + str(scrap_interval) + "\n"
				result = result + "\n"
		#result += "Configuration File - {}\n\n".format(str(PROMETHEUS_CONF_FILE))
	except Exception as e:
		result = result + "Something went wrong while analysing Prometheus Monitoring Configuration\nFile   :{}\nError  :  {}\n".format(PROMETHEUS_CONF_FILE,e)
	return result

def check_statsd():
	result = ""
	try:
		result += "\n                     Statsd - {}\n                   ---------------------\n\n".format({True: "Enabled", False: "Disabled"} [ (str(STATSD_CONFIG.get('STATSD','enabled')) == "true" or str(STATSD_CONFIG.get('STATSD','enabled')) == "1" )])
		for section in STATSD_CONFIG.sections():
			result = result + "[" + str(section) +"]" + " "*(18-len(str(section))) + "hostname         : " + str(STATSD_CONFIG.get(section,'hostname')) + "\n"
			result = result + " "*(20) +"port             : " + str(STATSD_CONFIG.get(section,'port')) + "\n"
			result = result + " "*(20) +"flush interval   : " + str(STATSD_CONFIG.get(section,'flush_interval')) + "\n"
			result = result + " "*(20) +"push interval    : " + str(STATSD_CONFIG.get(section,'push_interval')) + "\n"
			result = result + "\n"
	except Exception as e:
		result = result + "Something went wrong occoured while analysing Statsd Monitoring Configuration\nFile   :{}\nError  :  {}\n".format(STATSD_CONF_FILE,e)
	return result

def checkPrometheusStatus():
	result = ""
	try:
		if str(PROMETHEUS_CONFIG.get('PROMETHEUS','enabled')) == "true" or str(PROMETHEUS_CONFIG.get('PROMETHEUS','enabled')) == "1":
			result = "enabled"
		elif str(PROMETHEUS_CONFIG.get('PROMETHEUS','enabled')) == "false" or str(PROMETHEUS_CONFIG.get('PROMETHEUS','enabled')) == "0":
			result = "disabled"
	except Exception as e:
		result = "Something went wrong while analysing Prometheus Status\nFile   :{}\nError  :  {}\n".format(PROMETHEUS_CONF_FILE,e)
	return result

def checkStatsdStatus():
	result = ""
	try:
		if str(STATSD_CONFIG.get('STATSD','enabled')) == "true" or str(STATSD_CONFIG.get('STATSD','enabled')) == "1":
			result = "enabled"
		elif str(STATSD_CONFIG.get('STATSD','enabled')) == "false" or str(STATSD_CONFIG.get('STATSD','enabled')) == "0":
			result = "disabled"
	except Exception as e:
		result = "Something went wrong while analysing Statsd Status\nFile   :{}\nError  :  {}\n".format(STATSD_CONF_FILE,e)
	return result

def checkPrometheusAddInput(param):
	result = "invalid"
	try:
		value = json.loads(param)
		for instance in value:
			if all(each in instance for each in ['prometheus_url', 'instance_name', 'include_pattern']):
				if not PROMETHEUS_CONFIG.has_section(instance['instance_name']):
					result = "valid"
				else:
					result = "Instance Name already exists"
	except Exception as e:
		result = "Something went wrong while Checking Add Prometheus Configuration Input\nError  :  {}\n".format(e)
	return result

def checkPrometheusRemoveInput(param):
	result = "invalid"
	try:
		value = json.loads(param)
		for instance in value:
			if 'instance_name' in instance:
				if PROMETHEUS_CONFIG.has_section(instance['instance_name']):
					result = "valid"
				else:
					result = "Instance Name does not exists"
	except Exception as e:
		result = "Something went wrong while Checking Remove Prometheus Configuration Input\nError  :  {}\n".format(e)
	return result

def checkPrometheusScrapeInterval(param):
	result = "invalid"
	try:
		if ":" in param:
			instance = param.split(":")[0]
			value = param.split(":")[1]
		else:
			instance = "PROMETHEUS"
			value = param
		if PROMETHEUS_CONFIG.has_section(instance):
			if PROMETHEUS_CONFIG.has_option(instance, "scrape_interval"):
				scrap_interval = PROMETHEUS_CONFIG.get(instance,'scrape_interval')
				if str(scrap_interval) != str(value):
					result = "valid"
				else:
					result = "Scrape Interval already :: {}\n".format(scrap_interval)
			else:
				result = "valid"
		else:
			result = "Prometheus does not have an Instance :: {}\n".format(instance)
	except Exception as e:
		result = "Something went wrong while Checking Remove Prometheus Configuration Input\nError  :  {}\n".format(e)
	return result

def checkPrometheusUpdateCongig(param):
	result = "invalid"
	try:
		output = checkPrometheusAddInput(param)
		if "Instance Name already exists" == output:
			value = json.loads(param)
			for instance in value:
				if all(each in instance for each in ['prometheus_url', 'instance_name', 'include_pattern']):
					if instance['prometheus_url'] == PROMETHEUS_CONFIG.get(instance['instance_name'], 'prometheus_url') and instance['include_pattern'] == PROMETHEUS_CONFIG.get(instance['instance_name'], 'include_pattern'):
						result = "alreadysame"
					else:
						result = "valid"
		elif "valid" == output:
			result = "notexist"
		else:
			result = output
	except Exception as e:
		result = "Something went wrong while Checking Update Prometheus Configuration Input\nError  :  {}\n".format(e)
	return result

def checkStatsdEditInput(param):
	result = "invalid"
	try:
		value = json.loads(param)
		for instance in value:
			if all(each in instance for each in ['hostname', 'port']):
					result = "valid"
	except Exception as e:
		result = "Something went wrong while Checking Edit Statsd Configuration Input\nError  :  {}\n".format(e)
	return result

def loadDataFromFile(str_fileName):
	bool_returnStatus = True
	file_obj = None
	dic_dataToReturn = None
	try:
		file_obj = open(str_fileName,'r')
		dic_dataToReturn = json.load(file_obj,object_pairs_hook=collections.OrderedDict)
	except Exception as e:
		print(e)
		bool_returnStatus = False
	finally:
		if not file_obj == None:
			file_obj.close()
	return bool_returnStatus, dic_dataToReturn
	
def check_plugin():
	try:
		result = "\n                       Plugins\n                  ----------------\n\n"
		if os.path.exists(PLUGIN_CONF_FILE):
			bool_FileLoaded, plugin_dict = loadDataFromFile(PLUGIN_CONF_FILE)
			if plugin_dict:
				result += " Plugin Name      | Instance Name     |  About\n-----------------------------------------------------------\n"
				for key,value in plugin_dict.items():
					if 'instance_name' in value and value['instance_name']:
						instance = value['instance_name']
					else:
						instance = "Nil"
					if 'plugin_name' in value and value['plugin_name']:
						plugin_name = value['plugin_name']
					else:
						plugin_name = key
					if value['status'] == 0:
						status = "ACTIVE"
					elif value['status'] == 2:
						status = "IN-ACTIVE"
					elif value['status'] == 3:
						status = "DELETED"
					result += "[" + plugin_name + "]" + " "*(18-len(str(plugin_name))) + "[" + instance + "]" + " "*(18-len(str(instance))) + "status     :  "+ status + "\n"
					if 'version' in value and value['version']:
						result += " "*40 + "version    :  " + value['version'] + "\n"
					if 'error_msg' in value and value['error_msg']:
						result += " "*40 + "error_msg  :  " + value['error_msg'] + "\n"
					result += "\n"
			else:
				result = result + "Something went wrong occoured while Reading Plugin Monitoring Configuration\nFile   :{}\nError  :  {}\n".format(PLUGIN_CONF_FILE,e)
		else:
			domain_name = MONAGENT_CONFIG.get('SERVER_INFO','server_name')
			domain = domain_name.split('.')[2]
			plugin_url = "No Plugin is installed in the agent, Install plugins directly from 50+ Ready to use Plugin Integerations\nhttps://www.site24x7." + str(domain) + "/app/client?a=f#/admin/inventory/monitors-configure/PLUGIN/home\n" 
			result = result + plugin_url
	except Exception as e:
		result = result + "Something went wrong occoured while analysing Plugin Monitoring Configuration\nFile   :{}\nError  :  {}\n".format(PLUGIN_CONF_FILE,e)
	return result


def upload_logs(ticket_id, email_id):
	response = None
	folder_path = MONAGENT_DIR + '/logs'
	install_log_path = MONAGENT_DIR.rstrip('monagent') + 'site24x7install.log'
	log_zip_path = MONAGENT_DIR + '/temp/agent_logs.zip'
	url = 'https://bonitas.zohocorp.com/v1/upload_file/'

	if not os.path.exists(log_zip_path):
		with zipfile.ZipFile(log_zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
			for root, dirs, files in os.walk(folder_path):
				for file in files:
					file_path = os.path.join(root, file)
					relative_path = os.path.relpath(file_path, folder_path)
					zipf.write(file_path, relative_path)
			zipf.write(install_log_path)

	files = {'uploadfile': open(log_zip_path, 'rb')}

	dict_to_send = {
		'fromaddress': email_id,
		'toaddress': 'support@site24x7.com',
		'ticketid': ticket_id,
		'subject': 'Monagent_logs',
		'usermessage': 'Agent manager triggered logs upload'
	}

	try:
		response = requests.post(url, files=files, data=dict_to_send)
		if response:
			resp_dict = json.loads(response.content)
			if resp_dict.get('status') == 'SUCCESS':
				print("Agent logs archive posted successfully to Site24x7 support")
			else:
				print("Unable to send agent logs to Site24x7 support | Reason: " + repr(resp_dict.get("message")))
	except: 
		print("Unable to send agent logs to Site24x7 support. Exception occured")
		print('You can manually upload the log archive located at '+log_zip_path+' to "https://bonitas.zohocorp.com/#to=support@site24x7.com" ')
		traceback.print_exc()

if __name__ == "__main__":
	if len(sys.argv) < 2:
		print("Not enough arguments passed")
		exit()
	else:
		output = ""
		req_type = sys.argv[1]

	if "prometheus" == req_type:
		output = output + check_prometheus()
	elif "statsd" == req_type:
		output = output + check_statsd()
	elif "plugin" == req_type:
		output = output + check_plugin()
	elif "checkPrometheus" == req_type:
		output = output + checkPrometheusStatus()
	elif "checkStatsd" == req_type:
		output = output + checkStatsdStatus()
	elif "checkPrometheusAddInput" == req_type:
		output = output + checkPrometheusAddInput(sys.argv[2])
	elif "checkPrometheusRemoveInput" == req_type:
		output = output + checkPrometheusRemoveInput(sys.argv[2])
	elif "checkStatsdEditInput" == req_type:
		output = output + checkStatsdEditInput(sys.argv[2])
	elif "checkPrometheusScrapeInterval" == req_type:
		output = output + checkPrometheusScrapeInterval(sys.argv[2])
	elif "checkPrometheusUpdateCongig" == req_type:
		output = output + checkPrometheusUpdateCongig(sys.argv[2])
	elif 'upload_logs' == req_type:
		upload_logs(sys.argv[2], sys.argv[3])
	else:
		print("Unknown option !!!")

	if output != "":
		print(output)