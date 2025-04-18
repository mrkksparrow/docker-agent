#$Id$
import os
import time
import logging
import zipfile
import traceback
import json
import threading
import platform
import re

from com.manageengine.monagent.metrics import metrics_constants
from com.manageengine.monagent.metrics import buffer,metrics_logger
from com.manageengine.monagent.metrics import communication_handler as req_obj
from com.manageengine.monagent.metrics import file_handler as file_obj 
from com.manageengine.monagent.metrics.file_handler import ZipUploadInfo

LAST_UPLOADED_TIME = 0
UPLOAD_PAUSE_TIME = 0
UPLOAD_PAUSE_FLAG = False

def initialize():
    UPLOADER = Uploader()
    UPLOADER.start()

class Uploader(threading.Thread):            
    def __init__(self):
        threading.Thread.__init__(self)
        self.name = 'UploaderThread'
        self.add_files_to_upload_buffer()
    def run(self):
        try:
            while True:
                Uploader.upload()
                time.sleep(10)
        except Exception as e:
            traceback.print_exc()
    
    def add_files_to_upload_buffer(self):
        try:
            upload_buffer = buffer.get_buffer(metrics_constants.FILES_TO_UPLOAD_BUFFER, metrics_constants.MAX_SIZE_UPLOAD_BUFFER)
            for zipFileName in sorted(os.listdir(metrics_constants.METRICS_DATA_ZIP_DIRECTORY)):
                metrics_logger.debug('add files to upload buffer :: {}'.format(str(zipFileName)))
                zip_upload_obj = ZipUploadInfo()
                zip_upload_obj.zipFileName = os.path.join(metrics_constants.METRICS_DATA_ZIP_DIRECTORY,zipFileName)
                upload_buffer.add(zip_upload_obj)
        except Exception as e:
            traceback.print_exc()
        
    def upload():
        global LAST_UPLOADED_TIME, UPLOAD_PAUSE_TIME, UPLOAD_PAUSE_FLAG
        upload_buffer = buffer.get_buffer(metrics_constants.FILES_TO_UPLOAD_BUFFER, metrics_constants.MAX_SIZE_UPLOAD_BUFFER)
        try:
            while upload_buffer.size() > 0:
                metric_instance=None
                if UPLOAD_PAUSE_FLAG:
                    metrics_logger.log("Upload pause time set")
                    ct = time.time()
                    if ((ct - LAST_UPLOADED_TIME) > UPLOAD_PAUSE_TIME):
                        metrics_logger.log("Upload pause time requested by server completed. Hence switching to normal upload mode")
                        UPLOAD_PAUSE_FLAG = False
                        UPLOAD_PAUSE_TIME = 0
                    else:
                        metrics_logger.log("breaking")
                        break
                zipobj=upload_buffer.pop()
                metrics_logger.debug('upload started for :: {}'.format(str(zipobj.zipFileName)))
                request_params = {}
                request_params['agentkey'] = metrics_constants.SERVER_AGENT_KEY
                request_params['apikey'] = metrics_constants.DEVICE_KEY
                request_params['source'] = platform.node()
                #request_params['zips_in_buffer']=int(upload_buffer.size())
                fname = os.path.basename(zipobj.zipFileName)
                if fname.startswith(metrics_constants.METRICS_STATSD):
                    metric_instance = metrics_constants.METRICS_STATSD
                if metrics_constants.PROMETHEUS_INSTANCES:
                    for each in metrics_constants.PROMETHEUS_INSTANCES:
                        pattern = re.compile(str(each)+r'_\d+_\d+\.zip')
                        if pattern.search(fname):
                            request_params['unique_name'] = each
                            metric_instance = each
                            break
                data_read_status,data=file_obj.zip_file_read(zipobj.zipFileName)
                response=None
                if metric_instance in metrics_constants.DELETED_INSTANCE:
                    metrics_logger.log('Deleted Instance zip file found :: {} :: {}'.format(request_params['unique_name'],zipobj.zipFileName))
                    file_obj.delete_file(zipobj.zipFileName)
                else:
                    if data_read_status:
                        response=req_obj.upload_payload(request_params,zipobj.zipFileName,data)                                                                
                        if response:
                            file_obj.delete_file(zipobj.zipFileName)
                            req_obj.handle_response_headers(response)
                            metrics_logger.log('Successfully posted the zip file :: {} :: {}'.format(response.code,zipobj.zipFileName))
                        else:
                            metrics_logger.errlog('Unable to post the zip file :: {} :: {}'.format(response.code,zipobj.zipFileName))
                            upload_buffer.appendleft(zipobj)
                        LAST_UPLOADED_TIME = time.time()
                    else:
                        metrics_logger.warnlog('data read status :: {}'.format("no zip file found"))
                    time.sleep(3)
        except Exception as e:
            metrics_logger.errlog('Exception in Prometheus server :: {}\n'.format(e))
    
