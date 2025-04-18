#$Id$
import sys
import socket
import time
import traceback
import logging
import os
import json
import re
import threading
from threading import Thread 
   
from com.manageengine.monagent.metrics import counter,gauge,sets,timer
from com.manageengine.monagent.metrics import communication_handler,file_handler
from com.manageengine.monagent.metrics import metrics_constants,metrics_util,metrics_logger
from com.manageengine.monagent.metrics import file_handler as file_obj

'''
    Statsd Data format
    Event:1|c|@0.9|#key2:value2,key1:value1
    Metricname:value|type|@sample_rate|#tags 
'''

class StatsDServer(threading.Thread):
    def __init__(self,config): 
    	try:
            threading.Thread.__init__(self)
            self.name = 'StatsDThread'
            self.upload_buffer=[]
            self.conf=config
            self.host=config.get('STATSD','hostname')
            self.port=int(config.get('STATSD','port'))
            self.source = config.get('STATSD','source')
            self.counter_obj = {}
            self.gauge_obj = {}
            self.gauge_reset=config.get('STATSD','gauge_reset')
            self.sets_obj = {}
            self.timer_obj = {}		
            if not os.path.exists(metrics_constants.STATSD_WORKING_DIR):
                os.mkdir(metrics_constants.STATSD_WORKING_DIR)
            self.data_path=metrics_constants.METRICS_DATA_TEXT_DIRECTORY
            self.zip_path=metrics_constants.METRICS_DATA_ZIP_DIRECTORY
            self.metrics_limit=int(config.get('STATSD','metrics_limit'))
            self.key_data={}
            self.flush_interval=float(config.get('STATSD','flush_interval'))		
            self.push_interval=int(config.get('STATSD','push_interval'))
            self.__kill = False
            self.ZIP_METRICS_LIMIT = int(config.get('STATSD','zip_metrics_limit'))
            metrics_logger.log('STATSD CONFIG :: FLUSH INTERVAL : {} PUSH INTERVAL : {} GAUGE RESET : {} METRICS LIMIT : {} ZIP_METRICS_LIMIT : {}'.format(self.flush_interval,self.push_interval,self.gauge_reset , self.metrics_limit,self.ZIP_METRICS_LIMIT))
    	except Exception as e:
    		metrics_logger.log('Exception in StatsDServer init method ::{} \n'.format(e))
    
    def stop(self):
        metrics_logger.log('statsd marked for deletion shutting down')
        self.__kill=True



    def delete_metric(self,del_metrics):
        try:
            metrics_logger.log('delete metric ::  {}'.format(json.dumps(del_metrics)))
            for m_type , m_list in del_metrics.items():
                for m_dict in m_list:
                    u_name = m_dict['name']
                    if 'dimensions' in m_dict:
                        dime = m_dict['dimensions']
                        dime = dict(sorted(dime.items()))
                        u_name = u_name + str(dime)
                    unique_key = metrics_util.get_hash(u_name)
                    if m_type in self.key_data:
                        if unique_key in self.key_data[m_type]:
                            self.key_data[m_type][unique_key]['del']=1
                            if unique_key in self.gauge_obj:
                                self.gauge_obj.pop(unique_key)
            metrics_logger.log('Post Delete metrics action :: {}'.format(self.key_data))
            temp_data=json.dumps(self.key_data)
            file_obj.write_data(temp_data,metrics_constants.STATSD_KEYS_PATH,metrics_constants.STATSD_KEY_FILE)
        except Exception as e:
            metrics_logger.errlog("Exception in delete_metric")
            traceback.print_exc()
    
    def data_parser(self,raw_data):
        try:
            result_data=[]
            main_data=raw_data.splitlines()
            for single_data in main_data:
                single_json={}
                data=re.split("[|]",single_data)
                single_json["metric_name"],single_json["value"]=data.pop(0).split(':')
                single_json["metric_type"]=data.pop(0)
                single_json["sample_rate"]=1
                single_json["metric_tags"]={}
                for temp in data:
                    if '@' in temp:
                        single_json["sample_rate"]=temp.replace('@','')
                    elif '#' in temp:
                        tags=temp.replace('#','')
                        tag_list=tags.split(',')
                        for itr in tag_list:
                            if ':' in itr:
                                key,val=itr.split(':')
                            else:
                                key=itr
                                val=""
                            single_json["metric_tags"][key]=val.strip()
                    else:
                        metrics_logger.log('UnSupported Data Type : {}'.format(single_data))
                result_data.append(single_json)
        except Exception as e:
            metrics_logger.errlog("Exception in statsd data_parser :: RawData - {} ".format(raw_data))
            traceback.print_exc()
        finally:
            return result_data

    def data_consolidator(self,consolidate_data):
        try:
            metrics_list = []
            metrics_tuple = ([])
            for key,value in consolidate_data.items():
                if value:
                    for m_name , m_data in value.items():
                        if m_name:
                            metrics_dict = {}
                            metrics_dict['name']= m_data['n']
                            metrics_dict['val']=m_data['value']
                            if 'dimensions' in m_data:
                                metrics_dict['dimensions']=m_data['dimensions']
                            if 'mean' in m_data:
                                metrics_dict['mean']=m_data['mean']
                            if 'max' in m_data:
                                metrics_dict['max']=m_data['max']
                            if 'min' in m_data:
                                metrics_dict['min']=m_data['min']
                            if 'total' in m_data:
                                metrics_dict['total']=m_data['min']
                            metrics_dict['mtype']=key
                            metrics_list.append(metrics_dict)
                            if len(metrics_list) > int(self.ZIP_METRICS_LIMIT - 1):
                                metrics_tuple.append(metrics_list)
                                metrics_list = []
            if metrics_list:
                metrics_tuple.append(metrics_list)
        except Exception as e:
            metrics_logger.errlog('Exception while parsing metrics to json :: {}'.format(e))
        finally:
            return metrics_tuple
    
    def statsd_consolidator(self) :	
        metrics_logger.log('=========== StatsD consolidator thread started ===========\n')
        while not self.__kill:	
            try:
                time.sleep(self.flush_interval)
                consolidate_data={}
                consolidate_data['Counter']=self.counter_obj
                consolidate_data['Gauge']=self.gauge_obj
                consolidate_data['Set']=self.sets_obj
                consolidate_data['Timer']=self.timer_obj
                tuple_list=self.data_consolidator(consolidate_data)
                if  tuple_list:
                    for var in enumerate(tuple_list):
                        data = json.dumps(var[1])
                        metrics_logger.log('Received final data to  flush :: {}'.format(data))
                        ct = str(var[0])+"_"+str(int(time.time())*1000)
                        data_filename=metrics_constants.METRICS_STATSD+"_"+str(ct)+".txt"
                        file_save_satus = file_obj.write_data(str(data),self.data_path,data_filename)
                        zip_filename=metrics_constants.METRICS_STATSD+'_'+str(ct)+'.zip'
                        zip_file_save_status,zipobj=file_obj.zip_file(os.path.join(self.zip_path,zip_filename),os.path.join(self.data_path,data_filename))
                        if zip_file_save_status:
                            metrics_util.add_to_buffer(zipobj)
                        file_obj.delete_file(os.path.join(self.data_path,data_filename))
                        metrics_logger.log('Data written in file {} and zipped as {}'.format(data_filename,zip_filename))
                if self.key_data:
                    file_obj.write_data(json.dumps(self.key_data),metrics_constants.STATSD_KEYS_PATH,metrics_constants.STATSD_KEY_FILE)
                self.counter_obj = {}
                if self.gauge_reset =='true':
                    self.gauge_obj={}
                self.timer_obj = {}
                self.sets_obj = {}
            except Exception as e:
                metrics_logger.errlog('Exception in statsd_consolidator thread :: {}'.format(e))
                traceback.print_exc()
											
    def run(self):
        try:
            metrics_logger.log('=========== Udp Data (run) receiving Method started ===========\n')
            data_consolidator=Thread(target=self.statsd_consolidator)            
            serversock=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
            serversock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR,1)
            serversock.bind((self.host, self.port))
            data_consolidator.start()
            metric_methods = metrics_constants.METRICS_METHOD
            isbool_keys,self.key_data=metrics_util.get_metrics_config(self.gauge_reset,metrics_constants.STATSD_KEYS_PATH,metrics_constants.STATSD_KEY_FILE)
            if isbool_keys:
                if self.gauge_reset == 'true' and 'gauge' in self.key_data:
                    self.gauge_obj = self.key_data['gauge']
            while not self.__kill:
                try:
                    raw_data,addr=serversock.recvfrom(1024)
                    raw_data=(raw_data).decode('Utf-8')
                    metrics_logger.log('Recieved Raw data : {}'.format(raw_data))
                    result_data_dict = self.data_parser(raw_data)
                    for single_data in result_data_dict:
                        metrics_logger.debug('metric_name - {} :: metric_type - {} :: metric_tags - {} :: value - {} :: sample_rate - {}'.format(single_data["metric_name"],single_data["metric_type"],single_data["metric_tags"],single_data["value"],single_data["sample_rate"]))
                        unique_key = metrics_util.get_unique_key(single_data["metric_tags"],single_data["metric_type"],single_data["metric_name"],single_data["value"])
                        metric_count_validator,is_metric_deleted = metrics_util.validate_metric(unique_key,single_data["value"],single_data["metric_type"],self.key_data,self.metrics_limit)
                        if metric_count_validator or is_metric_deleted:
                            metrics_logger.log("skipping metric : {} : count_violated  : {} deleted_metric : {} \n".format(single_data["metric_name"],metric_count_validator,is_metric_deleted))
                            continue
                        if single_data["metric_type"] in metric_methods.keys():
                            script_path=metric_methods[single_data["metric_type"]].rsplit('.',1)[0]
                            script_path=sys.modules[script_path]
                            script_name=metric_methods[single_data["metric_type"]].rsplit('.',1)[1]
                            getattr(script_path,script_name )(unique_key,single_data["metric_name"],single_data["value"],single_data["sample_rate"],single_data["metric_tags"],self)
                        else:
                            metrics_logger.log("Not an applicable Data type :: RawData - {} :: SingleData - {}  \n".format(raw_data,single_data))
                except Exception as e:
                    metrics_logger.errlog('Exception in Udp Data (run) receiving : {}'.format(e))
        except Exception as e:
        	metrics_logger.errlog('Exception in  Data (run) receiving Method started : {} \n'.format(e))
        
