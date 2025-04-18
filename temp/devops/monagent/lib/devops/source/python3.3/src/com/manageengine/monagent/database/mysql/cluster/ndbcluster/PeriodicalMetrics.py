import socket,json
from com.manageengine.monagent.database                             import DatabaseLogger, DBUtil, DBConstants

def addChildKey(data,child_keys):
    try:
        for node_name in data:
            if child_keys.get(node_name):
                data[node_name].update({"cid":child_keys[node_name]})
        return data
    except Exception as e:
        DatabaseLogger.Logger.log("Exception :: PeriodicalMetrics.addChildKey - {} :: child_keys - {}".format(e,child_keys))

def checkChanges(cachedData,freshData):
    try:
        temp={}
        for node_name,node_value in freshData.items():
            child_tmp   =   node_value.copy()
            if "upt" in child_tmp:
                child_tmp.pop("upt")

            if child_tmp.get('nhn'):
                child_tmp['ip']     =   socket.gethostbyname(child_tmp['nhn'])

            temp[node_name]         =   child_tmp

        str_temp=json.dumps(temp)

        if str_temp!=cachedData:
            return True,temp
    except Exception as e:
        DatabaseLogger.Logger.log("Exception :: PeriodicalMetrics.checkChanges - {}".format(e))
    return False,cachedData

# Topology data - executed every 3 mins, if changes detected then the data will be send to server

def getData(params):
    try:
        section_dict    =   params.get('section_dict')
        xmlExecutorObj  =   DBUtil.getXMLExecutorObj(DBConstants.MYSQL_NDB_CLUSTER,params.get("xmlString"))
        raw_data, _data =   DBUtil.executeMultiTags(xmlExecutorObj, ["topology"],section_dict, section_dict.get('NDB_version'), section_dict.get('NDB_disabled_queries'), DBConstants.MYSQL_DATABASE).get("TOPO")

        data_with_cid   =   addChildKey(_data,params.get('child_keys'))
        changed,cached  =   checkChanges(params.get('cached'),data_with_cid)
        final_data      =   {"mid":section_dict['mysqlNDBmonkey'],"Nodes":data_with_cid} if changed else None
    except Exception as e:
        DatabaseLogger.Logger.log("Exception :: PeriodicalMetrics.getData - {}".format(e))
    return changed,final_data,cached
