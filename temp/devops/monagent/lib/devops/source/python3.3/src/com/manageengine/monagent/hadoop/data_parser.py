import traceback,json
from com.manageengine.monagent.logger import AgentLogger
from com.manageengine.monagent import AgentConstants,AppConstants
from com.manageengine.monagent.util import AgentUtil,AppUtil

from xml.etree.ElementTree import tostring

def collect_data(metric_json):
    try:
        result_data = {}
        result_data[metric_json['config']['mid']]=[]
        app_name = metric_json['app_name']
        config_obj = AgentConstants.APPS_CONFIG_DATA
        metrics_api_dict = metric_json[app_name]['metrics_api']
        metrics_dict = {}
        error_dict = {}
        for metric_api , metric_items in metrics_api_dict.items():
            url = metric_json['config']['protocol']+"://"+metric_json['config']['host']+":"+metric_json['config']['port']+metric_items['api']
            dict_data = AppUtil.get_default_params()
            dict_data['url'] = url
            with AppUtil.handle_request(dict_data) as resp:
                success_flag, response_data, status_code, msg = resp.bool_flag, resp.data, resp.status_code, resp.msg
                AgentLogger.debug(AgentLogger.APPS,'response data -- {} -- {} -- {} -- {}'.format(success_flag,response_data,status_code,msg))
                if success_flag:
                    if response_data:
                        if 'yarn' not in app_name: 
                            metrics_dict[metric_items['output_tag']] = response_data['beans'][0]
                        else:
                            metrics_dict[metric_items['output_tag']] = response_data['clusterMetrics']
                            metrics_dict[metric_items['output_tag']].update({'host':metric_json['config']['host']})
                else:
                    error_dict = AppUtil.get_error_data(app_name.upper(),metric_json['config']['mid'])
                    AgentLogger.debug(AgentLogger.APPS,'error data -- {}'.format(json.dumps(error_dict)))
                    break
        final_list = []
        if not error_dict:
            data_dict = AppUtil.mergeDict(metrics_dict)
            AgentLogger.debug(AgentLogger.APPS,'data set -- {}'.format(json.dumps(data_dict)))
            perf_data_list = metric_json[app_name]['perf_data']
            if app_name == AppConstants.namenode_app:
                result_data['state'] = data_dict['State']
                AppConstants.nn_state = data_dict['State']
            if AppConstants.nn_state:
                result_data['state'] = AppConstants.nn_state
            for k , v in perf_data_list.items():
                temp_dict = {}
                inner_temp_dict = {}
                if 'iter' in v:
                    if AppConstants.namenode_app in AgentConstants.SKIP_STANDBY_NODES:
                        if result_data['state'] == 'standby':
                            AgentLogger.log(AgentLogger.APPS,'skip_standby_dc set to true hence skipping dc of data nodes')
                            break
                    multi_nodes = data_dict[v['iter']]
                    if not isinstance(multi_nodes, str):
                        multi_nodes = multi_nodes.encode('utf8')
                    multi_nodes = json.loads(multi_nodes)
                    for key , value in multi_nodes.items():
                        multi_node_data_dict = {}
                        error_dict = {}
                        if 'iter_api' in v:
                            inner_temp_dict = {}
                            temp_dict = {}
                            host_port = value['infoAddr']
                            if AppConstants.skip_dc_for_nodes:
                                if host_port.split(':')[0] in AppConstants.skip_dc_for_nodes:
                                    continue
                                if config_obj and AppConstants.datanode_app.upper() in config_obj:
                                        data_node_app_obj = config_obj[AppConstants.datanode_app.upper()]
                                        if host_port.split(':')[0] in data_node_app_obj:
                                            if int(data_node_app_obj[host_port.split(':')[0]]['status'])!=0:
                                                continue
                            response_dict = {}
                            apis_to_hit = v['iter_api']
                            for url in apis_to_hit:    
                                iter_url = metric_json['config']['protocol']+"://"+host_port+url
                                dict_data = AppUtil.get_default_params()
                                dict_data['url'] = iter_url
                                with AppUtil.handle_request(dict_data) as resp:
                                    success_flag, response_data, status_code, msg = resp.bool_flag, resp.data, resp.status_code, resp.msg
                                    if success_flag:
                                        response_data = response_data['beans'][0]
                                        response_dict[url] = response_data
                                    else:
                                        error_dict = AppUtil.get_error_data(AppConstants.datanode_app.upper(),host_port.split(':')[0])
                                        break
                            if not error_dict:
                                multi_node_data_dict = AppUtil.mergeDict(response_dict)
                                construct_dc_node(v['metrics'], inner_temp_dict, multi_node_data_dict, final_list,temp_dict,config_obj,AppConstants.datanode_app)
                            else:
                                construct_dc_error_node(error_dict,final_list,{},{},config_obj)
                        else:
                            multi_node_data_dict[v['pkey']] = host_port.split(':')[0]
                            construct_dc_node(v['metrics'], inner_temp_dict, multi_node_data_dict, final_list,temp_dict,config_obj,AppConstants.datanode_app)
                else:
                    construct_dc_node(v['metrics'], inner_temp_dict, data_dict, final_list,temp_dict,config_obj,k)
        else:
            construct_dc_error_node(error_dict,final_list,{},{},config_obj)
        for val in final_list:
            result = AgentConstants.XMLJSON_BF.etree(val)
            result_data[metric_json['config']['mid']].append(tostring(result[0]).decode('utf-8'))
            result_data['node'] = app_name 
    except Exception as e:
        traceback.print_exc()
    finally:
        return result_data
            
def construct_dc_node(v,inner_temp_dict,data_dict,final_list,temp_dict,app_config_obj,app_name):
    try:
        for k1 , v1 in v.items():
            if 'expr_for_ct' in v1:
                v1['value'] = AgentUtil.getTimeInMillis()
            if 'eval' in v1:
                v1['value'] = AgentUtil.get_value_from_expression(v1['eval'], data_dict)
            if 'delimeter' in v1:
                un_delimited = data_dict.get(v1['value'])
                if un_delimited:
                    v1['value'] = un_delimited.split(v1['delimeter'])[v1['index']]
            if 'config_obj' in v1:
                v1['value'] = -1
                look_up_key = v1['config_obj']
                if app_name.upper() in app_config_obj:
                    app_config = app_config_obj[app_name.upper()]
                    if look_up_key in data_dict:
                        p_key = data_dict[look_up_key]
                        if p_key in app_config:
                            if int(app_config[p_key]['status']) != 0:
                                AgentLogger.log(AgentLogger.APPS,' skipping dc as app status is not active :: {}'.format(app_config[p_key])+'\n')
                                return
                            if p_key in AppConstants.skip_dc_for_nodes:
                                AgentLogger.log(AgentLogger.APPS,' skipping dc as app is in stop dc node list :: {}'.format(p_key)+'\n')
                                return
                            v1['value'] = app_config[p_key]['mid']
            inner_temp_dict['@'+k1] = data_dict.get(v1['value'], v1['value'])
        temp_dict['DC'] = inner_temp_dict
        final_list.append(temp_dict)
    except Exception as e:
        traceback.print_exc()
    
def construct_dc_error_node(error_dict ,final_list,temp_dict,inner_temp_dict,config_obj):
    for k1 , v1 in error_dict.items():
        inner_temp_dict['@'+k1] = error_dict[k1]
    temp_dict['DC'] = inner_temp_dict
    final_list.append(temp_dict)