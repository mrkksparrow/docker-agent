#$Id$
import hashlib
import traceback
import logging,json
import os
import ssl
try:
    import configparser
except Exception as e:
    import ConfigParser as configparser

try:
    from Crypto.Cipher import AES
    from base64 import b64encode, b64decode
except Exception as e:
    pass

IV = '1ab2cd345ef..@@1' #16 characters

INTERRUPT = '\u0001'
PAD = '\u0000'

from com.manageengine.monagent.metrics import metrics_constants
from com.manageengine.monagent.metrics import metrics_config_parser
from com.manageengine.monagent.metrics import file_handler as file_obj

from com.manageengine.monagent.metrics import buffer,metrics_logger

upload_buffer = buffer.get_buffer(metrics_constants.FILES_TO_UPLOAD_BUFFER, metrics_constants.MAX_SIZE_UPLOAD_BUFFER)

STATSD_CONFIG = metrics_config_parser.get_config_data(os.path.join(metrics_constants.STATSD_CONF_FILE))
PROMETHEUS_CONFIG = metrics_config_parser.get_config_data(os.path.join(metrics_constants.PROMETHEUS_CONF_FILE))

def get_hash(strArgs):
    try:
        return hashlib.md5(strArgs.encode()).hexdigest()
    except Exception as e:
        metrics_logger.errlog('Exception while getting hash : {}'.format(e))
        
def check_metric_deleted(mtype,unique_key,metric_key_data):
    is_metric_deleted = False
    try:
        real_metric_type = metrics_constants.METRICS_TYPE_NAMING_MAPPER.get(mtype,mtype)
        if real_metric_type in metric_key_data:
            if unique_key in metric_key_data[real_metric_type]:
                if 'del' in metric_key_data[real_metric_type][unique_key]:
                    is_metric_deleted = True
    except Exception as e:
        metrics_logger.errlog('Exception while checking metric deleted : {}'.format(e))
    return is_metric_deleted

def is_app_enabled(mtype,config):
    is_valid=False
    try:
        if config.has_option(mtype.upper(), 'enabled') and (str(config.get(mtype.upper(), 'enabled'))=='true' or str(config.get(mtype.upper(), 'enabled'))=='1'):
            is_valid=True    
    except Exception as e:
        metrics_logger.errlog("Exception in valid_start %s",traceback.print_exc())
    finally:
        return is_valid

def persist_conf_data(conf_file, write_config):
    try:
        with open(conf_file,'w+') as config:
        	write_config.write(config)
    except Exception as e:
         metrics_logger.errlog("Exception in persist_conf_data :: {} : {}".format(conf_file,traceback.print_exc()))

def check_metric_count(name,value,metric_type,metric_key_data,metrics_limit):
    metric_count_validator=False    
    try:
        metric_count = 0
        for key , value in metric_key_data.items():
            metric_count += len(value)
        if metric_count >= metrics_limit:
            if metric_type in metric_key_data and name not in metric_key_data[metric_type]:
                metrics_logger.log('Metric count exceeds license limit')
                metric_count_validator=True
    except Exception as e:
        metrics_logger.errlog('Exception in validate_keys %s \n',traceback.print_exc())
    finally:
        return metric_count_validator
    
def get_unique_key(metric_tags,metric_type,name,value):
    try:
        unique_key = None 
        u_name = None
        if metric_tags:
            metric_tags = dict(sorted(metric_tags.items()))
            if metric_type == 's':
                u_name = value + str(metric_tags)
            else:
                u_name = name + str(metric_tags)
        else:
            u_name = name
        unique_key = get_hash(u_name)
    except Exception as e:
        traceback.print_exc()
    return unique_key

def validate_metric(unique_key,value,metric_type,metric_key_data,metrics_limit):
    try:
        is_metric_within_count=check_metric_count(unique_key,value,metric_type,metric_key_data,metrics_limit)
        is_metric_deleted = check_metric_deleted(metric_type,unique_key,metric_key_data)
    except Exception as e:
        traceback.print_exc()
    return is_metric_within_count,is_metric_deleted


def get_metrics_config(gauge_reset,keys_path,keys_file):
    import os
    isbool_keys=False
    temp_storage={}
    try:
        key_data=file_obj.read_data(keys_path,keys_file)
        if  not key_data:
            metrics_logger.log('No keys deducted\n')
        else:
            isbool_keys=True
            temp_storage=json.loads(key_data)
            if 'gauge' in temp_storage:
                if gauge_reset =='True':
                    temp_storage.pop("gauge",None)
                    temp_data=json.dumps(temp_storage)
                    fileobj.write_data(temp_data,keys_path,keys_file)    
    except Exception as e:
        metrics_logger.errlog("Exception in initialize_keys %s",traceback.print_exc())
    finally:
        return isbool_keys,temp_storage

def StripPadding(data, interrupt, pad):
    return str(data,'UTF-8').rstrip(pad).rstrip(interrupt)

def DecryptWithAES(decrypt_cipher, encrypted_data):
    decoded_encrypted_data = b64decode(encrypted_data)
    decrypted_data = decrypt_cipher.decrypt(decoded_encrypted_data)
    return StripPadding(decrypted_data, INTERRUPT, PAD)

def decrypt(encrypted_customer_id,salt):
    cipher_for_decryption = AES.new(salt.encode("utf8"), AES.MODE_CBC, IV.encode("utf8"))
    return DecryptWithAES(cipher_for_decryption, bytes(encrypted_customer_id,'UTF-8'))
    
def get_customer_id(encrypted_customer_id):
    customer_id = None
    try:
        install_time = file_obj.read_data(metrics_constants.AGENT_TEMP_DIR,metrics_constants.INSTALL_TIME_FILE)
        salt = install_time + "sagent"
        customer_id = decrypt(encrypted_customer_id,salt)
    except Exception as e:
        traceback.print_exc()
    return customer_id

def remove_dc_zips():
    try:
        for the_file in os.listdir(metrics_constants.METRICS_DATA_ZIP_DIRECTORY):
            file_path = os.path.join(metrics_constants.METRICS_DATA_ZIP_DIRECTORY, the_file)
            try:
                if os.path.isfile(file_path):
                    metrics_logger.log("Deleting metrics DC zips :: {}".format(file_path))
                    os.remove(file_path)
            except Exception as e:
                metrics_logger.log("Exception while deleting metrics DC zips :: {}".format(e))
                traceback.print_exc()
    except Exception as e:
        traceback.print_exc()
        
def load_server_configurations(config_file):
    try:        
        config = metrics_config_parser.get_config_data(config_file)
        metrics_constants.SERVER_NAME = config.get('SERVER_INFO','server_name')
        metrics_constants.SERVER_PORT = config.get('SERVER_INFO','server_port')
        metrics_constants.SERVER_TIMEOUT = config.get('SERVER_INFO','server_timeout')
        metrics_constants.SERVER_PROTOCOL = config.get('SERVER_INFO','server_protocol')
        metrics_constants.SERVER_AGENT_KEY = config.get('AGENT_INFO','agent_key')
        if config.has_option('AGENT_INFO','customer_id'):
            metrics_constants.DEVICE_KEY=config.get('AGENT_INFO','customer_id')
        if config.has_option('AGENT_INFO','encrypted_customer_id'):
            metrics_constants.DEVICE_KEY = get_customer_id(config.get('AGENT_INFO','encrypted_customer_id'))
        if config.has_option('AGENT_INFO','ssl_verify'):
            metrics_constants.SSL_VERIFY = True if str(config.get('AGENT_INFO','ssl_verify')) == "true" else False
        metrics_constants.PROXY_SERVER = config.get('PROXY_INFO','proxy_server_name')
        metrics_constants.PROXY_SERVER_PORT = config.get('PROXY_INFO','proxy_server_port')
        metrics_constants.PROXY_USERNAME = config.get('PROXY_INFO','proxy_user_name')
        metrics_constants.PROXY_PASSWORD = config.get('PROXY_INFO','proxy_password')
        metrics_constants.PROXY_PROTOCOL = config.get('PROXY_INFO','proxy_server_protocol')
        if str(metrics_constants.PROXY_SERVER)!='0' :
                if str(metrics_constants.PROXY_PROTOCOL) =='0':
                    proxy_server_protocol=metrics_constants.HTTP_PROTOCOL            
                proxy_server=metrics_constants.PROXY_SERVER+":"+metrics_constants.PROXY_SERVER_PORT
                if str(metrics_constants.PROXY_USERNAME) !='0':
                    metrics_constants.PROXY_URL=proxy_server_protocol+'://'+metrics_constants.PROXY_USERNAME+':'+metrics_constants.PROXY_PASSWORD+'@'+proxy_server
                else:
                    metrics_constants.PROXY_URL=proxy_server_protocol+'://'+proxy_server
        metrics_logger.log("proxy url :: {}".format(metrics_constants.PROXY_URL))        
        #metrics_logger.log("device key :: {}".format(metrics_constants.DEVICE_KEY))
    except Exception as e:
        traceback.print_exc()

def init_ssl_context(bypass_ssl=False):
    try:
        if not metrics_constants.SSL_VERIFY or bypass_ssl:
            metrics_logger.log('*** intializing local ssl context ***')
            metrics_constants.LOCAL_SSL_CONTEXT = ssl.create_default_context()
            metrics_constants.LOCAL_SSL_CONTEXT.check_hostname = False
            metrics_constants.LOCAL_SSL_CONTEXT.verify_mode = ssl.CERT_NONE
    except Exception as e:
        metrics_logger.log('*** EXCEPTION *** => {}'.format(traceback.format_exc()))

def create_upload_directories():
    try:
        if not os.path.exists(metrics_constants.METRICS_DATA_TEXT_DIRECTORY):
            os.mkdir(metrics_constants.METRICS_DATA_TEXT_DIRECTORY)
        if not os.path.exists(metrics_constants.METRICS_DATA_ZIP_DIRECTORY):
            os.mkdir(metrics_constants.METRICS_DATA_ZIP_DIRECTORY)
    except Exception as e:
        traceback.print_exc()

def add_to_buffer(zipobj):
    upload_buffer.add(zipobj)

