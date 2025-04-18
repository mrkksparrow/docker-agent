'''
Created on 29-July-2017

@author: giri
'''
from com.manageengine.monagent.framework.suite import activepool

OUTPUT_XML_PARENT_ENTITY = "DC"
METRICS_XML_ENTITY_TAG = "Metrics"
CMD_XML_ATTRIBUTE = "@cmd"
URL_XML_ATTRIBUTE = "@url"
ID_XML_ATTRIBUTE = "@id"
CATEGORY_XML_PATH = "Framework.DataCollection.Category"
S24X7_INVENTORY = "s24x7_inventory"
MONITOR_ID_XML_ATTRIBUTE = "@mid"
REGISTERED_APPS = activepool.RegisteredAppsActivePool()
LOGGER_DICT = {}

HADOOP_USER_NAME = None