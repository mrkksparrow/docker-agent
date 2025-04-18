from com.manageengine.monagent.database import DatabaseLogger, DBUtil, DBConstants
import traceback,copy

class ChildDatabaseDC:
    def __init__(self,instance_info,xmlExecutorObj,dbs):
        try:
            self.instance_info  = instance_info
            self.xmlExecutorObj = xmlExecutorObj
            self.dbs            = dbs
        except Exception as e:
            DatabaseLogger.Logger.log("Exception :: constructor of ChilDatabaseDC - {}".format(e))

    def collect_database_data(self):
        try:
            result, current_data    = {}, {}
            Version,disabled_queries =  self.instance_info.get("Version"),self.instance_info.get("disabled_queries") or {}

            tags = ["pg_database"]
            
            for datname in self.dbs:
                raw_data, db_data   =   DBUtil.executeMultiTags(self.xmlExecutorObj, tags, self.instance_info,Version,disabled_queries,DBConstants.POSTGRES_DATABASE,datname)
                
                for tag in db_data:
                    if type(db_data[tag]) is dict:
                        if datname not in current_data:
                            current_data[datname]={}
                        current_data[datname].update(db_data[tag])
                
                result.update(self.get_basic_performance_data(current_data, datname))
        except Exception as e:
            DatabaseLogger.Logger.log("Exception :: collect_database_data - {} \ntraceback - {}".format(e,traceback.print_exc()))
        return current_data,result
    
    def get_basic_performance_data(self, current_data, datname):
        result = {}
        try:
            previous_data   = (self.instance_info.get("cached_data") or {}).get("child_data")
            
            if previous_data and datname in previous_data and current_data and datname in current_data:
                keys_dict = ["ss","is","hbh","hbr","hur","dr","lr","rins","rupd","rdel"]

                result = copy.deepcopy(current_data[datname])
                for key in keys_dict:
                    if key in previous_data[datname] and key in current_data[datname]:
                        if current_data[datname][key] >= previous_data[datname][key]:
                            result[key] = current_data[datname][key] - previous_data[datname][key]
                        else:
                            if result[key]>=0:
                                result[key] = current_data[datname][key]
                            elif key in result:
                                    result.pop(key)
                result={datname:result}
        except Exception as e:
            DatabaseLogger.Logger.log("Exception :: get_basic_performance_data - {} \ntraceback - {}".format(e,traceback.print_exc()))
        return result
