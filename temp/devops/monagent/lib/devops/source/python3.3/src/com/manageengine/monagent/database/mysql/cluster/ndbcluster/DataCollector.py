from com.manageengine.monagent.database import DatabaseLogger
from com.manageengine.monagent.database.mysql.cluster.ndbcluster import PerformanceMetrics,PeriodicalMetrics

class NDBCollector:
    def collect_ndb_data(self,dict_param):
        result = {}
        try:
            collection_type     =   dict_param.get("collection_type")
            if collection_type == "8":
                result  =   PerformanceMetrics.getData(dict_param)
            elif collection_type == "9":
                result  =   PeriodicalMetrics.getData(dict_param)
                
        except Exception as e:
            DatabaseLogger.Logger.log("Exception :: NDBCollector.collect_ndb_data() - {}".format(e))
        return result