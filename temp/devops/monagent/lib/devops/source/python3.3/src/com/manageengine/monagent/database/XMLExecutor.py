import xml.etree.ElementTree as ET
import decimal,re,traceback,datetime,copy,time
try:
    import psycopg2
    ExceptionClass = psycopg2.Error
except:
    ExceptionClass = Exception

from com.manageengine.monagent.database import DatabaseLogger
""" This executor parses the xml file and converts it to dict which is then used to generate output """

class Executor(object):
    def __init__(self,xmlString) -> None:
        try:
            root = ET.fromstring(xmlString)
            self.__parse(root)
        except Exception as e:
            DatabaseLogger.Logger.log("Error while initializing Executor - {}".format(e))

    def __parse(self,__root):
        try:
            __parsedStructure,tags = {},set()
            for __element in __root:
                if __element.tag not in tags:
                    tags.add(__element.tag)
                    __parsedStructure[__element.tag] = {}

            for element in __root:
                split_query = str(element.attrib.get("Query")).strip(' ;').split(';')
                len_split_query = len(split_query)
                if len_split_query>=2:
                    raise Exception("\n\n Warning :: Executor.parse :: Vulnerability found while parsing query :: {} queries found\n query :: {}\n\n".format(len_split_query,split_query))
 
                if not str(element.attrib.get("Query")).startswith("select"):
                    raise Exception("\n\n Warning :: Executor.parse :: Vulnerability found while parsing query\n\n")

                queryname = element.get("Name") +"--"+ element.get("Version") if element.get("Version") else element.get("Name")
                __parsedStructure[element.tag][queryname] = self.__createEntry( element )

            self.__parsedStructure = __parsedStructure
        except Exception as e:
            DatabaseLogger.Logger.log( "Error while parsing :: Executor.parse :: Error -> {}".format(e))
            self.__parsedStructure = {}
    
    @staticmethod
    def __createEntry(__element):
        try:
            __attrib = __element.attrib
            __counter_metrics = []
            _colDict, _keys = {}, {}
            for _col in __element:
                if _col.get("Res") == "True":
                    _key = {}
                    for __res in _col:
                        _key.update({__res.get("Name"): __res.get("DisplayName")})
                        if __res.get('IsCounterMetric') == "True":
                            __counter_metrics.append(__res.get("DisplayName"))
                    _keys.update({_col.attrib["DisplayName"]: _key})
                elif _col.get("IsCounterMetric") == "True":
                    __counter_metrics.append(_col.get("DisplayName"))
                _colDict.update({_col.attrib["Name"]: _col.attrib["DisplayName"]})
            return {
                "Query": __attrib["Query"],
                "Col": _colDict,
                "Format": __attrib.get("Format"),
                "KeyWithNone": __attrib.get("KeyWithNone"),
                "Res": _keys,
                "Version": __attrib.get("Version"),
                "CounterMetrics": __counter_metrics
            }
        except Exception as e:
            DatabaseLogger.Logger.log( "class :: Executor.__createEntry :: Error -> {}".format(e))

    # Used by executor to validate query based on version
    @staticmethod
    def isValidVersion(version, Versions):
        try:
            version = re.findall("\d+\.?\d?\d?", version)
            if len(version)>=1:
                num=float(version[0])
            else:
                return False
            if Versions == None:
                return True
            for v in Versions:
                if v == '':
                    continue
                if v == version:
                    return True
                if '<=' in v:
                    if num<=float(v.lstrip('<=')):
                        return True
                elif '>=' in v:
                    if num>=float(v.lstrip('>=')):
                        return True
                elif '<' in v:
                    if num<=float(v.lstrip('<')):
                        return True
                elif '>' in v:
                    if num>=float(v.lstrip('>')):
                        return True
            return False
        except Exception as e:
            DatabaseLogger.Logger.log("isValidVersion :: current version - {} Supported Versions - {} Error - {}".format(version,Versions,e))
            return False
    
    def __getVersionSpecificQueriesName(self, tag, __version, disabled_queries):
        try:
            queries_to_execute = []
            if tag not in self.__parsedStructure:
                return None
            DatabaseLogger.Logger.debug("tag - {} :".format(tag))
            for query_name in self.__parsedStructure[tag]:
                __versions = self.__parsedStructure[tag][query_name].get("Version")
                if tag in disabled_queries and query_name.split("--")[0] in disabled_queries[tag]:
                    continue
                if __versions == None or self.isValidVersion(__version, __versions.split(",")):
                    DatabaseLogger.Logger.debug("query_name - {} :: __version - {} :: __versions - {}".format(query_name,__version,__versions))
                    queries_to_execute.append(query_name)
                else:
                    DatabaseLogger.Logger.debug("not included :: query_name - {} :: __version - {} :: __versions - {}".format(query_name,__version,__versions))

        except Exception as e:
            DatabaseLogger.Logger.log( "Error while parsing :: Executor.__getVersionSpecificQueriesName :: Error -> {} :: traceback - {}".format(e,traceback.print_exc()))
        return queries_to_execute

    # Generates JSON based on given tag
    def executeWithTag(self, instance_name,tag, connection, __version, disabled_queries,previousDC={}):
        try:
            __outputJSON,__rawOutputJSON = {}, {}
            if self.__parsedStructure.get(tag) == None:
                return None
            cursor  = connection.cursor()
            start_time_for_tag = time.time()
            if cursor:
                selectedQueries = self.__getVersionSpecificQueriesName(tag, __version, disabled_queries)
                for query in selectedQueries:
                    try:
                        #DatabaseLogger.Logger.log("tag - {} :: query_name - {}".format(tag,query))
                        # with connection.cursor() as cursor:
                        start_time  = time.time()
                        cursor.execute(self.__parsedStructure[tag][query]["Query"])
                        DatabaseLogger.Logger.log("{} :: Tag - {} :: Query Name - {} :: Time Taken - {:.4f} sec".format(instance_name,tag,query,time.time()-start_time),"QUERY")
                        __data = cursor.fetchall()
                        headers, format, KeyWithNone, res, counterMetrics = (
                            [],
                            self.__parsedStructure[tag][query].get("Format"),
                            self.__parsedStructure[tag][query].get("KeyWithNone"),
                            self.__parsedStructure[tag][query].get("Res"),
                            self.__parsedStructure[tag][query].get("CounterMetrics"),
                        )
                        plainQueryName = query.split("--")[0]
                        __outputJSON[plainQueryName] = {} if format else []

                        for _column in cursor.description:
                            if self.__parsedStructure[tag][query]["Col"].get(_column[0]):
                                headers.append(
                                    self.__parsedStructure[tag][query]["Col"][_column[0]]
                                )
                            else:
                                headers.append(_column[0])

                        formatter = self.__getFormatter(format)
                        for row in __data:
                            i, rowData = 0, {}
                            for i, header in enumerate(headers):
                                if row[i] == None and KeyWithNone == "False":
                                    continue
                                if type(row[i]) is decimal.Decimal:
                                    value = int(row[i])
                                elif type(row[i]) is datetime.datetime:
                                    value = row[i].ctime()
                                elif type(row[i]) is float:
                                    value = round(row[i],2)
                                else:
                                    value = row[i]
                                if res.get(header):
                                    value = (
                                        res[header][value] if res[header].get(value) else value
                                    )
                                rowData.update({header: value})
                            formatter(__outputJSON[plainQueryName], rowData)
                        
                        # DatabaseLogger.Logger.log("plain output - {}".format(__outputJSON[plainQueryName]))

                        if len(counterMetrics) <= 0:
                            continue
                        __format = format.split(",")
                        if __format[-1] != "[]" and __format[-1] != "":
                            _len_format = len(__format) - 1
                            __rawOutputJSON[plainQueryName] = copy.deepcopy(__outputJSON[plainQueryName])
                            self.computeRecursively(__outputJSON[plainQueryName],previousDC.get(plainQueryName),counterMetrics,_len_format if _len_format > 0 else 0)
                        # DatabaseLogger.Logger.log("calculated output - {}".format(__outputJSON[plainQueryName]))
                    except ExceptionClass as e:
                        if __outputJSON.get('ERROR') == None:
                            __outputJSON['ERROR']={'errors':[]}

                        if hasattr(e,"pgcode"):
                            # if e.pgcode in ['42501','25P02',"42P01"]:
                            try:
                                connection.reset()
                                cursor = connection.cursor()
                            except:
                                pass
                            DatabaseLogger.Logger.log("Error in postgres while executing query : {} error code : {} msg : {}".format(query,e.pgcode,e))
                            __outputJSON['ERROR']["errors"].append({"err_code":e.pgcode,"err_msg":e.pgerror,"query_name":query})
                        else:
                            DatabaseLogger.Logger.log("Error in while executing query : {} error msg : {}".format(query,e))
                            traceback.print_exc()
                            __outputJSON['ERROR']['errors'].append({"err_msg":str(e)})
                    except Exception as e:
                        if __outputJSON.get('ERROR') == None:
                            __outputJSON['ERROR']={'errors':[]}
                        DatabaseLogger.Logger.log("Error in while executing query : {} error msg : {}".format(query,e))
                        traceback.print_exc()
                        __outputJSON['ERROR']['errors'].append({"err_msg":str(e)})
                cursor.close()
            else:
                __outputJSON['ERROR'] = {'errors':[{'err_msg':"Cannot create cursor. There may be an issue in connection.","err_code":-1}]}
            DatabaseLogger.Logger.log("{} :: Total time taken to execute and parse - Tag Name - {} - {:.4f} sec".format(instance_name,tag,time.time()-start_time_for_tag),"QUERY")
            return __rawOutputJSON,__outputJSON
        except Exception as e:
            DatabaseLogger.Logger.log( "Error while executing sql :: executeWithTag ({}) :: Error -> {}".format(tag,e))
            return None,{"ERROR":{"errors":[{"err_msg":str(e)}]}}

    @staticmethod
    def __getFormatter(format):
        try:
            __format_len, isarr = 0, True
            if format:
                format = format.split(",")

                if format[-1] == "{}":
                    isarr = False
                    format.pop()
                __format_len = len(format)

            def simpleFormatArr(__temp, rowData):
                __temp.append(rowData)

            def simpleFormatObj(__temp, rowData):
                __temp.update(rowData)

            def redundant(__temp, rowData):
                for f in range(__format_len - 1):
                    if __temp.get(rowData[format[f]]) == None:
                        __temp[rowData[format[f]]] = {}
                    __temp = __temp[rowData[format[f]]]
                row_json = copy.deepcopy(rowData)
                for _f in format:
                    if row_json.get(_f):
                        row_json.pop(_f)
                return row_json, __temp

            def toValFormat(__temp, rowData):
                row_json, __temp = redundant(__temp, rowData)
                [key, value] = format[-1].split(":")
                __temp[rowData[key]] = row_json[value]

            def toObjFormat(__temp, rowData):
                row_json, __temp = redundant(__temp, rowData)
                if __temp.get(rowData[format[-1]]) == None:
                    __temp[rowData[format[-1]]] = row_json
                else:
                    __temp[rowData[format[-1]]].update(row_json)

            def toArrFormat(__temp, rowData):
                row_json, __temp = redundant(__temp, rowData)
                if __temp.get(rowData[format[-1]]) == None:
                    __temp[rowData[format[-1]]] = [row_json]
                else:
                    __temp[rowData[format[-1]]].append(row_json)

            if format:
                if format[-1].find(":") >= 0:
                    return toValFormat
                if isarr:
                    return toArrFormat
                else:
                    return toObjFormat
            if isarr:
                return simpleFormatArr
            return simpleFormatObj
        except Exception as e:
            DatabaseLogger.Logger.log( " class :: Executor.__getFormatter :: Error -> {}".format(e))
    
    def computeRecursively(self,newObj,oldObj,counterMetrics,level):
        try:
            if not newObj or not oldObj or level < 0:
                return
            if level == 0:
                for metric in counterMetrics:
                    if metric not in newObj:
                        continue
                    if metric in oldObj and newObj.get(metric) >= oldObj.get(metric) and newObj[metric] > 0:
                        newObj[metric] = newObj[metric] - oldObj[metric]
                    else:
                        if metric not in oldObj or newObj[metric]<0:
                            newObj.pop(metric)
            elif type(newObj) is dict:
                for metricName,metricValue in newObj.items():
                    self.computeRecursively(metricValue,oldObj.get(metricName),counterMetrics,level-1)
        except Exception as e:
            DatabaseLogger.Logger.log("class :: Executor.computeRecursively :: Error -> {}".format(e))
