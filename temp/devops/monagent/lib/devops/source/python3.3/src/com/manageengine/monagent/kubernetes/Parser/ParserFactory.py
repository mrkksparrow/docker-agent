from com.manageengine.monagent.kubernetes.Parser.JSONParser.DaemonSets import DaemonSets
from com.manageengine.monagent.kubernetes.Parser.JSONParser.Namespaces import Namespaces
from com.manageengine.monagent.kubernetes.Parser.JSONParser.Deployments import Deployments
from com.manageengine.monagent.kubernetes.Parser.JSONParser.Jobs import Jobs
from com.manageengine.monagent.kubernetes.Parser.JSONParser.Services import Services
from com.manageengine.monagent.kubernetes.Parser.JSONParser.StatefulSets import StatefulSets
from com.manageengine.monagent.kubernetes.Parser.JSONParser.ResourceQuotas import ResourceQuota
from com.manageengine.monagent.kubernetes.Parser.JSONParser.Nodes import Nodes
from com.manageengine.monagent.kubernetes.Parser.JSONParser.Pods import Pods
from com.manageengine.monagent.kubernetes.Parser.JSONParser.KubeletData import KubeletMetrics
from com.manageengine.monagent.kubernetes.Parser.JSONParser.ReplicaSets import ReplicaSets
from com.manageengine.monagent.kubernetes.Parser.JSONParser.Ingresses import Ingresses
from com.manageengine.monagent.kubernetes.Parser.JSONParser.PV import PersistentVolume
from com.manageengine.monagent.kubernetes.Parser.JSONParser.PVC import PersistentVolumeClaim
from com.manageengine.monagent.kubernetes.Parser.JSONParser.HPA import HPA

from com.manageengine.monagent.kubernetes.Parser.PrometheusParser.CAdvisor import CAdvisor
from com.manageengine.monagent.kubernetes.Parser.PrometheusParser.NPCStateMetricsParser import NPCStateMetrics
from com.manageengine.monagent.kubernetes.Parser.PrometheusParser.ResourceDependencyMetricsParser import ResourceDependency


def get_json_parser(resource_type):
    if resource_type == "Nodes":
        return Nodes
    elif resource_type == "Pods":
        return Pods
    elif resource_type == "KubeletMetrics":
        return KubeletMetrics
    elif resource_type == "DaemonSets":
        return DaemonSets
    elif resource_type == "Deployments":
        return Deployments
    elif resource_type == "StatefulSets":
        return StatefulSets
    elif resource_type == "Namespaces":
        return Namespaces
    elif resource_type == "Jobs":
        return Jobs
    elif resource_type == "Services":
        return Services
    elif resource_type == "ResourceQuota":
        return ResourceQuota
    elif resource_type == "ReplicaSets":
        return ReplicaSets
    elif resource_type == "Ingresses":
        return Ingresses
    elif resource_type == "PV":
        return PersistentVolume
    elif resource_type == "PersistentVolumeClaim":
        return PersistentVolumeClaim
    elif resource_type == "HorizontalPodAutoscalers":
        return HPA


def get_prometheus_parser(resource_type):
    if resource_type == "CAdvisor":
        return CAdvisor
    elif resource_type == "NPCStateMetrics":
        return NPCStateMetrics
    elif resource_type == "ResourceDependency":
        return ResourceDependency
