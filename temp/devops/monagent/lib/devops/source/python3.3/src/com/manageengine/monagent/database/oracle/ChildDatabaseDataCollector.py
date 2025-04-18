from com.manageengine.monagent.database import DatabaseLogger, DBUtil, DBConstants
import traceback,copy

class ChildDatabaseDC:
    def __init__(self,instance_info,xmlExecutorObj,dbs,connection=None):
        try:
            self.instance_info  = instance_info
            self.xmlExecutorObj = xmlExecutorObj
            self.dbs            = dbs
            if connection:
                self.__connection   = connection
        except Exception as e:
            DatabaseLogger.Logger.log("Exception :: oracledb :: instance - {} :: constructor of ChilDatabaseDC - {}".format(instance_info.get("instance_name"),e))

    def collect_database_data(self):
        try:
            raw_data,result    = {}, {}
            Version,disabled_queries =  self.instance_info.get("Version"),self.instance_info.get("disabled_queries") or {}

            tags    =   ["oracledb"]
            # __connection = self.__connection
            status,__connection = DBUtil.getConnection(self.instance_info,DBConstants.ORACLE_DATABASE,self.instance_info.get('service_name'))
            if status:
                for datname in self.dbs:
                    status,attempts  = alter_session_container_db(__connection,datname,self.instance_info.get("instance_name"))
                    if status:
                        previousDC=((self.instance_info.get("cached_data") or {}).get("child_data") or {}).get(datname) or {}
                        raw_data[datname], db_data   =   DBUtil.executeMultiTags(self.xmlExecutorObj, tags, self.instance_info,Version,disabled_queries,DBConstants.ORACLE_DATABASE,extended_connection=__connection,previousDC=previousDC)

                        result[datname] = {"availability":"1", "cid" : self.dbs[datname].get("mid")}

                        try:
                            if "SESSION" in db_data:
                                db_data["SESSION"]["tuss"] = int(db_data["SESSION"].get("inss") or 0) + int(db_data["SESSION"].get("acss") or 0)
                                db_data["SESSION"]["uscmrb"] = int(db_data["SESSION"].get("usrb") or 0) + int(db_data["SESSION"].get("uscm") or 0)
                                db_data["SESSION"]["tert"] = int(db_data["SESSION"].get("rert") or 0) + int(db_data["SESSION"].get("sert") or 0)
                        except Exception as e:
                            DatabaseLogger.Logger.log("instance - {} :: issue in SESSION metrics calculation :: datname - {} :: Error - {} ".format(self.instance_info.get("instance_name"),datname,e))

                        
                        result[datname].update(db_data.get('SESSION') or {})
                        result[datname].update(db_data.get('SINGLE_VALUES') or {})
                        dc_tablespace = db_data.get("TABLESPACE") or []
                        final_ts = []

                        child_keys = self.dbs[datname].get(DBConstants.ORACLE_CHILD_TABLESPACE_TYPE) or {}
                        for tablespace in dc_tablespace:
                            if tablespace.get("tsnm"):
                                if tablespace["tsnm"] in child_keys and "mid" in child_keys[tablespace["tsnm"]] and child_keys[tablespace["tsnm"]].get("status")=="0":
                                    tablespace["cid"] = child_keys[tablespace["tsnm"]]["mid"]
                                    final_ts.append(tablespace)
                            else: 
                                DatabaseLogger.Logger.log("instance - {} :: tsnm is not present in database :: {} :: {}".format(self.instance_info.get("instance_name"),datname,tablespace))
                        result[datname]["TABLESPACE"] = final_ts

                    else:
                        result[datname]= {"availability":"0","attempts":attempts, "cid" : self.dbs[datname].get("mid")}
                        DatabaseLogger.Logger.log("unable to alter connection for collect_database_data :: instance_name - {} :: database - {}".format(self.instance_info.get("instance_name"),datname))
                __connection.close() # comment if global connection is used.
                
        except Exception as e:
            DatabaseLogger.Logger.log("Exception :: oracledb :: collect_database_data - {} :: instance - {}".format(e,self.instance_info.get("instance_name")))
            traceback.print_exc()
        return raw_data,result

def alter_session_container_db(connection,container_name,instance,alter_connection_attempt=1,max_connection_attempts=2):
    status = False
    try:
        cursor = connection.cursor()
        cursor.execute('alter session set container={}'.format(container_name))
        # cursor.execute("select sys_context('USERENV','CON_NAME') from dual")
        # con_name = cursor.fetchall()
        cursor.close()
        # con_name = con_name[0][0] if con_name else con_name
        # DatabaseLogger.Logger.log(" oracle :: instance - {} :: Alter session attempt :: {} :: container_name :: {} :: altered to - {}".format(instance,alter_connection_attempt,container_name,con_name))
        DatabaseLogger.Logger.log(" oracle :: instance - {} :: Alter session attempt :: {} :: container_name :: {}".format(instance,alter_connection_attempt,container_name))
        status = True
        return status,alter_connection_attempt
    except Exception as e:
        DatabaseLogger.Logger.log("Exception while trying to alter session for db - {} :: instance - {} :: alter_session_attempt - {} :: Error - {}".format(container_name,instance,alter_connection_attempt,e))
        # if alter_connection_attempt<max_connection_attempts:
        #     return alter_session_container_db(connection,container_name,instance,alter_connection_attempt+1)
        # else:
        #     return status,alter_connection_attempt
        return status,alter_connection_attempt
