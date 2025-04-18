'''
Created on 21-July-2017

@author: giri
'''

from contextlib import contextmanager
import urllib
from six.moves.urllib.parse import urlencode
import collections
from com.manageengine.monagent.framework.suite.helper import handle_request

extract_key = lambda header_name, header_value : True if header_name == "hadoopkey" else False

@contextmanager
def handle_s247server_request(req_params, monitor_obj):
    resp = collections.namedtuple("Response", "bool_flag status data error_msg")
    resp = resp(bool_flag=False, status=200, data={}, error_msg='')
    dict_data = {}
    dict_data["request_type"] = "get"
    dict_data["params"] = urlencode(req_params)
    dict_data["headers"] = [("Content-Type", 'application/json'), ("Accept", "text/plain"), ("Connection", 'close')]
    dict_data["proxies"] = {} 
    dict_data["url"] = "http://vinoth-2277.csez.zohocorpin.com:8081/plus/ApplicationDiscoveryServlet?{}".format(dict_data["params"])
    with handle_request(dict_data) as resp_data:
        if resp_data.status_code == 200:
            for header in resp_data.headers:
                if extract_key(*header) is True:
                    monitor_obj.mid = header[-1]
    yield resp
    
def handle_data(worker_dict, prefix_str, temp_xml, monitor_obj):
    try:
        if worker_dict['output_xml']:
            op_xml = worker_dict['output_xml']
            if prefix_str(worker_dict['output_xml']) == "":
                del(temp_xml["@cid"])
                with handle_s247server_request(temp_xml, monitor_obj) as resp:
                     if resp.status == 200:
                         return True  
            else:
                if op_xml in monitor_obj.output_xml:
                    if not type(monitor_obj.output_xml[op_xml]) is list:
                        monitor_obj.output_xml[op_xml] = [monitor_obj.output_xml[op_xml], temp_xml]
                else:
                    monitor_obj.output_xml[op_xml] = temp_xml
    except Exception as e:
        import traceback
        traceback.print_exc()