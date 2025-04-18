'''
Created on 03-Nov-2016
@author: giri
'''
import csv, re
from com.manageengine.monagent.remoteinstaller import TryDecorator,Constant,logutil
import configparser
import os
import traceback
from functools import partial
from configparser import DuplicateSectionError

logger = logutil.Logger('main')

def index_checker( value_list, index, input_name):
    try:
        input_value = value_list[index] if not index is None else None
    except IndexError as ie:
        input_value = None
    return input_value
        


def read_common_credentials_file():
    try:
        common_password, common_pem_file_path = None, None
        config = configparser.RawConfigParser()
        config.read(Constant.CONFIGURATION_FILE_PATH)
        if config.has_section('AUTHENTICATION'):
            common_password = config['AUTHENTICATION']['commonpassword'] if 'commonpassword' in config['AUTHENTICATION'] else None
            common_pem_file_path = config['AUTHENTICATION']['commonpemfilepath'] if 'commonpemfilepath' in config['AUTHENTICATION'] else None
            if common_password == '0':
                common_password = None
            if common_pem_file_path == '0':
                common_pem_file_path = None
    except Exception as e:
        traceback.print_exc()
    
    return common_password, common_pem_file_path
    
@TryDecorator.helper
def csv_to_configfile_convertor():
    is_header_present = False
    hostname_index, username_index, password_index, pemfile_path_index, displayname_index = None, None, None, None, None
    common_password, common_pem_file_path = read_common_credentials_file()
    config = configparser.RawConfigParser()
    with open(Constant.CSVFILE_PATH_TXT, 'r') as f:
        reader = csv.reader(f, skipinitialspace=True)
        for line in reader:
            if line and line[0].lower().startswith('#header'):
                matcher = re.match(r'\#[H|h]eader.*?:(?P<sectionname>.*)', line[0])
                if matcher:
                    line[0] = matcher.groupdict()['sectionname']
                    line = [l.strip() for l in line]
                    is_header_present = True
                    hostname_index = line.index("hostname") if "hostname" in line else None
                    username_index = line.index("username") if "username" in line else None
                    password_index = line.index("password") if "password" in line else None
                    pemfile_path_index = line.index("pemfile") if "pemfile" in line else None
                    displayname_index = line.index("displayname") if "displayname" in line else None
                    logger.info("host_index: "+str(hostname_index)+" username_index: "+str(username_index)+" password_index: "+str(password_index)+" pemfile_index: "+str(pemfile_path_index)+" displayname_index: "+str(displayname_index))
            elif not line or line[0].startswith("#"):
                continue
                     
            else:
                if is_header_present is False:
                    logger.info("ignoring this line since no header template is present before ------------> "+repr(line)+" Kindly add a header")
                    continue
                line = [l.strip() for l in line]
                hostname = partial(index_checker, line, hostname_index, "host name")()
                username = partial(index_checker, line, username_index, "username")()
                password = partial(index_checker, line, password_index, "password")()
                pemfile_path = partial(index_checker, line, pemfile_path_index, "pemfile")()
                displayname = partial(index_checker, line, displayname_index, "displayname")()
                if hostname and username and (pemfile_path or password or common_password or common_pem_file_path):
                    try:
                        config.add_section(hostname)
                    except DuplicateSectionError as de:
                        Constant.PRINT_SSH_DATA.append(hostname+" already present hence ignoring this entry")
                        continue
                    try:
                        config.set(line[hostname_index], 'username', username)
                        if not pemfile_path_index and password_index:
                            if password:
                                config.set(line[hostname_index], 'password', password)
                            else:
                                config.set(line[hostname_index], 'password', common_password)
                        elif not password_index and pemfile_path_index:
                            if pemfile_path:
                                config.set(line[hostname_index], 'pemfile', pemfile_path)
                            else:
                                config.set(line[hostname_index], 'pemfile', common_pem_file_path)
                        else:
                            if common_password:
                                config.set(line[hostname_index], 'password', common_password)
                            else:
                                config.set(line[hostname_index], 'pemfile', common_pem_file_path)
                        if displayname_index:
                            config.set(line[hostname_index], 'displayname', displayname)

                    except Exception as e:
                        traceback.print_exc()
                else:
                    if hostname:
                        Constant.PRINT_SSH_DATA.append("sufficient details not provided for host {}".format(hostname))
    with open(Constant.REMOTE_MACHINE_DETAILS_FILE_PATH, 'w') as  fp:
        config.write(fp)