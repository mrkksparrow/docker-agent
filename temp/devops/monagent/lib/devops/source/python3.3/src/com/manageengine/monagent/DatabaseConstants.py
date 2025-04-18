#$Id$
import time
import platform
import os
import sys
import tempfile
import getpass
import traceback
from pwd import getpwnam
import pwd
import traceback

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

AGENT_CONF_DIR = AGENT_WORKING_DIR + '/conf'
APPS_FOLDER = os.path.join(AGENT_CONF_DIR, "apps")

#MySQL
DATABASE_SETTING="database"
MYSQL_DB="mysql"
MYSQLDB="mysqldb"
MYSQL_CONF_FOLDER=os.path.join(APPS_FOLDER, "mysql")
MYSQL_CONF_FILE=os.path.join(MYSQL_CONF_FOLDER, "mysql.cfg")
MYSQL_INPUT_FILE=os.path.join(AGENT_CONF_DIR,'mysql_input')
MYSQL_PROCESS_COMMAND='/bin/ps -eo pid,user,pri,fname,pcpu,pmem,nlwp,command,args | grep -v "\[sh] <defunct>" | grep -E mysqld | grep -v grep'
MYSQL_PID_COMMAND='netstat -nltp | grep -v "\[sh] <defunct>" | grep -E mysqld | grep -v grep'
MYSQL_VERSION_COMMAND="mysql -V"
MONGODB_DB="mongodb"
MONGODB_CONF_FOLDER=os.path.join(APPS_FOLDER, "mongodb")
MONGODB_CONF_FILE=os.path.join(MONGODB_CONF_FOLDER, "mongodb.cfg")
MONGODB_INPUT_FILE=os.path.join(AGENT_CONF_DIR,'mongodb_input')
MONGODB_PID_COMMAND='netstat -nltp | grep -v "\[sh] <defunct>" | grep -E mongod | grep -v grep'
MONGODB_VERSION_COMMAND='mongo --version'
POSTGRES_DB="postgres"
POSTGRES_CONF_FOLDER=os.path.join(APPS_FOLDER, "postgres")
POSTGRES_CONF_FILE=os.path.join(POSTGRES_CONF_FOLDER, "postgres.cfg")
POSTGRES_INPUT_FILE=os.path.join(AGENT_CONF_DIR,'postgres_input')
POSTGRES_PID_COMMAND='netstat -nltp | grep -v "\[sh] <defunct>" | grep -E postgres | grep -v grep'
POSTGRES_VERSION_COMMAND='psql -V'
DATABASE_APPLICATIONS={'mysql': {'conf_file':MYSQL_CONF_FILE, 'working_dir':MYSQL_CONF_FOLDER, 'input_file':MYSQL_INPUT_FILE},
                       'mongodb': {'conf_file':MONGODB_CONF_FILE, 'working_dir':MONGODB_CONF_FOLDER, 'input_file':MONGODB_INPUT_FILE},
                       'postgres': {'conf_file':POSTGRES_CONF_FILE, 'working_dir':POSTGRES_CONF_FOLDER, 'input_file':POSTGRES_INPUT_FILE}}
