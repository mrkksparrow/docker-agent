#$Id$
import sys
import socket
import time
import traceback
import logging
import os
import json
import threading
from threading import Thread 
import requests

from com.manageengine.monagent.metrics import buffer
from prometheus_client.parser import text_string_to_metric_families
import math
import re

from com.manageengine.monagent.metrics import communication_handler,file_handler
from com.manageengine.monagent.metrics import metrics_constants,metrics_util,metrics_logger
from com.manageengine.monagent.metrics import file_handler as file_obj

class PrometheusServer(threading.Thread):
    def __init__(self,instance,config): 
        try:
            threading.Thread.__init__(self)
            self.name = instance
            #self.target_hostname=config.get(instance,'target_hostname')
            #self.target_port=config.get(instance,'target_port')
            #self.target_metrics_api=config.get(instance,'target_metrics_api')
            #self.target_protocol=config.get(instance,'target_protocol')
            if config.has_option(instance, 'timeout'):
                self.timeout = config.get(instance,'timeout')
            else:
                self.timeout = config.get('PROMETHEUS', 'timeout')
            if config.has_option(instance, 'scrape_interval'):
                self.scrape_interval = config.get(instance,'scrape_interval')
            else:
                self.scrape_interval = config.get('PROMETHEUS', 'scrape_interval')
            if not config.has_option(instance, 'status'):
                config.set(instance, 'status', '0')
                metrics_util.persist_conf_data(metrics_constants.PROMETHEUS_CONF_FILE, config)
            self.include_pattern = config.get(instance,'include_pattern')
            self.url=config.get(instance,'prometheus_url')
            self.data_path=metrics_constants.METRICS_DATA_TEXT_DIRECTORY
            self.zip_path=metrics_constants.METRICS_DATA_ZIP_DIRECTORY
            self.key_data = {}
            if os.path.exists(os.path.join(metrics_constants.PROMETHEUS_WORKING_DIR,instance+"_metrics.json")):
                file_read_status,self.key_data = metrics_util.get_metrics_config(False,metrics_constants.PROMETHEUS_WORKING_DIR,instance+"_metrics.json")
            if not os.path.exists(metrics_constants.PROMETHEUS_WORKING_DIR):
                os.mkdir(metrics_constants.PROMETHEUS_WORKING_DIR)
            self.metrics_limit=int(config.get('PROMETHEUS','metrics_limit'))
            self.push_interval=int(config.get('PROMETHEUS','push_interval'))
            self.__kill = False
            self.ZIP_METRICS_LIMIT = int(config.get('PROMETHEUS','zip_metrics_limit'))            
            metrics_logger.log(('PROMETHEUS CONFIG :: SCRAPE INTERVAL : {}  METRICS LIMIT : {} ZIP_METRICS_LIMIT : {}'.format(self.scrape_interval , self.metrics_limit,self.ZIP_METRICS_LIMIT)))
        except Exception as e:
            metrics_logger.errlog('Exception in PrometheusServer init method ::{} \n'.format(e))
                        
    def stop(self):
        metrics_logger.log('Prometheus monitoring marked for deletion : shutting down :: {}'.format(self.name))
        self.__kill=True
    
    def delete_metric(self,del_metrics):
        try:
            metrics_logger.log('delete metric ::  {}'.format(json.dumps(del_metrics)))
            for m_type , m_list in del_metrics.items():
                m_type = m_type.upper()
                for m_dict in m_list:
                    u_name = m_dict['name']
                    m_dict['dimensions'].pop("instance")
                    if 'dimensions' in m_dict and m_dict['dimensions']:
                        dime = m_dict['dimensions']
                        dime = dict(sorted(dime.items()))
                        u_name = u_name + str(dime)
                    unique_key = metrics_util.get_hash(u_name)
                    if m_type in self.key_data:
                        if unique_key in self.key_data[m_type]:
                            self.key_data[m_type][unique_key]['del']=1
                            metrics_logger.log('Successfully deleted metric :: {}'.format(self.key_data[m_type][unique_key]))
            #metrics_logger.log('Post Delete metrics action :: {}'.format(self.key_data))
            temp_data=json.dumps(self.key_data)
            file_obj.write_data(temp_data,metrics_constants.PROMETHEUS_KEYS_PATH,self.name+"_"+""+metrics_constants.PROMETHEUS_KEY_FILE)
        except Exception as e:
            metrics_logger.errlog("Exception in prometheus delete_metric :: {}".format(e))
            traceback.print_exc()

    def metric_upload_check(self,dimensions,value,metric_type,metric_name,single_metric_json,metrics_list,metrics_tuple):
        continue_process = False
        try:
            unique_key = metrics_util.get_unique_key(dimensions,metric_type,metric_name,None)
            metric_count_validator,is_metric_deleted = metrics_util.validate_metric(unique_key,value,metric_type,self.key_data,self.metrics_limit)
            if metric_count_validator or is_metric_deleted:
                continue_process = True
                return continue_process, metrics_list, metrics_tuple
            metrics_list.append(single_metric_json)
            if metric_type not in self.key_data:
                self.key_data[metric_type] = {}
            if unique_key not in self.key_data[metric_type]:
                self.key_data[metric_type][unique_key]=dict(single_metric_json)   
            if len(metrics_list) > int(self.ZIP_METRICS_LIMIT - 1):
                metrics_tuple.append(metrics_list)
                metrics_list = []
                continue_process = True
        except Exception as e:
            metrics_logger.errlog("Exception in prometheus metric_upload_check :: {}".format(e))
            traceback.print_exc()
        return continue_process, metrics_list, metrics_tuple
        
    def prometheus_data_parsing(self,response):
        metrics_list=[]
        metrics_tuple = ([])
        is_pattern_matched = False
        if self.include_pattern == "*":
            pattern = ""
        else:
            pattern = self.include_pattern
        metric = re.compile(pattern, flags=re.IGNORECASE)

        try:
            metrics_logger.log('=========== Parsing prometheus data received from url ===========\n')
            for family in text_string_to_metric_families((response.content).decode("utf-8")):        
                sample_obj = family.samples
                metric_type = family.type.upper()
                metric_name = family.name
                # if metric.search(metric_name):
                # is_pattern_matched = True
                single_metric_json = {}
                dimension_matching = {}
                list_key = []
                for samples in sample_obj:
                    sample_name = samples.name

                    if metric.search(sample_name):
                        is_pattern_matched = True

                        if metric_type == 'SUMMARY' or metric_type == 'HISTOGRAM':
                            if sample_name.endswith('_count'):
                                if samples.labels:
                                    if str(samples.labels) in dimension_matching:
                                        dimension_matching[str(samples.labels)].update({"count": samples.value})
                                    else:
                                        dimension_matching[str(samples.labels)] = {"count": samples.value, "dimensions": samples.labels}
                                else:
                                    single_metric_json['count']=samples.value

                            elif sample_name.endswith('_sum'):
                                if samples.labels:
                                    if str(samples.labels) in dimension_matching:
                                        dimension_matching[str(samples.labels)].update({"sum": samples.value})
                                    else:
                                        dimension_matching[str(samples.labels)] = {"sum": samples.value, "dimensions": samples.labels}
                                else:
                                    single_metric_json['sum']=samples.value

                            elif samples.labels and 'quantile' in samples.labels:
                                quantile_data = {}
                                quantile_data['quantile'] = samples.labels['quantile']
                                quantile_data['val'] = samples.value
                                list_key.append(quantile_data)
                                if len(samples.labels)>1:
                                    samples.labels.pop('quantile')
                                    if str(samples.labels) in dimension_matching:
                                        dimension_matching[str(samples.labels)].update({"summary": list_key})
                                    else:
                                        dimension_matching[str(samples.labels)] = {"summary": list_key, "dimensions": samples.labels}
                                else:
                                    single_metric_json['summary']=list_key

                            elif sample_name.endswith('_bucket'):
                                quantile_data = {}
                                quantile_data['le'] = samples.labels['le']
                                quantile_data['val'] = samples.value
                                list_key.append(quantile_data)
                                if len(samples.labels)>1:
                                    samples.labels.pop('le')
                                    if str(samples.labels) in dimension_matching:
                                        dimension_matching[str(samples.labels)].update({"histogram": list_key})
                                    else:
                                        dimension_matching[str(samples.labels)] = {"histogram": list_key, "dimensions": samples.labels}
                                else:
                                    single_metric_json['histogram']=list_key

                        elif metric_type == 'COUNTER' or metric_type == 'GAUGE':
                            single_metric_json = {}
                            single_metric_json['name'] = sample_name
                            single_metric_json['mtype'] = metric_type
                            value = samples.value
                            if math.isnan(value):
                                continue
                            single_metric_json['val'] = value
                            dimensions = samples.labels
                            if dimensions:
                                single_metric_json['dimensions'] = dimensions
                            continue_process, metrics_list, metrics_tuple = self.metric_upload_check(dimensions,value,metric_type,metric_name,single_metric_json,metrics_list,metrics_tuple)
                            single_metric_json = {}
                            if continue_process:
                                continue

                if single_metric_json:
                    dimensions = {}
                    single_metric_json['name'] = metric_name
                    single_metric_json['mtype'] = metric_type
                    continue_process, metrics_list, metrics_tuple = self.metric_upload_check(dimensions,single_metric_json['sum'],metric_type,metric_name,single_metric_json,metrics_list,metrics_tuple)
                    if continue_process:
                        continue
                elif dimension_matching:
                    for each in dimension_matching:
                        single_metric_json = {}
                        single_metric_json['name'] = metric_name
                        single_metric_json['mtype'] = metric_type
                        single_metric_json['dimensions'] = dimension_matching[each]['dimensions']
                        single_metric_json['count'] = dimension_matching[each]['count']
                        single_metric_json['sum'] = dimension_matching[each]['sum']
                        if metric_type == 'SUMMARY':
                            single_metric_json['summary'] = dimension_matching[each]['summary']
                        elif metric_type == 'HISTOGRAM':
                            single_metric_json['histogram'] = dimension_matching[each]['histogram']
                        continue_process, metrics_list, metrics_tuple = self.metric_upload_check(dimension_matching[each]['dimensions'],dimension_matching[each]['sum'],metric_type,metric_name,single_metric_json,metrics_list,metrics_tuple)
                        if continue_process:
                            continue
                                
            if metrics_list:
                metrics_tuple.append(metrics_list)

            if not is_pattern_matched:
                metrics_logger.log("Pattern did not match with any metrics :: {} : {} ".format(self.include_pattern,metrics_tuple))

        except Exception as e:
            metrics_logger.errlog('Exception in prometheus_data_parsing ::{} \n'.format(e))
            traceback.print_exc()
        return metrics_tuple    

    def run(self) :    
        metrics_logger.log('=========== Prometheus consolidator thread started ===========\n')
        while not self.__kill:    
            try:                
                try:
                    response= requests.get(self.url, verify=False)                                            
                    tuple_list=self.prometheus_data_parsing(response)
                    metrics_logger.debug('=========== Prometheus consolidator thread completed =========== {}'.format(tuple_list))
                except requests.exceptions.Timeout as e:
                    output_ditc = {}
                    output_ditc["status"] = "0"
                    output_ditc["msg"] = str(e)
                    tuple_list=[[output_ditc]]
                    metrics_logger.errlog('Prometheus URL error :: {} :: {}'.format(self.name,output_ditc))
                except requests.exceptions.HTTPError as e:
                    output_ditc = {}
                    output_ditc["status"] = "0"
                    output_ditc["msg"] = str(e)
                    tuple_list=[[output_ditc]]
                    metrics_logger.errlog('Prometheus URL error :: {} :: {}'.format(self.name,output_ditc))
                except Exception as e:
                    output_ditc = {}
                    output_ditc["status"] = "0"
                    output_ditc["msg"] = str(e)
                    tuple_list=[[output_ditc]]
                    metrics_logger.errlog('Prometheus URL error :: {} :: {}'.format(self.name,output_ditc))
                if tuple_list:
                    for var in enumerate(tuple_list):
                        data = json.dumps(var[1])
                        ct = str(var[0])+"_"+str(int(time.time())*1000)
                        data_filename=metrics_constants.METRICS_PROMETHEUS+"_"+str(self.name)+"_"+str(ct)+".txt"
                        file_save_satus = file_obj.write_data(str(data),self.data_path,data_filename)
                        zip_filename=metrics_constants.METRICS_PROMETHEUS+"_"+str(self.name)+"_"+str(ct)+'.zip'
                        zip_file_save_status,zipobj=file_obj.zip_file(os.path.join(self.zip_path,zip_filename),os.path.join(self.data_path,data_filename))
                        if zip_file_save_status:
                            metrics_util.add_to_buffer(zipobj)
                        file_obj.delete_file(os.path.join(self.data_path,data_filename))
                        metrics_logger.log('Data written in file {} and zipped as {}'.format(data_filename,zip_filename))
                else:
                    metrics_logger.log('No Data collected from parser :: Pattern - {} : Result Data - {}'.format(self.include_pattern,tuple_list))
                if self.key_data:
                    file_obj.write_data(json.dumps(self.key_data),metrics_constants.PROMETHEUS_KEYS_PATH,self.name+"_"+""+metrics_constants.PROMETHEUS_KEY_FILE)
                time.sleep(int(self.scrape_interval))
            except Exception as e:
                metrics_logger.errlog('Exception in prometheus_consolidator thread :: {} \n'.format(e))
            
