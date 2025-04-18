#$Id$
import os
from com.manageengine.monagent import AgentConstants

def initialize():
    if not os.path.exists(AgentConstants.AGENT_LOG_DIR):
        os.makedirs(AgentConstants.AGENT_LOG_DIR)
    if not os.path.exists(AgentConstants.AGENT_LOG_DETAIL_DIR):
        os.makedirs(AgentConstants.AGENT_LOG_DETAIL_DIR)
    if not os.path.exists(AgentConstants.AGENT_CONF_BACKUP_DIR):
        os.makedirs(AgentConstants.AGENT_CONF_BACKUP_DIR)
    if not os.path.exists(AgentConstants.AGENT_QUERY_CONF_DIR):
        os.makedirs(AgentConstants.AGENT_QUERY_CONF_DIR)
    if not os.path.exists(AgentConstants.AGENT_UPLOAD_DIR):
        os.makedirs(AgentConstants.AGENT_UPLOAD_DIR)
    if not os.path.exists(AgentConstants.AGENT_DATA_DIR):
        os.makedirs(AgentConstants.AGENT_DATA_DIR)
    if not os.path.exists(AgentConstants.AGENT_SCRIPTS_DIR):
        os.makedirs(AgentConstants.AGENT_SCRIPTS_DIR)
    if not os.path.exists(AgentConstants.AGENT_UPGRADE_DIR):
        os.makedirs(AgentConstants.AGENT_UPGRADE_DIR)
    if not os.path.exists(AgentConstants.AGENT_TEMP_DIR):
        os.makedirs(AgentConstants.AGENT_TEMP_DIR)
    
    
initialize()