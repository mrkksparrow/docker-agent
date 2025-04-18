import copy
import traceback
from types import MethodType

from prometheus_client.parser import text_string_to_metric_families
from com.manageengine.monagent.kubernetes import KubeUtil, KubeGlobal
from com.manageengine.monagent.kubernetes.Logging import KubeLogger as AgentLogger

def exception_handler(func):
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            AgentLogger.log(AgentLogger.KUBERNETES, "*** EXCEPTION *** => [PrometheusParserInterface] => {} => {} => {}".format(func.__name__, e, traceback.format_exc()))
    return wrapper


class PrometheusParser:
    @exception_handler
    def __init__(self, url, ksm_data=None):
        self.url = url
        self.status_code = None
        self.connection_error = False
        self.onchange_occurred = None
        self.raw_data = None
        # if not ksm data provided fetch data from url, else use provided ksm_data
        self.ksm_data = ksm_data
        self.final_data = {"DCErrors": {}}
        # by inheriting this parser class, write separate parser method for family that need unique parsing
        self.parser_config = {}
        # counter metric storage should be taken as copy, since same family can have multiple grouped dc collection
        self.prometheus_counter_storage = self.get_counter_cache_copy()
        # onchange data storage should be taken as copy, since same family can have multiple grouped dc collection
        self.metrics_onchange_storage = self.get_onchange_cache_copy()
        # function declaration for metrics types
        self.no_label_parser_method = {
            "counter": self.construct_CG_empty_label_metric,
            "gauge": self.construct_CG_empty_label_metric,
            "summary": self.construct_SH_empty_label_metric,
            "histogram": self.construct_SH_empty_label_metric
        }
        self.labeled_parser_method = {
            "counter": self.construct_CG_with_label_metric,
            "gauge": self.construct_CG_with_label_metric,
            "summary": self.construct_SH_with_label_metric,
            "histogram": self.construct_SH_with_label_metric
        }

    # creates copy of last counter metric cached data
    # if cache updated in the middle should not use updated data for present polling
    @exception_handler
    def get_counter_cache_copy(self):
        if self.url not in KubeGlobal.PROMETHEUS_COUNTER_DATA_STORAGE:
            KubeGlobal.PROMETHEUS_COUNTER_DATA_STORAGE[self.url] = {}
        return copy.deepcopy(KubeGlobal.PROMETHEUS_COUNTER_DATA_STORAGE[self.url])

    # creates copy of last onchange cached data
    # if cache updated in the middle should not use updated data for present polling
    @exception_handler
    def get_onchange_cache_copy(self):
        if self.url not in KubeGlobal.PROMETHEUS_ONCHANGE_DATA_STORAGE:
            KubeGlobal.PROMETHEUS_ONCHANGE_DATA_STORAGE[self.url] = {}
        return copy.deepcopy(KubeGlobal.PROMETHEUS_ONCHANGE_DATA_STORAGE[self.url])

    # sort the array/dictionary by asc/des order with top n objects
    @KubeUtil.exception_handler
    def get_top_n_data(self, data, sort_key, descending=True, topn=10):
        if type(data) == dict:
            return dict(sorted({k: v for k, v in data.items() if sort_key in v}.items(), key=lambda x: x[1][sort_key], reverse=descending)[:topn])
        elif type(data) == list:
            return sorted((item for item in data if sort_key in item), key=lambda x: x[sort_key], reverse=descending)[:topn]
        else:
            return data

    # return whether given family is with labels or not
    @exception_handler
    def check_labeled_metric(self, labels):
        return False if labels == {} or (labels and ("quantile" in labels or "le" in labels) and len(labels) < 2) else True

    @exception_handler
    def get_prometheus_data(self):
        if self.ksm_data is None:
            self.status_code, data = KubeUtil.curl_api_with_token(self.url, False)
            if self.status_code == 200:
                self.raw_data = list(text_string_to_metric_families(data))
            else:
                self.final_data["DCErrors"] = data
                self.connection_error = True
        else:
            if "conn_err" in self.ksm_data:
                self.final_data["DCErrors"] = self.ksm_data
                self.connection_error = True
            else:
                self.raw_data = list(text_string_to_metric_families(self.ksm_data))

    # creates a unique name to store the counter metric cache with all labels and metric short_name
    # can even add function to give unique prefix if needed
    @KubeUtil.exception_handler
    def get_unique_name(self, metric_config, prom_entry):
        unique_name = ""
        if "identifier" in metric_config:
            for label in metric_config["identifier"]: unique_name += prom_entry.labels[label]+"_"
        else:
            for label in prom_entry.labels: unique_name += prom_entry.labels[label]+"_"
        if str(prom_entry.name).endswith("_sum"):
            unique_name += "sum_"
        elif str(prom_entry.name).endswith("_count"):
            unique_name += "count_"
        unique_name += metric_config["short_name"]
        return unique_name

    # stores the current value in copied counter object and get value to return from last polled cache
    @exception_handler
    def get_counter_metric_value(self, unique_name, value):
        rate_value = 0
        self.prometheus_counter_storage[unique_name] = value
        if unique_name in KubeGlobal.PROMETHEUS_COUNTER_DATA_STORAGE[self.url]:
            rate_value = value - KubeGlobal.PROMETHEUS_COUNTER_DATA_STORAGE[self.url][unique_name]
        return round(rate_value, 2)

    # stores the current polling updated cache data in global object after finishing all parsing
    @exception_handler
    def update_counter_metric_value(self):
        KubeGlobal.PROMETHEUS_COUNTER_DATA_STORAGE[self.url] = self.prometheus_counter_storage

    # stores the current polling updated onchange cache data in global object after finishing all parsing
    @exception_handler
    def update_onchange_metric_value(self):
        KubeGlobal.PROMETHEUS_ONCHANGE_DATA_STORAGE[self.url] = self.metrics_onchange_storage


    # does arithmetic operation to the value of metric(*,/,+,-), and converts the type of value
    @exception_handler
    def convert_value(self, value, metric_config):
        value = eval(str(value)+str(metric_config["expression"])) if "expression" in metric_config else value
        value = metric_config["value_type"](value) if "value_type" in metric_config else value
        value = round(value, 2) if type(value) == float or "round_value" in metric_config else value
        return value

    # provides rate value for the histogram and summary metric by sum/count
    @exception_handler
    def get_SH_rate_value(self,sh_dict,metric_name):
        return round(float(sh_dict[metric_name+"S"]/sh_dict[metric_name+"C"]), 2) if (metric_name+"S" and metric_name+"C" in sh_dict) and (float(sh_dict[metric_name+"C"])) else 0

    # add the list of dicts value into one value with the short name "yyy" and store in result data with key "group_name"
    # sum_only (optional) option will only add the summed metric to final dict and ignores the rest
    @exception_handler
    def check_sum_data(self, metric_data, metric_config, metric_type=None):
        skip_list_data = False
        metric_list = None
        if type(metric_data) == dict:
            metric_list = list(metric_data.values())
        elif type(metric_data) == list:
            metric_list = metric_data
        if metric_list:
            sum_group_path = metric_config["sum"][0]
            metric_name = metric_config["sum"][1]
            if metric_type in ["summary", "histogram"]:
                metric_dict = {metric_name: 0, metric_name+"C": 0 , metric_name+"S": 0}
                for group_metric in metric_list:
                    metric_dict[metric_name+"S"] += group_metric[metric_config["short_name"]+"S"]
                    metric_dict[metric_name+"C"] += group_metric[metric_config["short_name"]+"C"]
                metric_dict[metric_name] = round(float(metric_dict[metric_name+"S"]/metric_dict[metric_name+"C"]), 2) if float(metric_dict[metric_name+"C"]) else 0
                metric_dict[metric_name+"S"] = round(metric_dict[metric_name+"S"],2)
                metric_dict[metric_name+"C"] = round(metric_dict[metric_name+"C"],2)
                metric_dict[metric_name] = round(metric_dict[metric_name],2)
            else:
                metric_dict = {metric_name: 0}
                for group_metric in metric_list:
                    metric_dict[metric_name] += round(group_metric[metric_config["short_name"]], 2)
            self.add_metric_to_final_data(metric_dict, sum_group_path)
            if "sum_only" in metric_config["sum"]:
                skip_list_data = True
        return skip_list_data

    # sample will be added to dc only when the value changes or first dc after agent restart, value will be stored in cache
    @KubeUtil.exception_handler
    def get_onchange_status(self, metric_config, entry):
        unique_name = metric_config["short_name"]+"_"
        for label in entry.labels: unique_name += entry.labels[label]+"_"
        if unique_name not in KubeGlobal.PROMETHEUS_ONCHANGE_DATA_STORAGE[self.url]:
            self.metrics_onchange_storage[unique_name] = entry.value
            self.onchange_occurred = True
        elif KubeGlobal.PROMETHEUS_ONCHANGE_DATA_STORAGE[self.url][unique_name] != entry.value:
            self.metrics_onchange_storage[unique_name] = entry.value
            self.onchange_occurred = True

    # sample will be added to dc only if the mentioned label matches its value
    @KubeUtil.exception_handler
    def get_match_label_value(self, metric_config, labels):
        bool_continue = False
        for label_name, label_value in metric_config["match_labels"].items():
            if labels[label_name] != label_value:
                bool_continue = True
        return bool_continue

    # will check the value of metric, and replace the value with label's value (3rd index provided) and add da if passes
    @KubeUtil.exception_handler
    def check_value_threshold(self, metric_config, value, labels):
        bool_continue = True
        operator = metric_config["value_threshold"][0]
        threshold_value = float(metric_config["value_threshold"][1])
        if operator == '=':
            bool_continue = (value == threshold_value)
        elif operator == '>':
            bool_continue = (value > threshold_value)
        elif operator == '<':
            bool_continue = (value < threshold_value)
        elif operator == '>=':
            bool_continue = (value >= threshold_value)
        elif operator == '<=':
            bool_continue = (value <= threshold_value)
        elif operator == '!=':
            bool_continue = (value != threshold_value)

        if bool_continue and len(metric_config["value_threshold"]) > 2 and metric_config["value_threshold"][2] in labels:
            value = labels[metric_config["value_threshold"][2]]
        return bool_continue,value

    # adds collected data to the final json
    # should not place dict value data and list value data in same group name
    # if group_name is "", place dict data on root of final json
    @exception_handler
    def add_metric_to_final_data(self, metric_data, group_name):
        if type(metric_data) is dict:
            if group_name == "":
                self.final_data.update(metric_data)
            else:
                if group_name not in self.final_data:
                    self.final_data[group_name] = metric_data
                elif group_name in self.final_data and type(self.final_data[group_name]) is dict:
                    for root_name, data_dict in metric_data.items():
                        if root_name in self.final_data[group_name]:
                            self.final_data[group_name][root_name].update(data_dict)
                        else:
                            self.final_data[group_name][root_name] = data_dict
                else:
                    AgentLogger.log(AgentLogger.KUBERNETES, "*** EXCEPTION *** => [add_metric_to_final_data] => cannot add dict data to existing list data => {}".format(self.final_data[group_name]))
        elif type(metric_data) is list:
            if group_name != "":
                if group_name not in self.final_data:
                    self.final_data[group_name] = metric_data
                elif group_name in self.final_data and type(self.final_data[group_name]) is list:
                    self.final_data[group_name].extend(metric_data)
                else:
                    AgentLogger.log(AgentLogger.KUBERNETES, "*** EXCEPTION *** => [add_metric_to_final_data] => cannot add list data to existing dict data => {}".format(self.final_data[group_name]))
            else:
                AgentLogger.log(AgentLogger.KUBERNETES, "*** EXCEPTION *** => [add_metric_to_final_data] => cannot add list data to root path => {}".format(metric_data))
        else:
            AgentLogger.log(AgentLogger.KUBERNETES, "*** EXCEPTION *** => [add_metric_to_final_data] => unknown data format => {}".format(metric_data))

    @exception_handler
    def construct_CG_empty_label_metric(self, family_list, metric_type, metric_config):
        metric_dict = {}
        for entry in family_list:
            value = entry.value
            if str(metric_type).lower() == "counter":
                value = self.get_counter_metric_value(metric_config["short_name"], value)
            value = self.convert_value(value, metric_config)
            metric_dict[metric_config["short_name"]] = value
        self.add_metric_to_final_data(metric_dict, metric_config["group_name"])

    @exception_handler
    def construct_SH_empty_label_metric(self, family_list, metric_type, metric_config):
        metric_dict = {}
        for entry in family_list:
            value = round(entry.value, 2)
            if str(entry.name).endswith("_sum"):
                unique_name = "sum_"+metric_config["short_name"]
                value = self.get_counter_metric_value(unique_name, value)
                metric_dict[metric_config["short_name"]+"S"] = round(value, 2)
            if str(entry.name).endswith("_count"):
                unique_name = "count_"+metric_config["short_name"]
                value = self.get_counter_metric_value(unique_name, value)
                metric_dict[metric_config["short_name"]+"C"]= value
        value = self.get_SH_rate_value(metric_dict,metric_config["short_name"])
        value = self.convert_value(value, metric_config)
        metric_dict[metric_config["short_name"]] = round(value, 2)
        self.add_metric_to_final_data(metric_dict, metric_config["group_name"])

    @exception_handler
    def construct_CG_with_label_metric(self, family_list, metric_type, metric_config):
        self.onchange_occurred = False if "onchange" in metric_config else None
        include_label     = metric_config["labels"] if "labels" in metric_config else {}
        group_entry_label = metric_config["group_labels"] if "group_labels" in metric_config else []
        parsed_cg_data    = {} if group_entry_label else []
        for entry in family_list:
            value = entry.value
            if "onchange" in metric_config:
                self.get_onchange_status(metric_config, entry)
            if "match_labels" in metric_config and self.get_match_label_value(metric_config, entry.labels):
                continue
            if "value_threshold" in metric_config:
                bool_continue, value = self.check_value_threshold(metric_config, value, entry.labels)
                if not bool_continue:
                    continue
            group_label_list = [entry.labels[label] for label in group_entry_label]
            if "" in group_label_list or None in group_label_list:
                continue
            metric_dict = {}
            group_label_key = "_".join(group_label_list)
            if str(metric_type).lower() == "counter":
                unique_name = self.get_unique_name(metric_config, entry)
                value = self.get_counter_metric_value(unique_name, value)
            value = self.convert_value(value, metric_config)
            if group_entry_label:
                if group_label_key not in parsed_cg_data:
                    for label in include_label: metric_dict[include_label[label]] = entry.labels[label]
                    metric_dict[metric_config["short_name"]] = value
                    parsed_cg_data[group_label_key] = metric_dict
                else:
                    parsed_cg_data[group_label_key][metric_config["short_name"]] += value
            else:
                for label in include_label: metric_dict[include_label[label]] = entry.labels[label]
                metric_dict[metric_config["short_name"]] = value
                parsed_cg_data.append(metric_dict)
        if "sum" in metric_config and self.check_sum_data(parsed_cg_data, metric_config, metric_type):
            return  #exit if only sum data is needed, else add sum data to json and continue to add list of parsed data
        if self.onchange_occurred in [True, None]:
            self.add_metric_to_final_data(parsed_cg_data, metric_config["group_name"])

    @exception_handler
    def construct_SH_with_label_metric(self, family_list, metric_type, metric_config):
        include_label     = metric_config["labels"] if "labels" in metric_config else {}
        group_entry_label = metric_config["group_labels"] if "group_labels" in metric_config else []
        parsed_sh_data    = {}
        for entry in family_list:
            value = round(entry.value, 2)
            metric_name = None
            if not (str(entry.name).endswith("_sum") or str(entry.name).endswith("_count")):
                continue
            if "match_labels" in metric_config and self.get_match_label_value(metric_config, entry.labels):
                continue
            if "value_threshold" in metric_config:
                bool_continue, value = self.check_value_threshold(metric_config, value, entry.labels)
                if not bool_continue:
                    continue
            if str(entry.name).endswith("_sum"):
                unique_name = self.get_unique_name(metric_config, entry)
                value = self.get_counter_metric_value(unique_name, value)
                value = round(value,2)
                metric_name = metric_config["short_name"]+"S"
            if str(entry.name).endswith("_count"):
                unique_name = self.get_unique_name(metric_config, entry)
                value = self.get_counter_metric_value(unique_name, value)
                value = round(value,metric_config["round_value"]) if "round_value" in metric_config else value
                metric_name = metric_config["short_name"]+"C"
            group_label_key = "_".join([entry.labels[label] for label in group_entry_label]) if group_entry_label else "_".join([entry.labels[label] for label in entry.labels])
            if group_label_key not in parsed_sh_data:
                metric_dict = {}
                for label in include_label: metric_dict[include_label[label]] = entry.labels[label]
                metric_dict[metric_name] = round(value, 2)
                parsed_sh_data[group_label_key] = metric_dict
            else:
                parsed_sh_data[group_label_key][metric_name] = round(value, 2) if metric_name not in parsed_sh_data[group_label_key] else round(parsed_sh_data[group_label_key][metric_name], 2) + round(value, 2)
        for grouped_label, metric_dict in parsed_sh_data.items():
            value = self.get_SH_rate_value(metric_dict,metric_config["short_name"])
            value = self.convert_value(value, metric_config)
            metric_dict[metric_config["short_name"]] = round(value, 2)
        if not group_entry_label:
            parsed_sh_data = list(parsed_sh_data.values())
        if "sum" in metric_config and self.check_sum_data(parsed_sh_data, metric_config, metric_type):
            return  #exit if only sum data is needed, else add sum data to json and continue to add list of parsed data
        self.add_metric_to_final_data(parsed_sh_data, metric_config["group_name"])

    @exception_handler
    def parse_data(self):
        if not self.connection_error:
            for family in self.raw_data:
                if family.name in self.parser_config and family.samples:
                    metric_family = family.name
                    family_list = family.samples
                    for family_parser_task in self.parser_config[metric_family]:
                        if isinstance(family_parser_task, MethodType):
                            family_parser_task(family_list)
                        else:
                            metric_type = family.type
                            if self.check_labeled_metric(family_list[0].labels):
                                self.labeled_parser_method[str(metric_type).lower()](family_list, metric_type, family_parser_task)
                            else:
                                self.no_label_parser_method[str(metric_type).lower()](family_list, metric_type, family_parser_task)

    @exception_handler
    def get_data(self):
        self.get_prometheus_data()
        self.parse_data()
        self.update_counter_metric_value()
        self.update_onchange_metric_value()


