'''
@author: bharath.veerakumar

Created on Feb 20 2023
'''


from datetime import datetime
import traceback
import sys, time

from com.manageengine.monagent.kubernetes.Logging import KubeLogger as AgentLogger
from com.manageengine.monagent.kubernetes import KubeGlobal
from com.manageengine.monagent.kubernetes.Collector.DataCollectorInterface import DataCollector

if 'com.manageengine.monagent.kubernetes.KubeUtil' in sys.modules:
    KubeUtil = sys.modules['com.manageengine.monagent.kubernetes.KubeUtil']
else:
    from com.manageengine.monagent.kubernetes import KubeUtil

BUFFER_LIMIT = 3000
lastRepTime = None
bufLen = 0


class EventCollector(DataCollector):
    def __init__(self, dc_requisites_obj):
        super().__init__(dc_requisites_obj)
        self.bufLen = 0
        self.final_json = []

    def collect_data(self):
        global lastRepTime, bufLen
        try:
            if KubeGlobal.EVENTS_ENABLED != "true":
                return

            start_time = datetime.strptime(str(datetime.now()), '%Y-%m-%d %H:%M:%S.%f')
            KubeUtil.get_api_data_by_limit(KubeGlobal.apiEndpoint + KubeGlobal.eventsListenerPath, self.eventsFilter, self.final_json)
            lastRepTime = start_time
        except Exception as e:
            AgentLogger.log(AgentLogger.KUBERNETES, 'Exception -> events collect_data -> {}'.format(e))
            traceback.print_exc()
        finally:
            bufLen = 0

    def get_data_for_cluster_agent(self, req_params=None):
        KubeGlobal.mid = req_params.get('mid', '')
        return super().get_data_for_cluster_agent()

    def get_cluster_agent_request_params(self):
        return {
            "mid": KubeGlobal.mid
        }

    def eventsFilter(self, events, final_data):
        global bufLen
        try:
            for event in events["items"]:
                if bufLen > BUFFER_LIMIT:
                    AgentLogger.log(AgentLogger.KUBERNETES, 'Exceeded Buffer Limit of Events {}')
                    break

                if self.isValidEvent(event):
                    event_dict = {}
                    self.eventParser(event_dict, event)
                    final_data.append(event_dict)
                    bufLen += 1
        except Exception as e:
            AgentLogger.log(AgentLogger.KUBERNETES, 'Exception while parsing the Events {}'.format(e))
            traceback.print_exc()

    @KubeUtil.exception_handler
    def eventParser(self, eveDict, event):
        if "creationTimestamp" in event["metadata"]:
            eveDict["EventTime"] = event["metadata"]["creationTimestamp"]
            if "deprecatedLastTimestamp" in event["metadata"]:
                eveDict["EventTime"] = event["metadata"]["deprecatedLastTimestamp"]

        if "regarding" in event:
            regDict = event["regarding"]
            if "kind" in regDict:
                eveDict["Kind"] = regDict["kind"]
            if "namespace" in regDict:
                eveDict["Namespace"] = regDict["namespace"]
            if "name" in regDict:
                eveDict["Name"] = regDict["name"]
            if "uid" in regDict:
                eveDict["Id"] = regDict["uid"]

        if "reason" in event:
            eveDict["Reason"] = event["reason"]
        if "note" in event:
            eveDict["Note"] = event["note"]
        if "type" in event:
            eveDict["Type"] = event["type"]
        if "deprecatedCount" in event:
            eveDict["deprecatedCount"] = event["deprecatedCount"]

        if "deprecatedSource" in event:
            source = ""
            if "component" in event["deprecatedSource"]:
                source += event["deprecatedSource"]["component"]
            if "host" in event["deprecatedSource"]:
                source += ", " + event["deprecatedSource"]["host"]
            eveDict["Source"] = source

        eveDict["_zl_timestamp"] = time.time() * 1000
        eveDict["s247agentuid"] = KubeGlobal.mid

    def isValidEvent(self, eventJson):
        try:
            if lastRepTime:
                eventTime = None
                if "deprecatedLastTimestamp" in eventJson:
                    eventTime = eventJson["deprecatedLastTimestamp"]    #for the updated events we take last updated time
                if not eventTime:
                    eventTime = eventJson["metadata"]["creationTimestamp"]

                eventTime = eventTime.replace('T', ' ').replace('Z', '.0000')     #converting TimeStamp to datetime
                eventTime = datetime.strptime(eventTime, '%Y-%m-%d %H:%M:%S.%f')

                if lastRepTime > eventTime:
                    return False

            return True
        except Exception as e:
            AgentLogger.log(AgentLogger.KUBERNETES, 'Exception in isValidEvent {}'.format(e))
            traceback.print_exc()
            return False

    @KubeUtil.exception_handler
    def split_data(self):
        for listChunks in KubeUtil.list_chunks(self.final_json, int(KubeGlobal.eventsWriteCount)):
            self.final_splitted_data.append({
                    "k8s_events": listChunks,
                    "upload_dir_code": self.dc_requisites_obj.servlet_name
            })
