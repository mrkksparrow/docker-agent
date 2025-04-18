'''
Created on 17-May-2024

@author: kavin
'''

import os
import sys
import platform
from cx_Freeze import setup, Executable


class SetupBuildConfig:
    def __init__(self):
        self.src_dir_path = None
        self.monagent_dir_path = None
        self.build_executable_path = None
        self.build_exe_options = None
        self.executables = None
        self.base = None
        self.set_agent_path()
        self.set_build_option()

    def set_agent_path(self):
        self.monagent_dir_path = os.path.dirname(os.path.realpath(sys.argv[0]))
        self.src_dir_path = os.path.dirname(os.path.dirname(os.path.dirname(self.monagent_dir_path)))
        if str(platform.machine()) in ["arm64", "aarch64", "ARM", "Arm", "aarch"]:
            self.build_executable_path = os.path.join(os.path.dirname(os.path.dirname(self.src_dir_path)), "build", "ME_AGENT", "pkg", "arm", "lib")
        else:
            self.build_executable_path = os.path.join(os.path.dirname(os.path.dirname(self.src_dir_path)), "build", "ME_AGENT", "pkg", "monagent", "lib") # "x86", "lib")

    def set_build_option(self):
        if platform.architecture()[0] == '32bit':
            self.build_exe_options = {
                'build_exe': self.build_executable_path,
                'path': sys.path + [self.src_dir_path],
                "packages" : ["idna","redis"]
            }
            self.executables = [
                Executable(os.path.join(self.monagent_dir_path, "MonitoringAgent.py"), targetName="Site24x7Agent", base=self.base),
                Executable(os.path.join(self.monagent_dir_path, "watchdog", "MonitoringAgentWatchdog.py"), targetName="Site24x7AgentWatchdog", base=self.base),
                Executable(os.path.join(self.monagent_dir_path, "metrics", "metrics_agent.py"), targetName="Site24x7MetricsAgent", base=self.base)
            ]
        else:
            self.build_exe_options = {
                'build_exe': self.build_executable_path,
                'path': sys.path + [self.src_dir_path],
                'bin_includes': ['/usr/lib64/libffi.so.6'],
                'include_files': ['/usr/local/lib/python3.11/site-packages/psycopg2_binary.libs'],
                'packages' : ['cryptography']
            }
            self.executables = [
                Executable(os.path.join(self.monagent_dir_path, "MonitoringAgent.py"), target_name="Site24x7Agent", base=self.base),
                Executable(os.path.join(self.monagent_dir_path, "watchdog", "MonitoringAgentWatchdog.py"), target_name="Site24x7AgentWatchdog", base=self.base),
                Executable(os.path.join(self.monagent_dir_path, "remoteinstaller", "LinuxRemoteInstaller.py"), target_name="Site24x7RemoteAgentInstaller", base=self.base),
                Executable(os.path.join(self.monagent_dir_path, "metrics", "metrics_agent.py"), target_name="Site24x7MetricsAgent", base=self.base)
            ]


setup_obj = SetupBuildConfig()
setup(name = 'Site24x7Agent',
      version = '1.0',
      author = 'Site24x7',
      author_email = 'site24x7plus@zohocorp.com',
      url = 'https://www.site24x7.com',
      options = {'build_exe' : setup_obj.build_exe_options},
      executables = setup_obj.executables)
