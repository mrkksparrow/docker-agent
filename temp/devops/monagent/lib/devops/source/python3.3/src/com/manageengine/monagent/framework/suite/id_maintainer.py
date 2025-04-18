'''
Created on 02-September-2017

@author: giri
'''
import json

#s24x7 packages
from com.manageengine.monagent.util import AgentUtil
from com.manageengine.monagent.logger import AgentLogger
from com.manageengine.monagent import AgentConstants

def handle_s24x7_id(app, dict_data):
    s24x7_id_dict = dict_data
    if os.path.isfile(AgentConstants.AGENT_APPS_ID_FILE):
        with open(AgentConstants.AGENT_APPS_ID_FILE, "r") as fp:
            s24x7_id_dict = json.loads(fp.read())
        if type(s24x7_id_dict) is dict:
            s24x7_id_dict[app] = dict_data
    save_status = AgentUtil.writeDataToFile(AgentConstants.AGENT_DOCKER_SITE24X7ID, s24x7_id_dict)
    if not save_status:
        AgentLogger.log(AgentLogger.APPS, "Unable to update id file")

