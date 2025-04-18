#$Id$
import ssl
import logging
import os
import json
import six.moves.urllib.request as urlconnection
from six.moves.urllib.error import URLError, HTTPError
from six.moves.urllib.parse import urlencode
import six.moves.urllib.error as error
import traceback
from com.manageengine.monagent.metrics import metrics_constants,metrics_logger,metrics_util,buffer
from com.manageengine.monagent.metrics import file_handler as file_obj
import com

def upload_payload(request_params,filename,data):
    response_from_server = None
    try:
        headers = {'Content-Type': 'application/zip'}
        uri = None
        if metrics_constants.METRICS_STATSD in filename:
            uri = metrics_constants.STATSD_URI
        elif metrics_constants.METRICS_PROMETHEUS in filename:
            uri = metrics_constants.PROMETHEUS_URI
        url=str(metrics_constants.SERVER_PROTOCOL+'://'+metrics_constants.SERVER_NAME+':'+metrics_constants.SERVER_PORT+uri+'{}'.format(urlencode(request_params)))
        metrics_logger.debug('data upload url :: {} :: {}'.format(url,request_params))
        request_obj=urlconnection.Request(url,data=data,headers=headers)

        if metrics_constants.PROXY_URL:
            if metrics_constants.LOCAL_SSL_CONTEXT is None:
                context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH,
                                                     cafile=metrics_constants.CA_CERT_FILE,
                                                     capath=None)
            else:
                context = metrics_constants.LOCAL_SSL_CONTEXT
            context.set_alpn_protocols(['http/1.1'])
            https_handler = urlconnection.HTTPSHandler(context=context)
            proxy = urlconnection.ProxyHandler({metrics_constants.HTTPS_PROTOCOL: metrics_constants.PROXY_URL})
            auth = urlconnection.HTTPBasicAuthHandler()
            opener=urlconnection.build_opener(proxy,auth,https_handler)
            urlconnection.install_opener(opener)
            response_from_server = urlconnection.urlopen(request_obj, timeout=float(metrics_constants.SERVER_TIMEOUT))
        elif metrics_constants.LOCAL_SSL_CONTEXT is not None:
            response_from_server = urlconnection.urlopen(request_obj, timeout=float(metrics_constants.SERVER_TIMEOUT), context=metrics_constants.LOCAL_SSL_CONTEXT)
        else:
            response_from_server = urlconnection.urlopen(request_obj, timeout=float(metrics_constants.SERVER_TIMEOUT), cafile=metrics_constants.CA_CERT_FILE, capath=None)

        if response_from_server.getcode() == 200:
            metrics_logger.debug('upload payload successful :: {} '.format(filename))
        else:
            metrics_logger.errlog('upload payload failed :: {}'.format(filename))
    except URLError as e:
        metrics_logger.errlog('SSL Exception while sending data :: {}'.format(traceback.format_exc()))
        if isinstance(e.reason, ssl.SSLCertVerificationError) or isinstance(e.reason, ssl.SSLError) or isinstance(e.reason, ssl.CertificateError) or isinstance(e.reason, ssl.SSLEOFError):
            metrics_util.init_ssl_context(True)
    except Exception as e:
        metrics_logger.errlog('Exception while sending data :: {}'.format(traceback.format_exc()))
    return response_from_server

def handle_response_headers(response_from_server):
    persist_statsd_conf_changes = False
    persist_prometheus_conf_changes = False
    try:
        response_headers = dict(response_from_server.headers)
        if response_headers and "SUSPEND_UPLOAD" in response_headers:
            com.manageengine.monagent.metrics.uploader.UPLOAD_PAUSE_FLAG = True
            com.manageengine.monagent.metrics.uploader.UPLOAD_PAUSE_TIME = int(response_headers['SUSPEND_UPLOAD_TIME'])
        if 'push_interval' in response_headers:
            push_interval=headers_dict.get('push_interval')
            metrics_util.STATSD_CONFIG.set('STATSD_INFO','push_interval',push_interval)
            #statsd_obj.push_interval=push_interval
            metrics_util.persist_conf_data(metrics_constants.STATSD_CONF_FILE, metrics_util.STATSD_CONFIG)
        if 'action' in response_headers:
            metrics_logger.log("Request Type - {} :: Response Headers - {} ".format(response_headers['action'],response_headers))
            #metrics_logger.log('response_headers :: {}'.format(response_headers))
            if response_headers['action']==metrics_constants.SUSPEND_MONITOR:
                app_type = response_headers.get("APP_NAME", None)
                instance_name = response_headers.get("instance_name", None)
                if app_type == metrics_constants.METRICS_STATSD.upper():
                    if str(metrics_util.STATSD_CONFIG.get('STATSD','enabled')) == 'true':
                        metrics_util.STATSD_CONFIG.set('STATSD','enabled','false')
                        metrics_util.persist_conf_data(metrics_constants.STATSD_CONF_FILE, metrics_util.STATSD_CONFIG)
                        metrics_constants.METRICS_THREAD_OBJ.stop(metrics_constants.METRICS_STATSD)
                    else:
                        metrics_logger.log("==== Statsd Monitor already Inctive ====")
                elif app_type == metrics_constants.METRICS_PROMETHEUS.upper():
                    if instance_name:
                        if str(metrics_util.PROMETHEUS_CONFIG.get(instance_name,'status')) != '5':
                            metrics_util.PROMETHEUS_CONFIG.set(instance_name,'status','5')
                            metrics_util.persist_conf_data(metrics_constants.PROMETHEUS_CONF_FILE, metrics_util.PROMETHEUS_CONFIG)
                            metrics_constants.METRICS_THREAD_OBJ.stop(instance_name)
                        else:
                            metrics_logger.log("==== Prometheus Monitor already Suspended ====")
                metrics_logger.log("Post Suspend Monitor result  :: {}".format(metrics_constants.METRICS_THREAD_OBJ.instances_obj))   

            elif response_headers['action']==metrics_constants.ACTIVATE_MONITOR:
                app_type = response_headers.get("APP_NAME", None)
                instance_name = response_headers.get("instance_name", None)
                if app_type == metrics_constants.METRICS_STATSD.upper():
                    if str(metrics_util.STATSD_CONFIG.get('STATSD','enabled')) == 'false':
                        metrics_util.STATSD_CONFIG.set('STATSD','enabled','true')
                        metrics_util.persist_conf_data(metrics_constants.STATSD_CONF_FILE, metrics_util.STATSD_CONFIG)
                        metrics_constants.METRICS_THREAD_OBJ.activate_statsd_monitor(metrics_util.STATSD_CONFIG)
                    else:
                        metrics_logger.log("==== Statsd Monitor already Active ====")
                elif app_type == metrics_constants.METRICS_PROMETHEUS.upper():
                    if instance_name:
                        if str(metrics_util.PROMETHEUS_CONFIG.get(instance_name,'status')) != '0':
                            metrics_util.PROMETHEUS_CONFIG.set(instance_name,'status','0')
                            metrics_util.persist_conf_data(metrics_constants.PROMETHEUS_CONF_FILE, metrics_util.PROMETHEUS_CONFIG)
                            metrics_constants.METRICS_THREAD_OBJ.activate_prometheus_monitor(instance_name, metrics_util.PROMETHEUS_CONFIG)
                        else:
                            metrics_logger.log("==== Prometheus Monitor already Active ====")
                if instance_name in metrics_constants.DELETED_INSTANCE: metrics_constants.DELETED_INSTANCE.remove(instance_name)
                metrics_logger.log("Post Activate Monitor result  :: {}".format(metrics_constants.METRICS_THREAD_OBJ.instances_obj))   

            elif response_headers['action']==metrics_constants.DELETE_MONITOR:
                app_type = response_headers.get("APP_NAME", None)
                instance_name = response_headers.get("instance_name", None)
                if app_type == metrics_constants.METRICS_STATSD.upper():
                    if str(metrics_util.STATSD_CONFIG.get('STATSD','enabled')) == 'true':
                        metrics_util.STATSD_CONFIG.set('STATSD','enabled','false')
                        metrics_util.persist_conf_data(metrics_constants.STATSD_CONF_FILE, metrics_util.STATSD_CONFIG)
                        metrics_constants.METRICS_THREAD_OBJ.stop(metrics_constants.METRICS_STATSD)
                    else:
                        metrics_logger.log("==== Statsd Monitor already Inactive ====")
                elif app_type == metrics_constants.METRICS_PROMETHEUS.upper():
                    if instance_name:
                        if str(metrics_util.PROMETHEUS_CONFIG.get(instance_name,'status')) != '3':
                            metrics_util.PROMETHEUS_CONFIG.set(instance_name,'status','3')
                            metrics_util.persist_conf_data(metrics_constants.PROMETHEUS_CONF_FILE, metrics_util.PROMETHEUS_CONFIG)
                            metrics_constants.METRICS_THREAD_OBJ.stop(instance_name)
                        else:
                            metrics_logger.log("==== Prometheus Monitor already Deleted ====")
                if instance_name not in metrics_constants.DELETED_INSTANCE: metrics_constants.DELETED_INSTANCE.append(instance_name)
                metrics_logger.log("Post Delete Monitor result  :: {}".format(metrics_constants.METRICS_THREAD_OBJ.instances_obj))   

            elif response_headers['action']==metrics_constants.DELETE_METRICS:
                app_type = response_headers.get("APP_NAME", None)
                metric=response_headers['metric']
                metrics = json.loads(metric)
                if app_type == metrics_constants.METRICS_STATSD.upper():
                    metrics_logger.log("Delete check for statsd :: {} :: {}".format(metrics, response_headers))
                    metrics_constants.METRICS_THREAD_OBJ.instances_obj[metrics_constants.METRICS_STATSD].delete_metric(metrics)
                elif app_type == metrics_constants.METRICS_PROMETHEUS.upper():
                    metrics_logger.log("Delete check for prometheus :: {} :: {}".format(metrics, response_headers))
                    for instance in metrics:
                        metrics_constants.METRICS_THREAD_OBJ.instances_obj[instance].delete_metric(metrics[instance])

            elif response_headers['action']==metrics_constants.STOP_STATSD:
                metrics_util.STATSD_CONFIG.set('STATSD','enabled','false')
                metrics_util.persist_conf_data(metrics_constants.STATSD_CONF_FILE, metrics_util.STATSD_CONFIG)
                if metrics_constants.METRICS_STATSD not in metrics_constants.DELETED_INSTANCE:
                    metrics_constants.DELETED_INSTANCE.append(metrics_constants.METRICS_STATSD)
                metrics_constants.METRICS_THREAD_OBJ.stop(metrics_constants.METRICS_STATSD)

            elif response_headers['action']==metrics_constants.START_STATSD:
                if metrics_util.STATSD_CONFIG.get('STATSD','enabled') == 'false':
                    metrics_util.STATSD_CONFIG.set('STATSD','enabled','true')
                    metrics_util.persist_conf_data(metrics_constants.STATSD_CONF_FILE, metrics_util.STATSD_CONFIG)
                    if metrics_constants.METRICS_STATSD in metrics_constants.DELETED_INSTANCE:
                        metrics_constants.DELETED_INSTANCE.remove(metrics_constants.METRICS_STATSD)
                    metrics_constants.METRICS_THREAD_OBJ.activate_statsd_monitor(metrics_util.STATSD_CONFIG)
                else:
                    metrics_logger.log("===== Statsd already stopped =====")

            elif response_headers['action']==metrics_constants.STOP_PROMETHEUS:
                metrics_util.PROMETHEUS_CONFIG.set('PROMETHEUS','enabled','false')
                metrics_util.persist_conf_data(metrics_constants.PROMETHEUS_CONF_FILE, metrics_util.PROMETHEUS_CONFIG)
                for instance, instance_obj in list(metrics_constants.METRICS_THREAD_OBJ.instances_obj.items()):
                    if instance != metrics_constants.METRICS_STATSD:
                        metrics_constants.METRICS_THREAD_OBJ.instances_obj.pop(instance)
                        instance_obj.stop()
                        metrics_constants.DELETED_INSTANCE.append(instance)
                metrics_logger.log("=========== instances for monitoring ======= :: {}".format(metrics_constants.METRICS_THREAD_OBJ.instances_obj))
            
            elif response_headers['action']==metrics_constants.START_PROMETHEUS:
                metrics_util.PROMETHEUS_CONFIG.set('PROMETHEUS','enabled','true')
                metrics_util.persist_conf_data(metrics_constants.PROMETHEUS_CONF_FILE, metrics_util.PROMETHEUS_CONFIG)
                if metrics_constants.METRICS_STATSD in metrics_constants.DELETED_INSTANCE:
                    metrics_constants.DELETED_INSTANCE=[instance for instance in metrics_constants.DELETED_INSTANCE if instance == metrics_constants.METRICS_STATSD]
                else:
                    metrics_constants.DELETED_INSTANCE=[]
                metrics_constants.METRICS_THREAD_OBJ.start_prometheus(metrics_util.PROMETHEUS_CONFIG)

            elif response_headers['action']==metrics_constants.REMOVE_METRICS_DC_ZIPS:
                metrics_util.remove_dc_zips()
                buffer.cleanUp()
                metrics_logger.log("------removing dc zips and cleaning buffers------ :: REMOVE_DC_ZIPS")

            elif response_headers['action']==metrics_constants.STOP_METRICS_AGENT:
                metrics_util.PROMETHEUS_CONFIG.set('PROMETHEUS','enabled','false')
                metrics_util.STATSD_CONFIG.set('STATSD','enabled','false')
                metrics_util.persist_conf_data(metrics_constants.PROMETHEUS_CONF_FILE, metrics_util.PROMETHEUS_CONFIG)
                metrics_util.persist_conf_data(metrics_constants.STATSD_CONF_FILE, metrics_util.STATSD_CONFIG)
                metrics_util.remove_dc_zips()
                buffer.cleanUp()
                metrics_logger.log("------removing dc zips and cleaning buffers------ :: STOP_METRICS_AGENT")
                for key, value in list(metrics_constants.METRICS_THREAD_OBJ.instances_obj.items()):
                    metrics_constants.METRICS_THREAD_OBJ.instances_obj.pop(key)
                    value.stop()
                metrics_logger.log("=========== instances for monitoring ======= :: {}".format(metrics_constants.METRICS_THREAD_OBJ.instances_obj))
            
            elif response_headers['action']==metrics_constants.START_METRICS_AGENT:
                metrics_util.PROMETHEUS_CONFIG.set('PROMETHEUS','enabled','true')
                metrics_util.STATSD_CONFIG.set('STATSD','enabled','true')
                metrics_util.persist_conf_data(metrics_constants.PROMETHEUS_CONF_FILE, metrics_util.PROMETHEUS_CONFIG)
                metrics_util.persist_conf_data(metrics_constants.STATSD_CONF_FILE, metrics_util.STATSD_CONFIG)
                metrics_constants.METRICS_THREAD_OBJ.start_prometheus(metrics_util.PROMETHEUS_CONFIG)
                metrics_constants.METRICS_THREAD_OBJ.activate_statsd_monitor(metrics_util.STATSD_CONFIG)
                metrics_logger.log('=========== instances for monitoring ======= {}'.format(metrics_constants.METRICS_THREAD_OBJ.instances_obj))

        if persist_statsd_conf_changes:
            with open(metrics_constants.STATSD_CONF_FILE,'w+') as config:
                metrics_util.STATSD_CONFIG.write(config)
        if persist_prometheus_conf_changes:
            with open(metrics_constants.PROMETHEUS_CONF_FILE,'w+') as config:
                metrics_util.PROMETHEUS_CONFIG.write(config)
    except Exception as e:
        metrics_logger.errlog("Exception in handling response header")
        metrics_logger.errlog(str(traceback.print_exc()))
    

