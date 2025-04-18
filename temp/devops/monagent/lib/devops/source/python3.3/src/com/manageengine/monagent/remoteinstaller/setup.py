'''
Created on 26-Oct-2016

@author: giri
'''
from cx_Freeze import setup, Executable
import sys
import platform
base = None
if sys.platform.startswith('linux'):
    base = None
    build_exe_options = {
                        'build_exe': 'remoteinstallation/lib',
                         "excludes": ["tkinter", "CompareFiles"],
                         "include_files": [ ("../installconfig/","../installconfig/"),("../scripts","../scripts")]
                        }
elif sys.platform.startswith('win32'):
    build_exe_options = {
                         'build_exe': 'remoteinstallation/lib',
                         "excludes": ["tkinter"],
                                                 "include_files": [ ("../conf/","../conf/"),("../install_files","../scripts")]}
    base = "Win32GUI"
setup(name = 'Site24x7RemoteInstaller',
      version = '1.0',
      author = 'Site24x7',
      author_email = 'site24x7plus@zohocorp.com',
      url = 'https://site24x7.manageengine.com',
      options = {'build_exe' : build_exe_options},
      executables = [Executable("LinuxRemoteInstaller.py", targetName="RemoteAgentInstaller", base=base, compress=True)]
      )
