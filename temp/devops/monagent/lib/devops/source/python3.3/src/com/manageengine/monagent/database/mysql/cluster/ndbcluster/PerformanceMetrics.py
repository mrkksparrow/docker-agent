from com.manageengine.monagent.database                             import DatabaseLogger,DBConstants, DBUtil
from com.manageengine.monagent.database.mysql                       import MySQLUtil
import traceback,time,json

# Don't change the order of MEMU,LSP,LBS
def getQueries(data):
    try:
        MEMU    =   DBUtil.ConvertL2NestingToL1(data.get("MEMU")) or {}
        LSP     =   DBUtil.ConvertL2NestingToL1(data.get("LSP"))  or {}
        LBS     =   DBUtil.ConvertL2NestingToL1(data.get("LBS"))  or {}

        CLCG    =   data.get("CLCG")  or {}
        PS      =   data.get("PS")    or {}
        NDS     =   data.get("NDS")   or {}
        MBSP    =   data.get("MBSP")  or {}
        DWSA    =   data.get("DWSA")  or {}
        DPB     =   data.get("DPB")   or {}
        return [MEMU, LSP, LBS, CLCG, PS, NDS, MBSP, DWSA, DPB]
    except Exception as e:
        DatabaseLogger.Logger.log("Exception :: getQueries - {}".format(e))
        return []

# Cluster Level Performance metrics
def getOverallCommon(data, tag):
    result  =   {}
    try:
        if data and data.get(tag):
            result = DBUtil.ConvertL2NestingToL1({tag: data[tag]})
    except Exception as e:
        DatabaseLogger.Logger.log("Exception :: getOverallCommon tag - {} :: Exception - {}".format(tag, e))
    return result.get(tag) or {}

# Metrics cached to collect difference between two time intervals

def CalculateCachedDPB(new, old):
    if not old or not new:
        return {}
    result = {"opr": 0, "opw": 0}
    try:
        __dict      =   old if len(old) < len(new) else new
        for node in __dict:
            psr, psw         =   old[node]["psr"] - new[node]["psr"],old[node]["psw"] - new[node]["psw"]
            result["opr"]   +=   psr if psr > 0 else 0
            result["opw"]   +=   psw if psw > 0 else 0
        old.update(new)
    except Exception as e:
        DatabaseLogger.Logger.log("Exception :: CalculateCachedDPB - {}".format(e))
    return result

def getOverallDiskPageBuffer(__DPB, data):
    if not data.get("DPB") or not __DPB:
        return {}
    hit_ratio, count, DPB   =   0, 0, data["DPB"]

    try:
        result = CalculateCachedDPB(DPB, __DPB)

        for node in DPB:
            count += 1
            if DPB[node].get("hr") == None:
                return result
            hit_ratio      +=   DPB[node]["hr"]

        result["ohr"]       =   hit_ratio / count

    except Exception as e:
        DatabaseLogger.Logger.log("Exception :: getOverallDiskPageBuffer - {}".format(e))
    return result

def getOverallDataNodeBytesTransferred(__TSPS, data):
    if not data.get("TSPS") or not __TSPS:
        return {}
    TSPS, result = data["TSPS"], {"otbs": 0, "otbr": 0}
    try:
        for node in TSPS:
            result["otbs"] += TSPS[node]["bst"] - __TSPS[node]["bst"]
            result["otbr"] += TSPS[node]["brd"] - __TSPS[node]["brd"]
    except Exception as e:
        DatabaseLogger.Logger.log("Exception :: getOverallDataNodeBytesTransferred - {}".format(e))
    return result

# Constructed final output performance metrics

def getOverallPerformanceMetricsData( data, cached, dict_param, childKeys,time_diff):
    result = {}
    mysqlNDBmonkey               =   dict_param.get("mysqlNDBmonkey")
    try:
        result.update(  getOverallDiskPageBuffer(           cached.get("DPB"),  data   ) )
        result.update(  getOverallDataNodeBytesTransferred( cached.get("TSPS"), data   ) )

        result.update(  getOverallCommon(data, "OMEM")  )
        result.update(  getOverallCommon(data, "OLSP")  )
        result.update(  getOverallCommon(data, "OLBS")  )
        
        result.update(  { "ct"  : MySQLUtil.getTimeInMillis(time_diff) } )

        result.update(  data.get("GV")      or {}    )
        result.update(  data.get("GS")      or {}    )
        result.update(  data.get("NC")      or {}    )
        result.update(  data.get("ACT")     or {}    )
        result.update(  data.get("ERROR")   or {}    )

        return convertToUploadFormat(  result, getPerformanceMetricsData( data, childKeys, time_diff ), mysqlNDBmonkey  )

    except Exception as e:
        DatabaseLogger.Logger.log( "Exception :: getOverallPerformanceMetricsData - {}".format(e) )
    
def convertToUploadFormat( overallPerf, perf, mysqlNDBmonkey ):
    try:
        final_list,count,temp   =   [], 0, []
        overallPerf['mid']      =   mysqlNDBmonkey
        Nodes                   =   (perf.get('Nodes') and perf.pop('Nodes')) or {}
        
        overallPerf.update( perf or {} )
        final_list.append( overallPerf )

        for node in Nodes:
            count               =   count+1
            Nodes[node]["nna"]  =   node

            temp.append( Nodes[node] )

            if count==DBConstants.NDB_CHILD_NODES_PER_FILE:
                final_list.append( {"Nodes": temp, "mid": mysqlNDBmonkey} )
                temp            =   []
                count           =   0

        if count>0:
            final_list.append( {"Nodes": temp, "mid": mysqlNDBmonkey} )

        return final_list
    except Exception as e:
        DatabaseLogger.Logger.log( "Exception :: convertToUploadFormat - {}".format(e) )


def getPerformanceMetricsData( __data, __childKeys, __time_diff ):
    result = {}
    try:
        arr             =   getQueries(__data)
        Nodes           =   {}
        now             =   MySQLUtil.getTimeInMillis(__time_diff)
        for element in arr:
            for key in element:
                if __childKeys.get(key):
                    if Nodes.get(key) == None:
                        Nodes[key] = {}
                    Nodes[key].update( {"cid": __childKeys[key],"ct": now } )
                    Nodes[key].update( element[key] )

        if __data.get("DNC"):
            for nna in __data["DNC"]:
                if Nodes.get(nna) == None:
                    Nodes[nna] = {}
                Nodes[nna].update({"DNC":__data["DNC"][nna]})

        RSRC, TSP = __data.get("RSRC"), __data.get("TSP")
        if RSRC:
            for key in RSRC:
                if Nodes.get(key):
                    Nodes[key]["resources"]     =   __data["RSRC"][key]

        if TSP:
            for key in TSP:
                if Nodes.get(key):
                    Nodes[key]["transporters"]  =    __data["TSP"][key]

        if Nodes:
            result["Nodes"]     =   Nodes

        result.update(__data.get("AVS") or {})

        if __data.get("RSIF"):
            result["RSIF"]  =   {}
            for node_name in __data["RSIF"]:
                if __childKeys.get(node_name):
                    result["RSIF"][node_name]   =   __data["RSIF"][node_name].copy()
                    result["RSIF"][node_name].update({"cid":__childKeys[node_name]})

    except Exception as e:
        DatabaseLogger.Logger.log("Exception :: getPerformanceMetricsData - {}".format(e))
    return result


def fetchHelper(xmlExecutorObj, dict_param,onceADayBool):
    try:
        tags    =   ["perf","overallperf"]
        if onceADayBool:
            tags.append("config")
        raw_data,_data   =   DBUtil.executeMultiTags(xmlExecutorObj, tags , dict_param, dict_param.get('NDB_version'), dict_param.get('NDB_disabled_queries'), DBConstants.MYSQL_DATABASE)
        
        return _data
    except Exception as e:
        DatabaseLogger.Logger.log("Exception :: PerformanceMetrics.fetchHelper -  {}".format(e))
        return {}

def getData(params):
    try:
        section_dict    =   params.get('section_dict')
        time_diff       =   params.get("time_diff") or 0
        xmlExecutorObj  =   DBUtil.getXMLExecutorObj(DBConstants.MYSQL_NDB_CLUSTER,params.get("xmlString"))
        _data           =   fetchHelper(xmlExecutorObj, section_dict, params.get('onceADayBool'))
        output          =   getOverallPerformanceMetricsData(_data, params.get('cached') or {}, section_dict, params.get('child_keys'),time_diff)

        return _data,output
    except Exception as e:
        DatabaseLogger.Logger.log("Exception :: PerformanceMetrics.getData - {}".format(e))