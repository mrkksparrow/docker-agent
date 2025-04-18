import os
import sys

if not "watchdog" in sys.argv[0].lower():
    AGENT_SRC_CHECK =os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(sys.argv[0])))))
else:
    AGENT_SRC_CHECK = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(sys.argv[0])))))
splitted_paths = os.path.split(AGENT_SRC_CHECK)
if splitted_paths[1].lower() == "com":
    IS_VENV_ACTIVATED = True
    AGENT_WORKING_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(AGENT_SRC_CHECK))))))
    AGENT_VENV_BIN_PYTHON = os.path.join(os.path.dirname(AGENT_WORKING_DIR), "venv", "bin", "python")
    STATSD_EXECUTOR_PATH=AGENT_VENV_BIN_PYTHON +' '+os.path.dirname(os.path.realpath(sys.argv[0]))+'/metrics_agent.py'
    if not os.path.isfile(AGENT_VENV_BIN_PYTHON):
        AGENT_VENV_BIN_PYTHON = None
else:
    IS_VENV_ACTIVATED = False
    AGENT_WORKING_DIR = os.path.dirname(os.path.dirname(os.path.realpath(sys.argv[0])))
    STATSD_EXECUTOR_PATH=os.path.dirname(os.path.realpath(sys.argv[0]))+'/Site24x7MetricsAgent'
STATSD_START="start"
STATSD_STOP="stop"
STATSD_START_COMMAND= STATSD_EXECUTOR_PATH+" "+STATSD_START
STATSD_STOP_COMMAND=STATSD_EXECUTOR_PATH+" "+STATSD_STOP
DEBUG_MODE=False

SUSPEND_MONITOR='9000'
DELETE_MONITOR='9001'
ACTIVATE_MONITOR='9003'
DELETE_METRICS='9002'

REMOVE_METRICS_DC_ZIPS='9010'
STOP_METRICS_AGENT='STOP_METRICS_AGENT'
STOP_PROMETHEUS='STOP_PROMETHEUS'
STOP_STATSD='STOP_STATSD'
START_METRICS_AGENT='START_METRICS_AGENT'
START_PROMETHEUS='START_PROMETHEUS'
START_STATSD='START_STATSD'
METRICS_LOGGER_NAME="METRICS"
METRICS_FILE='metrics.txt'
METRICS_WORKING_DIRECTORY=AGENT_WORKING_DIR+"/metrics"
METRICS_DAEMON_PID_FILE=os.path.join("/tmp",'metrics.pid')
METRICS_DATA_TEXT_DIRECTORY=os.path.join(METRICS_WORKING_DIRECTORY,'data')
METRICS_DATA_ZIP_DIRECTORY=os.path.join(METRICS_WORKING_DIRECTORY,'upload')
STATSD_WORKING_DIR=METRICS_WORKING_DIRECTORY+"/statsd"
METRICS_LOG_PATH=AGENT_WORKING_DIR+"/logs/"
STATSD_KEYS_PATH=STATSD_WORKING_DIR+"/"
STATSD_CONF_FILE=STATSD_WORKING_DIR+"/statsd.cfg"
STATSD_URI="/plugin/statsd/MetricsDataCollector?"
STATSD_KEY_FILE="metrics.json"
METRICS_METHOD={'c':'com.manageengine.monagent.metrics.counter.counting',
        'g':'com.manageengine.monagent.metrics.gauge.gauge_storing',
        's':'com.manageengine.monagent.metrics.sets.sets_storing',
        'ms':'com.manageengine.monagent.metrics.timer.time_calculation'}
HTTP_PROTOCOL='http'
HTTPS_PROTOCOL='https'
METRICS_STATSD='statsd'
METRICS_PROMETHEUS='prometheus'
METRICS_TYPES=[METRICS_STATSD,METRICS_PROMETHEUS]
METRICS_THREAD_OBJ = None
METRICS_TYPE_NAMING_MAPPER={'c':'counter','g':'gauge','s':'set','ms':'timer'}
ZIP_METRICS_LIMIT = 100
METRICS_CLASS_CONF={
                        METRICS_STATSD:{"module":"com.manageengine.monagent.metrics.statsd_executor","class":"StatsDServer"},
                        METRICS_PROMETHEUS:{"module":"com.manageengine.monagent.metrics.prometheus_executor","class":"PrometheusWrapper"}
                    }
PROMETHEUS_WORKING_DIR=METRICS_WORKING_DIRECTORY+"/"+METRICS_PROMETHEUS
PROMETHEUS_CONF_FILE=PROMETHEUS_WORKING_DIR+"/prometheus.cfg"
PROMETHEUS_KEYS_PATH=PROMETHEUS_WORKING_DIR+"/"
PROMETHEUS_KEY_FILE="metrics.json"
SERVER_CONFIG_FILE=os.path.join(AGENT_WORKING_DIR,"conf","monagent.cfg")
AGENT_LOGGING_CONF_FILE=os.path.join(AGENT_WORKING_DIR,"conf","logging.xml")
AGENT_TEMP_DIR=os.path.join(AGENT_WORKING_DIR,"temp")
INSTALL_TIME_FILE="install_time"
SERVER_NAME="plus.site24x7.com"
SERVER_PORT=443
SERVER_TIMEOUT=30
SERVER_PROTOCOL="https"
SERVER_AGENT_KEY=None
DEVICE_KEY=None
FILES_TO_UPLOAD_BUFFER="FILES_TO_UPLOAD_BUFFER"
MAX_SIZE_UPLOAD_BUFFER=1000
PROMETHEUS_URI="/plugin/prometheus/MetricsDataCollector?"
PROMETHEUS_INSTANCES=[]
DELETED_INSTANCE=[]
DELETE_STATSD_INSTANCE=[]
PROXY_SERVER = None
PROXY_SERVER_PORT = None
PROXY_USERNAME = None
PROXY_PASSWORD = None
PROXY_PROTOCOL = None
PROXY_URL = None
LOCAL_SSL_CONTEXT = None
SSL_VERIFY = False
CA_CERT_FILE = os.path.join(AGENT_WORKING_DIR,"lib","lib","certifi","cacert.pem")
if not IS_VENV_ACTIVATED:
    CA_CERT_FILE = os.path.join(AGENT_WORKING_DIR,"lib","lib","certifi","cacert.pem")
else:
    try:
        import certifi
        CA_CERT_FILE = certifi.where()
    except Exception as e:
        pass

