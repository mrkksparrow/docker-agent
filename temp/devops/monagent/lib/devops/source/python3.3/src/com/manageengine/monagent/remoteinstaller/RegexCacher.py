'''
Created on 26-Oct-2016

@author: giri
'''
import re
regex_map = {'monagent' : re.compile("Site24x7 .*? agent service started success.*?(?P<pid>\d+?)\s*\)", re.IGNORECASE),
             'uninstall' : re.compile(".*? uninstall Site24x7 monitoring agent\s*\?\s*\(y\/n\)", re.IGNORECASE),
             'watchdog' : re.compile("Site24x7 .*? watchdog service started success.*?(?P<pid>\d+?)\s*\)", re.IGNORECASE),
             'exiting_installation' : re.compile("Exiting Site24x7 monitoring agent installation", re.IGNORECASE),
             'unsuccessful_1' : re.compile("WARNING", re.IGNORECASE),
             'unsuccessful_2': re.compile(".*?contact support", re.IGNORECASE),
             'monagent_already_installed':re.compile(".*? monitoring agent is already running.*?(?P<pid>\d+?)\s*\)", re.IGNORECASE),
             'watchdog_already_installed':re.compile(".*? monitoring agent watchdog is already running.*?(?P<pid>\d+?)\s*\)", re.IGNORECASE),
             'root_user_check':re.compile(".*? log in as root to install Site24x7 monitoring agent.*", re.IGNORECASE),        
             'usage':re.compile("Usage :", re.IGNORECASE),
             'wrong_install':re.compile(".*?Uninstall the agent which is installed as root.*?", re.IGNORECASE), #trying to install nonroot agent when there is a root agent
             'uninstallation':re.compile("Site24x7 monitoring agent uninstalled successfully", re.IGNORECASE) #using for direct uninstallation not when installing
             }
