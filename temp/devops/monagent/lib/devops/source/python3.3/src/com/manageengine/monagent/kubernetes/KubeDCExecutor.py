import time
import traceback
import os
import sys

from com.manageengine.monagent.kubernetes.Collector.NPCDataCollector import NPCDataCollector
from com.manageengine.monagent.kubernetes.Collector.ClusterWorkloadsDataCollector import WorkloadsDataCollector
from com.manageengine.monagent.kubernetes.Collector.EventCollector import EventCollector
from com.manageengine.monagent.kubernetes.Collector.ResourceDependencyCollector import ResourceDependency
from com.manageengine.monagent.kubernetes.Collector.APIServerDataCollector import APIServerDataCollector
from com.manageengine.monagent.kubernetes.Collector.ControllerManagerDataCollector import ControllerManagerDataCollector
from com.manageengine.monagent.kubernetes.Collector.InstantDiscoveryDataCollector import InstantDiscoveryDataCollector
from com.manageengine.monagent.kubernetes.Collector.ClusterMetricsAggregator import ClusterMetricsAggregator
from com.manageengine.monagent.kubernetes.Collector.MetricsServerAggregator import MetricsServerAggregator
from com.manageengine.monagent.kubernetes.Collector.SidecarNPCCollector import SidecarNPCCollector
from com.manageengine.monagent.kubernetes.Collector.GuidanceMetrics import GuidanceMetrics
from com.manageengine.monagent.kubernetes.Collector.ServerTerminationTask import ServerTerminationTask
from com.manageengine.monagent.kubernetes.Collector.DataCollectorInterface import DCRequisites
from com.manageengine.monagent.kubernetes import KubeGlobal, KubeUtil
from com.manageengine.monagent.kubernetes.Logging import KubeLogger
from com.manageengine.monagent.kubernetes.Collector.YAMLFetcher import YAMLFetcher
from com.manageengine.monagent.kubernetes.Collector.KubeProxyMetricCollector import KubeProxyMetricCollector

if 'com.manageengine.monagent.kubernetes.SettingsHandler.Initializer' in sys.modules:
    Initializer = sys.modules['com.manageengine.monagent.kubernetes.SettingsHandler.Initializer']
else:
    from com.manageengine.monagent.kubernetes.SettingsHandler import Initializer


DC_OBJ_LIST = []


def init():
    try:
        Initializer.init()
    except Exception:
        traceback.print_exc()


def create_dc_objs():
    if os.environ.get("SIDECAR_AGENT") == "true":
        create_sidecar_agent_dc_objs()
    elif KubeUtil.is_conf_agent():
        create_conf_agent_dc_objs()
    else:
        create_perf_agent_dc_objs()


@KubeUtil.pre_dc_init
def execute_tasks():
    global DC_OBJ_LIST
    final_json = []
    try:
        KubeLogger.log(KubeLogger.KUBERNETES, '\n')
        KubeLogger.log(KubeLogger.KUBERNETES, 'Executing DC tasks !!!')
        KubeGlobal.DC_START_TIME = time.time()
        final_json = execute_dc_tasks()
        KubeLogger.log(KubeLogger.KUBERNETES, 'End of DC tasks execution!!!\n')
    except Exception:
        traceback.print_exc()
    return final_json


def execute_dc_tasks():
    final_json = []

    for dc_prerequest in DC_OBJ_LIST:
        final_json.extend(dc_prerequest.dc_class(dc_prerequest).execute_dc_tasks())
    return final_json

def create_perf_agent_dc_objs():
    global DC_OBJ_LIST
    DC_OBJ_LIST = []
    dc_requisites_obj = DCRequisites()
    dc_requisites_obj.set_dc_name(InstantDiscoveryDataCollector.__name__.lower())
    dc_requisites_obj.set_servlet_name("018")
    dc_requisites_obj.set_child_write_count(5)
    dc_requisites_obj.set_split_data_required(True)
    dc_requisites_obj.set_instant_push_needed(True)
    dc_requisites_obj.set_dc_class(InstantDiscoveryDataCollector)
    DC_OBJ_LIST.append(dc_requisites_obj)

    dc_requisites_obj = DCRequisites()
    dc_requisites_obj.set_dc_name(NPCDataCollector.__name__.lower())
    dc_requisites_obj.set_termination_needed(True)
    dc_requisites_obj.set_dc_type_needed(True)
    dc_requisites_obj.set_child_write_count(int(KubeGlobal.childWriteCount))
    dc_requisites_obj.set_split_data_required(True)
    dc_requisites_obj.set_id_mapping_needed(True)
    dc_requisites_obj.set_dc_class(NPCDataCollector)
    dc_requisites_obj.set_instant_push_needed(True)
    dc_requisites_obj.set_child_task_classes(get_perf_agent_child_tasks())
    DC_OBJ_LIST.append(dc_requisites_obj)

    dc_requisites_obj = DCRequisites()
    dc_requisites_obj.set_dc_name(APIServerDataCollector.__name__.lower())
    dc_requisites_obj.set_child_write_count(1000)
    dc_requisites_obj.set_split_data_required(True)
    dc_requisites_obj.set_id_mapping_needed(False)
    dc_requisites_obj.set_dc_class(APIServerDataCollector)
    DC_OBJ_LIST.append(dc_requisites_obj)

    dc_requisites_obj = DCRequisites()
    dc_requisites_obj.set_dc_name(KubeProxyMetricCollector.__name__.lower())
    dc_requisites_obj.set_split_data_required(True)
    dc_requisites_obj.set_dc_class(KubeProxyMetricCollector)
    DC_OBJ_LIST.append(dc_requisites_obj)


def create_conf_agent_dc_objs():
    global DC_OBJ_LIST
    DC_OBJ_LIST = []
    dc_requisites_obj = DCRequisites()
    dc_requisites_obj.set_dc_name(InstantDiscoveryDataCollector.__name__.lower())
    dc_requisites_obj.set_child_write_count(5)
    dc_requisites_obj.set_servlet_name("018")
    dc_requisites_obj.set_split_data_required(True)
    dc_requisites_obj.get_from_cluster_agent(True)
    dc_requisites_obj.set_instant_push_needed(True)
    dc_requisites_obj.set_cluster_req_type("POST")
    dc_requisites_obj.set_dc_class(InstantDiscoveryDataCollector)
    DC_OBJ_LIST.append(dc_requisites_obj)

    dc_requisites_obj = DCRequisites()
    dc_requisites_obj.set_dc_name(NPCDataCollector.__name__.lower())
    dc_requisites_obj.set_dc_type_needed(True)
    dc_requisites_obj.set_child_write_count(int(KubeGlobal.childWriteCount))
    dc_requisites_obj.set_split_data_required(True)
    dc_requisites_obj.set_id_mapping_needed(True)
    dc_requisites_obj.set_instant_push_needed(True)
    dc_requisites_obj.set_dc_class(NPCDataCollector)
    DC_OBJ_LIST.append(dc_requisites_obj)

    dc_requisites_obj = DCRequisites()
    dc_requisites_obj.set_dc_name(WorkloadsDataCollector.__name__.lower())
    dc_requisites_obj.set_dc_type_needed(True)
    dc_requisites_obj.set_termination_needed(True)
    dc_requisites_obj.set_child_write_count(int(KubeGlobal.childWriteCount))
    dc_requisites_obj.set_split_data_required(True)
    dc_requisites_obj.set_id_mapping_needed(True)
    dc_requisites_obj.get_from_cluster_agent(True)
    dc_requisites_obj.set_instant_push_needed(True)
    dc_requisites_obj.set_dc_class(WorkloadsDataCollector)
    dc_requisites_obj.set_child_task_classes(get_conf_agent_child_tasks())
    DC_OBJ_LIST.append(dc_requisites_obj)

    dc_requisites_obj = DCRequisites()
    dc_requisites_obj.set_dc_name(APIServerDataCollector.__name__.lower())
    dc_requisites_obj.set_child_write_count(1000)
    dc_requisites_obj.set_split_data_required(True)
    dc_requisites_obj.set_id_mapping_needed(False)
    dc_requisites_obj.set_dc_class(APIServerDataCollector)
    DC_OBJ_LIST.append(dc_requisites_obj)

    dc_requisites_obj = DCRequisites()
    dc_requisites_obj.set_dc_name(ControllerManagerDataCollector.__name__.lower())
    dc_requisites_obj.set_child_write_count(1000)
    dc_requisites_obj.set_split_data_required(True)
    dc_requisites_obj.set_id_mapping_needed(False)
    dc_requisites_obj.set_dc_class(ControllerManagerDataCollector)
    DC_OBJ_LIST.append(dc_requisites_obj)

    dc_requisites_obj = DCRequisites()
    dc_requisites_obj.set_dc_name(EventCollector.__name__.lower())
    dc_requisites_obj.set_child_write_count(int(KubeGlobal.eventsWriteCount))
    dc_requisites_obj.set_dc_class(EventCollector)
    dc_requisites_obj.set_split_data_required(True)
    dc_requisites_obj.get_from_cluster_agent(True)
    DC_OBJ_LIST.append(dc_requisites_obj)

    dc_requisites_obj = DCRequisites()
    dc_requisites_obj.set_dc_name(KubeProxyMetricCollector.__name__.lower())
    dc_requisites_obj.set_split_data_required(True)
    dc_requisites_obj.set_dc_class(KubeProxyMetricCollector)
    DC_OBJ_LIST.append(dc_requisites_obj)

    dc_requisites_obj = DCRequisites()
    dc_requisites_obj.set_dc_name(YAMLFetcher.__name__.lower())
    dc_requisites_obj.set_child_write_count(70)
    dc_requisites_obj.set_dc_class(YAMLFetcher)
    dc_requisites_obj.set_servlet_name("020")
    dc_requisites_obj.set_instant_push_needed(True)
    dc_requisites_obj.set_split_data_required(True)
    dc_requisites_obj.get_from_cluster_agent(True)
    dc_requisites_obj.set_cluster_req_type("POST")
    DC_OBJ_LIST.append(dc_requisites_obj)

    dc_requisites_obj = DCRequisites()
    dc_requisites_obj.set_dc_name(ServerTerminationTask.__name__.lower())
    dc_requisites_obj.set_split_data_required(True)
    dc_requisites_obj.get_from_cluster_agent(True)
    dc_requisites_obj.set_dc_class(ServerTerminationTask)
    DC_OBJ_LIST.append(dc_requisites_obj)

    dc_requisites_obj = DCRequisites()
    dc_requisites_obj.set_dc_name(ResourceDependency.__name__.lower())
    dc_requisites_obj.set_child_write_count(1000)
    dc_requisites_obj.set_servlet_name("017")
    dc_requisites_obj.set_dc_class(ResourceDependency)
    dc_requisites_obj.set_cluster_req_type("POST")
    dc_requisites_obj.set_split_data_required(True)
    dc_requisites_obj.get_from_cluster_agent(True)
    DC_OBJ_LIST.append(dc_requisites_obj)


def create_sidecar_agent_dc_objs():
    global DC_OBJ_LIST
    DC_OBJ_LIST = []
    dc_requisites_obj = DCRequisites()
    dc_requisites_obj.set_dc_name(SidecarNPCCollector.__name__.lower())
    dc_requisites_obj.set_dc_type_needed(True)
    dc_requisites_obj.set_child_write_count(int(KubeGlobal.childWriteCount))
    dc_requisites_obj.set_termination_needed(True)
    dc_requisites_obj.set_id_mapping_needed(True)
    dc_requisites_obj.set_node_base_ksm_needed(True)
    dc_requisites_obj.set_is_sidecar_agent(True)
    dc_requisites_obj.set_split_data_required(True)
    dc_requisites_obj.set_child_task_classes(get_sidecar_agent_child_tasks() if KubeUtil.is_conf_agent() else None)
    dc_requisites_obj.set_dc_class(SidecarNPCCollector)
    DC_OBJ_LIST.append(dc_requisites_obj)


def get_sidecar_agent_child_tasks():
    dc_list = []
    dc_requisites_obj = DCRequisites()
    dc_requisites_obj.set_dc_name(ClusterMetricsAggregator.__name__.lower())
    dc_requisites_obj.set_dc_class(ClusterMetricsAggregator)
    dc_requisites_obj.set_workloads_aggregation_needed(False)
    dc_list.append(dc_requisites_obj)

    return dc_list


def get_conf_agent_child_tasks():
    dc_list = []
    dc_requisites_obj = DCRequisites()
    dc_requisites_obj.set_dc_name(ClusterMetricsAggregator.__name__.lower())
    dc_requisites_obj.get_from_cluster_agent(True)
    dc_requisites_obj.set_dc_class(ClusterMetricsAggregator)
    dc_list.append(dc_requisites_obj)

    dc_requisites_obj = DCRequisites()
    dc_requisites_obj.set_dc_name(GuidanceMetrics.__name__.lower())
    dc_requisites_obj.set_dc_class(GuidanceMetrics)
    dc_requisites_obj.get_from_cluster_agent(True)
    dc_list.append(dc_requisites_obj)

    dc_requisites_obj = DCRequisites()
    dc_requisites_obj.set_dc_name(MetricsServerAggregator.__name__.lower())
    dc_requisites_obj.set_dc_class(MetricsServerAggregator)
    dc_requisites_obj.get_from_cluster_agent(True)
    dc_list.append(dc_requisites_obj)
    return dc_list


def get_perf_agent_child_tasks():
    dc_list = []
    dc_requisites_obj = DCRequisites()
    dc_requisites_obj.set_dc_name(GuidanceMetrics.__name__.lower())
    dc_requisites_obj.set_dc_class(GuidanceMetrics)
    dc_requisites_obj.get_from_cluster_agent(False)
    dc_list.append(dc_requisites_obj)

    return dc_list
