#$Id$
import os
import time
import logging
import zipfile
import traceback
import json
from com.manageengine.monagent.metrics import metrics_constants
from com.manageengine.monagent.metrics import metrics_logger

class ZipUploadInfo:
    def __init__(self):
        self.zipFileName = 'DEFAULT'
        self.uploadServlet = None

def read_data(path,filename):
    try:
        rdata=None
        config_file = os.path.join(path,filename)
        if os.path.exists(config_file):
            file=open(config_file,'r')
            rdata=file.read()
            file.close()
    except Exception as e:
        traceback.print_exc()
    return rdata

def delete_file(fname):
	try:
		if os.path.exists(fname):
			os.remove(fname)	
		else:
			metrics_logger.log("{} doesn't exists while deleting file \n".format(fname))		
	except Exception as e:	
		metrics_logger.errlog('Exception while while deleting file :: {} \n'.format(e))
						
def write_data(data,path,filename):
	try:
		file=open(os.path.join(path,filename),mode='w+')
		file.write(data)
		file.close()	
	except Exception as e:	
		metrics_logger.errlog('Exception while while writing data to file :: {} :: {} \n'.format(os.path.join(path,filename),e))	
								
def zip_file(zipFileName,str_fileToZipPath):	
	isbool_success=True
	zip_fileObj = None
	zip_upload_obj = ZipUploadInfo()
	try:
		zip_fileObj = zipfile.ZipFile(zipFileName, 'w')
		zip_fileObj.write(str_fileToZipPath,os.path.basename(str_fileToZipPath), zipfile.ZIP_DEFLATED)
		zip_upload_obj.zipFileName = zipFileName	
	except Exception as e:
		isbool_success = False
		metrics_logger.errlog("exception while writing zip file :: {}".format(e))
	finally:
		if not zip_fileObj == None:
			zip_fileObj.close()
	return isbool_success,zip_upload_obj

def zip_file_read(file_name):
    is_bool_success=False
    data=None
    try:
        if os.path.exists(file_name):
            file = open(file_name,'rb')
            data = file.read()
            file.close()
            is_bool_success=True
    except Exception as e:
        metrics_logger.errlog("exception while reading zip file :: {}".format(e))
    return is_bool_success,data
