import os
from zipfile import ZipFile, ZipInfo
from com.manageengine.monagent.logger import AgentLogger

class ZipManager(ZipFile):

    def extract(self, member, path=None, pwd=None):
        AgentLogger.log(AgentLogger.STDOUT,'ZipManager : extract : '+member)
        if not isinstance(member, ZipInfo):
            member = self.getinfo(member)

        if path is None:
            path = os.getcwd()

        ret_val = self._extract_member(member, path, pwd)
        attr = member.external_attr >> 16
        os.chmod(ret_val, attr)
        return ret_val
    
    def __enter__(self):
        AgentLogger.log(AgentLogger.STDOUT,'ZipManager : __enter__')
        return self

    def __exit__(self, type, value, traceback):
        AgentLogger.log(AgentLogger.STDOUT,'ZipManager : __exit__')
        self.close()