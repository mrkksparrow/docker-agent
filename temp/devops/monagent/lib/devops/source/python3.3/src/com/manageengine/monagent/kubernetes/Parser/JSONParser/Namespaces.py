from com.manageengine.monagent.kubernetes.Parser.JSONParserInterface import JSONParser


class Namespaces(JSONParser):
    def __init__(self):
        super().__init__('Namespaces')
        self.is_namespaces = False

    def get_metadata(self):
        super().get_metadata()
        self.value_dict["Fi"] = ",".join(self.get_2nd_path_value(['spec', 'finalizers']))
        self.value_dict["Ph"] = self.get_2nd_path_value(['status', 'phase'])
