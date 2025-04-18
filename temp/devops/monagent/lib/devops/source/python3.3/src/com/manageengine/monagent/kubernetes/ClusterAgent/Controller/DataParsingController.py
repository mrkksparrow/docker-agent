'''
@author: bharath.veerakumar

Created on Feb 20 2024
'''


import time
from flask.blueprints import Blueprint
from flask import request
from com.manageengine.monagent.kubernetes import KubeGlobal
from com.manageengine.monagent.kubernetes.ClusterAgent import ClusterAgentUtil


blp = Blueprint("DataParsingController", __name__)


@blp.route("/pd/get_dc_json/<dc_name>", methods=('GET', 'POST'))
def get_dc_json(dc_name):
    dc_obj = KubeGlobal.CLUSTER_AGENT_DC_OBJS_LIST[dc_name]
    if dc_obj.is_pre_parsing_needed:
        # constructing the file path for requested data_type
        file_path = KubeGlobal.PARSED_DATA_FOLDER_PATH + '/{}'.format(KubeGlobal.DATA_TYPE_PARSED_FILE_MAP[dc_name])

        # checking if that file is in cache (1 min TTL)
        parsed_data = ClusterAgentUtil.read_json_from_file(file_path)
        if parsed_data:
            return parsed_data

    return dc_obj.dc_class(dc_obj).get_data_for_cluster_agent(request.args) if request.method == 'GET' else dc_obj.dc_class(dc_obj).get_data_for_cluster_agent(request.get_json())
