'''
Created on 20-Oct-2016

@author: giri
'''

'''This python script executes remote installation on given machines as specified in servers.txt file'''

import paramiko, scp, select, re, time, sys, threading, argparse, socket
from com.manageengine.monagent.remoteinstaller import Constant,resultpool,logutil

import datetime
import dateutil.relativedelta
import itertools,shutil

def argumentbuilder():
    parser = argparse.ArgumentParser()
    parser.add_argument("a", nargs='?', default="check_string_for_empty")
    args = parser.parse_args()  
    if args.a == 'check_string_for_empty':
        sys.exit()
    Constant.AGENT_PARAMS = args.a

argumentbuilder()
import traceback, configparser
import os

if not os.path.exists(Constant.LOG_DIR_PATH):
    os.makedirs(Constant.LOG_DIR_PATH)

if not os.path.exists(os.path.join(Constant.LOG_DIR_PATH, str(Constant.AGENT_PARAMS))):
    os.makedirs(os.path.join(Constant.LOG_DIR_PATH, str(Constant.AGENT_PARAMS)))

Constant.LOG_FILE_PATH = os.path.join(Constant.LOG_DIR_PATH, str(Constant.AGENT_PARAMS), "remoteinstall.log")
#Constant.STDOUT_LOG_FILE_PATH = os.path.join(Constant.LOG_DIR_PATH, str(Constant.AGENT_PARAMS), "remoteinstall_stdout.log")
Constant.STDERR_LOG_FILE_PATH = os.path.join(Constant.LOG_DIR_PATH, str(Constant.AGENT_PARAMS), "remoteinstall_error.log")

logutil.register('main', Constant.LOG_FILE_PATH)
logger = logutil.Logger('main')
#logger.info('Initialized logger')

#logutil.register('stdout', Constant.STDOUT_LOG_FILE_PATH)
#stdout_logger = logutil.Logger('stdout')
#stdout_logger.info('Initialized stdout logger')

logutil.register('stderr', Constant.STDERR_LOG_FILE_PATH)
stderr_logger = logutil.Logger('stderr')
#stderr_logger.info('Initialized stderr logger')

import concurrent.futures
from com.manageengine.monagent.remoteinstaller import RequestHandler,RegexCacher,StreamtoLogfile,TryDecorator,CsvHelper,statusmonitor,singleinstance,print_handler
import json
from threading import Thread, current_thread
lock = threading.Lock()


@TryDecorator.helper
def prerequesties_handler():    
    
    '''checker for configuration.properties file'''
    if not os.path.exists(Constant.CONFIGURATION_FILE_PATH):
        logger.error("configuration.properties not present hence quitting")
        sys.exit()
    
    '''checker for servers.txt file'''
    if not os.path.exists(Constant.CSVFILE_PATH_TXT):
        logger.error("servers.txt file not found in installconfig folder hence quitting")
        sys.exit()

    '''checker for os_platform.sh file'''
    if not os.path.isfile(Constant.SCRIPTFILE_PATH):
        logger.error("os_platform.sh not found in scripts folder hence quitting")
        sys.exit()

class RemoteInstaller:
    def __init__(self, hostname, username, password, pemfile, displayname):
        self.hostname = hostname
        self.username = username
        self.password = password
        self.pemfile = pemfile
        self.displayname = displayname
        self.is_invalid_ssh_object = False
        self.installfile_path = None
        self.installfile_name = None
        self.os_checker_file_name = 'os_platform.sh'
        self.os_type = None
        self.is_root_user = None
        self.is_stdout_present = False
        self.stdout_lines = []
        self.stderr_lines = []
        self.error_log_path =  os.path.join(Constant.LOG_DIR_PATH, str(Constant.AGENT_PARAMS), self.hostname)
        self.error_log_file = os.path.join(self.error_log_path, "error.log")
        self.stdout_log_file = os.path.join(self.error_log_path, "stdout.log")
        self.private_key = None
        try:
            if not self.pemfile is None:              
                with lock:
                    try:
                        self.private_key = paramiko.RSAKey.from_private_key_file(self.pemfile)
                    except paramiko.SSHException as se:
                        logger.error("trying parsing as dsskey for host {}".format(self.hostname))
                        try:
                            self.private_key =  paramiko.DSSKey.from_private_key_file(self.pemfile)
                        except paramiko.SSHException as se:
                            logger.error("trying parsing as ecdsakey for host {}".format(self.hostname))
                            try:
                                self.private_key =  paramiko.ECDSAKey.from_private_key_file(self.pemfile)
                            except Exception as e:
                                pass                                
                    except Exception as e:
                        traceback.print_exc()
        except Exception as e:
            traceback.print_exc()
        self.ssh = None

    def ssh_connection_handler(self):
        try:
            self.ssh = paramiko.SSHClient()
            self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            if not self.password is None:
                self.ssh.connect(self.hostname, username = self.username, password = self.password, timeout=60)
            
            elif not self.private_key is None:
                self.ssh.connect(self.hostname, username = self.username, pkey=self.private_key)
            
            else:
                self.is_invalid_ssh_object = True
                logger.error("SSH Connection failed for host :"+self.hostname+'\n')
                Constant.RESULTPOOL_HANDLER.hold_result(self.hostname, "failed", "SSH Connection failed for host ")
                return
            
            logger.info("SSH - Connection Established Successfully for host :"+self.hostname+'\n')
        
        except paramiko.AuthenticationException as ae:
            self.is_invalid_ssh_object = True
            logger.error("SSH Connection failed for host :"+self.hostname+" |  error msg :"+str(ae)+'\n')
            Constant.RESULTPOOL_HANDLER.hold_result(self.hostname, "failed", "SSH Connection failed for host | "+str(ae))
        
        except paramiko.BadAuthenticationType as bae:
            self.is_invalid_ssh_object = True
            logger.error("SSH Connection failed for host :"+self.hostname+" |  error msg :"+str(bae)+'\n')
            Constant.RESULTPOOL_HANDLER.hold_result(self.hostname, "failed", "SSH Connection failed for host | "+str(bae))
        
        except paramiko.BadHostKeyException as bhe:
            self.is_invalid_ssh_object = True
            logger.error("SSH Connection failed for host :"+self.hostname+" |  error msg :"+str(bhe)+'\n')
            Constant.RESULTPOOL_HANDLER.hold_result(self.hostname, "failed", "SSH Connection failed for host | "+str(bhe))
        
        except paramiko.ChannelException as ce:
            self.is_invalid_ssh_object = True
            logger.error("SSH Connection failed for host :"+self.hostname+" |  error msg :"+str(ce)+'\n')
            Constant.RESULTPOOL_HANDLER.hold_result(self.hostname, "failed", "SSH Connection failed for host | "+str(ce))
        
        except paramiko.ProxyCommandFailure as pcf:
            self.is_invalid_ssh_object = True
            logger.error("SSH Connection failed for host :"+self.hostname+" |  error msg :"+str(pcf)+'\n')
            Constant.RESULTPOOL_HANDLER.hold_result(self.hostname, "failed", "SSH Connection failed for host | "+str(pcf))
            
        except paramiko.PasswordRequiredException as pre:
            self.is_invalid_ssh_object = True
            logger.error("SSH Connection failed for host :"+self.hostname+" |  error msg :"+str(pre)+'\n')
            Constant.RESULTPOOL_HANDLER.hold_result(self.hostname, "failed", "SSH Connection failed for host | "+str(pre))
            
        except paramiko.SSHException as se:
            self.is_invalid_ssh_object = True
            logger.error("SSH Connection failed for host :"+self.hostname+" |  error msg :"+str(se)+'\n')
            Constant.RESULTPOOL_HANDLER.hold_result(self.hostname, "failed", "SSH Connection failed for host | "+str(se))
        
        except Exception as e:
            self.is_invalid_ssh_object = True
            logger.error("SSH Connection failed for host :"+self.hostname+" |  error msg :"+str(e)+'\n')
            #Constant.RESULT_DICT[self.hostname]=str(e)
            Constant.RESULTPOOL_HANDLER.hold_result(self.hostname, "failed", "SSH Connection failed for host | "+str(e))
            #logger.error("Kindly check the user name and password information of the host "+self.hostname+'\n')

    def scp_script_handler(self):
        if not self.is_invalid_ssh_object is True:
            try:
                with scp.SCPClient(self.ssh.get_transport()) as self.scp_obj:
                    self.scp_obj.put(Constant.SCRIPTFILE_PATH, self.os_checker_file_name)
                    Constant.RESULTPOOL_HANDLER.del_host(self.hostname)
                    logger.info("OS checker Install File Copied Successfully to host :"+self.hostname+'\n')
                    return True
            except Exception as e:
                logger.error("SCP failed for host "+self.hostname+" "+str(e)+'\n')
                #Constant.RESULT_DICT[self.hostname]=str(e)
                Constant.RESULTPOOL_HANDLER.hold_result(self.hostname, "failed", str(e))
                return False
        else:
            return False

    def scp_connection_handler(self, retry = 0):
        if not self.installfile_path == "unsupported" or not self.installfile_path is None:
            try:
                with scp.SCPClient(self.ssh.get_transport()) as self.scp_handler:
                    self.scp_handler.put(self.installfile_path, self.installfile_name)
                    '''if self.hostname in Constant.RESULT_DICT:
                        del Constant.RESULT_DICT[self.hostname]'''
                    Constant.RESULTPOOL_HANDLER.del_host(self.hostname)
                    logger.info("SCP - Agent Install File Copied Successfully to host :"+self.hostname+'\n')
                    return True
            except Exception as e:
                if retry == 1:
                    logger.error("Problem with SCP for host "+self.hostname+" "+str(e)+'\n')
                    Constant.RESULTPOOL_HANDLER.hold_result(self.hostname, "failed", "Problem with SCP for host | "+str(e))
                return False
        else:
            return False
        
    def os_checker(self):
        try:
            '''dos2unix changes'''
            cmd = 'sed -i -e \'s/\\r$//\' os_platform.sh && bash os_platform.sh' if sys.platform == 'win32' else 'chmod 755 os_platform.sh && ./os_platform.sh'
            _, stdout, _ = self.ssh.exec_command(cmd)
            line = stdout.channel.recv(1024).decode("ISO-8859-1").strip()
            line = line.split('|')
            if line[0] == '64-bit':
                self.os_type = '64-bit'
                self.is_root_user = True if line[1] == '0' else False
                self.installfile_path = Constant.INSTALLFILE_64_BIT_PATH if not Constant.LOCAL_64BIT_INSTALLER_PATH else Constant.LOCAL_64BIT_INSTALLER_PATH
                self.installfile_name = Constant.INSTALLFILE_64_BIT_NAME 
            elif line[0] == '32-bit':
                self.os_type = '32-bit'
                self.is_root_user = True if line[1] == '0' else False
                self.installfile_path = Constant.INSTALLFILE_32_BIT_PATH if not Constant.LOCAL_32BIT_INSTALLER_PATH else Constant.LOCAL_32BIT_INSTALLER_PATH
                self.installfile_name = Constant.INSTALLFILE_32_BIT_NAME
            else:
                self.os_type = "unsupported"
                self.installfile_path = "unsupported"
                
        except Exception as e:
            logger.error("could not determine os bit version "+str(e))

    
    def download_install_file(self):
        if self.os_type == "unsupported" or (self.os_type == "64-bit" and Constant.IS_64BIT_DOWNLOADED is True) or (self.os_type == "32-bit" and Constant.IS_32BIT_DOWNLOADED is True):
            return
        with lock:
            if self.os_type == "64-bit" and Constant.IS_64BIT_DOWNLOADED is False:
                if RequestHandler.downloader(self.os_type) is True:
                    Constant.IS_64BIT_DOWNLOADED = True
                Constant.IS_64BIT_DOWNLOAD_ATTEMPT = True
            elif self.os_type == "32-bit" and Constant.IS_32BIT_DOWNLOADED is False:
                if RequestHandler.downloader(self.os_type) is True:
                    Constant.IS_32BIT_DOWNLOADED = True
                Constant.IS_32BIT_DOWNLOAD_ATTEMPT = True

    def run(self, pty=False, retry=0):
        try:
            if self.os_type == "unsupported":
                Constant.RESULTPOOL_HANDLER.hold_result(self.hostname, "failed", "OS type cannot be supported")
                return
            if not Constant.LOCAL_32BIT_INSTALLER_PATH and not Constant.LOCAL_64BIT_INSTALLER_PATH:
                self.download_install_file()
                if self.os_type == "64-bit" and Constant.IS_64BIT_DOWNLOAD_ATTEMPT is True and Constant.IS_64BIT_DOWNLOADED is False:
                    return
                elif self.os_type == "32-bit" and Constant.IS_32BIT_DOWNLOAD_ATTEMPT is True and Constant.IS_32BIT_DOWNLOADED is False:
                    return
            if not self.scp_connection_handler():
                time.sleep(0.2)
                self.installfile_name = self.installfile_name+str(Constant.CURRENT_MILLI_TIME())
                if not self.scp_connection_handler(retry = 1):
                    return
                
            if not Constant.HTTP_PROXY_URL is None:
                proxy_value = Constant.HTTP_PROXY_URL.lower().split("http://")[1]
                cmd = ' chmod 755 '+self.installfile_name+' && ./'+self.installfile_name+' '+Constant.INSTALL_PARAMS+' -installer='+Constant.REMOTE+' -proxy='+proxy_value
            else:
                cmd =' chmod 755 '+self.installfile_name+' &&  ./'+self.installfile_name+' '+Constant.INSTALL_PARAMS+' -installer='+Constant.REMOTE
            
            masked_install_param = re.sub(r'(-key=)(")\w+(")', r'\1!@#$%', Constant.INSTALL_PARAMS)
            logger.info('Install Params ::  '+ masked_install_param)
            
            if self.is_root_user is False:
                if self.password is None:
                    self.password = ''
                if not Constant.HTTP_PROXY_URL is None:
                    proxy_value = Constant.HTTP_PROXY_URL.lower().split("http://")[1]
                    if '-nr' in Constant.INSTALL_PARAMS:
                        cmd = ' chmod 755 '+self.installfile_name+' &&  ./'+self.installfile_name+' '+Constant.INSTALL_PARAMS+' -installer='+Constant.REMOTE+' -proxy='+proxy_value
                    else:
                        cmd = ' chmod 755 '+self.installfile_name+' &&  sudo ./'+self.installfile_name+' '+Constant.INSTALL_PARAMS+' -installer='+Constant.REMOTE+' -proxy='+proxy_value
                else:
                    if '-nr' in Constant.INSTALL_PARAMS:
                        cmd =' chmod 755 '+self.installfile_name+' && ./'+self.installfile_name+' '+Constant.INSTALL_PARAMS+' -installer='+Constant.REMOTE
                    else:
                        cmd =' chmod 755 '+self.installfile_name+' &&  sudo ./'+self.installfile_name+' '+Constant.INSTALL_PARAMS+' -installer='+Constant.REMOTE
                password = self.password.replace("$", "\$")
                password = password.replace("`", "\`")
                password = password.replace("&","\&")
                if '-nr' in Constant.INSTALL_PARAMS:
                    cmd = cmd
                else:
                    cmd = 'echo '+password+' | sudo -S'+cmd
            else:
                cmd = cmd
            
            if self.displayname:
                cmd = cmd + ' -dn='+self.displayname
            
            masked_cmd = re.sub('(key)(=)([^&]*)',r'\1\2!@#$%',cmd)
            #preventing logging of password
            if cmd.find('echo') >= 0:
                logger.info('Final cmd ::  '+ masked_cmd.replace(masked_cmd[masked_cmd.find('echo')+5:masked_cmd.find('|')-1],'!@#$%'))
            else:
                logger.info('Final cmd ::  '+ masked_cmd)
            
            try:
                if pty is False:
                    stdin, stdout, stderr = self.ssh.exec_command(cmd, timeout=60)
                else:
                    stdin, stdout, stderr = self.ssh.exec_command(cmd, get_pty=True, timeout=60)
                for line in stdout:
                    self.stdout_lines.append(line)
                    self.is_stdout_present = True
                    if RegexCacher.regex_map['root_user_check'].search(line):
                        logger.info('log in as root to install Site24x7 monitoring agent for host : '+self.hostname+"\n")
                        #Constant.RESULT_DICT[self.hostname]='failed, '+line
                        Constant.RESULTPOOL_HANDLER.hold_result(self.hostname, 'failed', line)
                        return
                    
                    elif RegexCacher.regex_map['uninstall'].search(line):
                        if Constant.FORCE_INSTALL == 'True':
                            logger.info('Agent Already Installed for host : '+self.hostname+" | "+'Force Install = True So Proceeding with Installation'+"\n")
                            #logger.info('force install enabled for host '+self.hostname+"\n")
                            stdin.write('y'+'\n')
                        else:
                            logger.info('Agent Already Installed for host : '+self.hostname+"\n")
                            #Constant.RESULT_DICT[self.hostname]='success, Agent Already Installed and force install disabled'
                            Constant.RESULTPOOL_HANDLER.hold_result(self.hostname, 'success', 'Agent Already Installed')
                            #logger.info('force install disabled for host ' + self.hostname+"\n")
                            stdin.write('n' + '\n')
                            return
                        
                    elif RegexCacher.regex_map['wrong_install'].search(line):
                        logger.info('Agent is already installed as root in the host : '+self.hostname+'hence, cannot proceed with non-root Installation'+"\n")
                        Constant.RESULTPOOL_HANDLER.hold_result(self.hostname, 'failed', 'Agent is already installed as root in the host')
                        return
                    
                    elif RegexCacher.regex_map['uninstallation'].search(line):
                        logger.info('Agent uninstalled successfully for the host : '+self.hostname+"\n")
                        Constant.RESULTPOOL_HANDLER.hold_result(self.hostname, 'success', line)
                        return
                    
                    elif RegexCacher.regex_map['usage'].search(line):
                        logger.error("agent param not correct hence failed "+self.hostname)
                        #Constant.RESULT_DICT[self.hostname]='failed, Installation param not correct '+Constant.INSTALL_PARAMS
                        Constant.RESULTPOOL_HANDLER.hold_result(self.hostname, 'failed', 'Installation param not correct: '+Constant.INSTALL_PARAMS)
                        return
                        
                    elif RegexCacher.regex_map['monagent'].search(line):
                        logger.info('agent successfully installed for host '+self.hostname+"\n")
                        #Constant.RESULT_DICT[self.hostname]='success, Agent Installation Successful '+line
                        Constant.RESULTPOOL_HANDLER.hold_result(self.hostname, 'success', line)
                        return
                        
                    elif RegexCacher.regex_map['watchdog'].search(line):
                        logger.info('watchdog successfully installed for host '+self.hostname+"\n")
                    
                    elif RegexCacher.regex_map['unsuccessful_1'].search(line):
                        logger.info('installation warning for host '+self.hostname+"\n")
                    
                    elif RegexCacher.regex_map['unsuccessful_2'].search(line):
                        #Constant.RESULT_DICT[self.hostname]='failed, '+line
                        Constant.RESULTPOOL_HANDLER.hold_result(self.hostname, 'failed', line)
                        logger.error('installation unsuccessful contact support for host '+self.hostname+"\n")
                        return
                    
                    elif RegexCacher.regex_map['exiting_installation'].search(line):
                        #Constant.RESULT_DICT[self.hostname]='success, '+line
                        Constant.RESULTPOOL_HANDLER.hold_result(self.hostname, 'success', line)
                        logger.info("Exiting agent installation for host "+self.hostname+"\n")
                        return                        
                    
                    elif RegexCacher.regex_map['watchdog_already_installed'].search(line):
                        logger.info("watchdog Agent already running for host "+self.hostname+"\n")                        
                        
                    elif RegexCacher.regex_map['monagent_already_installed'].search(line):
                        #Constant.RESULT_DICT[self.hostname]='success, '+line
                        Constant.RESULTPOOL_HANDLER.hold_result(self.hostname, 'success', line)
                        logger.info("Monagent already running for host " + self.hostname+"\n")
                        return
                time.sleep(2)        
                for line in stderr:
                    self.stderr_lines.append(line)
                    logger.error(line+" stderr line") 
                    if retry == 0 and "tty" in line.lower():
                        Constant.PRINT_SSH_DATA.append("Hostname - {} | Status - {} | Message - {}" .format(self.hostname, "retry", "tty cannot be detected"))
                        self.run(pty=True, retry=1)
                        return
                    
                if not self.is_stdout_present is True:
                    Constant.RESULTPOOL_HANDLER.hold_result(self.hostname, "failed", "cannot execute command may be no sudo permission for the user")
                    #Constant.RESULT_DICT[self.hostname] = "failed, may be wrong password for sudo command hence no installation"
                    logger.error('may be wrong password for sudo command hence no installation '+self.hostname+"\n")
                
                if not self.hostname in Constant.RESULTPOOL_HANDLER.result:
                    #Constant.RESULT_DICT[self.hostname]='failed'
                    if self.stdout_lines:
                        if not os.path.isdir(self.error_log_path):
                            os.mkdir(self.error_log_path)
                        with open(self.stdout_log_file, 'w') as fp:
                            for line in self.stdout_lines:
                                fp.write(line)
                        if self.stderr_lines:
                            with open(self.error_log_file, 'w') as fp:
                                for line in self.stderr_lines:
                                    fp.write(line)
                    Constant.RESULTPOOL_HANDLER.hold_result(self.hostname, "failed", "Contact support for this host")
                    logger.error("Unknown failed kindly contact support " + self.hostname+"\n")
                    return
            except socket.error as e:
                Constant.RESULTPOOL_HANDLER.hold_result(self.hostname, 'failed',  'ssh command timeout | '+repr(e))
                logger.error('SSH Command timeout for host {} | {}  '.format(self.hostname, repr(e)))
        except Exception as e:
            traceback.print_exc()
            #Constant.RESULT_DICT[self.hostname]='failed, installation problem in host, Exception'+repr(e)
            Constant.RESULTPOOL_HANDLER.hold_result(self.hostname, 'failed' , 'installation problem in host, Exception'+repr(e))
            logger.error('installation problem in host '+self.hostname+' '+repr(e))
            return


def read_conf_files():
    try:
        config = configparser.RawConfigParser()
        config.read(Constant.CONFIGURATION_FILE_PATH)
        if config.has_section('INSTALLATION'):
            Constant.FORCE_INSTALL = config['INSTALLATION']['force_install'] if 'force_install' in config['INSTALLATION'] else 'False'
            logger.info("force install status is "+Constant.FORCE_INSTALL)
            Constant.LOCAL_32BIT_INSTALLER_PATH = config['INSTALLATION'].get('local_32bit_installer_path', None)
            Constant.LOCAL_64BIT_INSTALLER_PATH = config['INSTALLATION'].get('local_64bit_installer_path', None)
            if Constant.LOCAL_32BIT_INSTALLER_PATH == '0': Constant.LOCAL_32BIT_INSTALLER_PATH = None
            if Constant.LOCAL_64BIT_INSTALLER_PATH == '0': Constant.LOCAL_64BIT_INSTALLER_PATH = None
            logger.info("Local installer path for 32bit: {} | 64bit: {} ".format(Constant.LOCAL_32BIT_INSTALLER_PATH, Constant.LOCAL_64BIT_INSTALLER_PATH))
        if config.has_section('AUTHENTICATION'):
            Constant.API_KEY = config['AUTHENTICATION']['devicekey'] if 'devicekey' in config['AUTHENTICATION'] else None
        if config.has_section('PARAMS'):
            Constant.INSTALL_PARAMS = config['PARAMS']['installparam'] if 'installparam' in config['PARAMS'] else None
        if Constant.API_KEY is None:
            logger.error("Device key not provided quitting")
            sys.exit()
        
        Constant.MONITORS_CONFIG = configparser.RawConfigParser()
        Constant.MONITORS_CONFIG.read(Constant.REMOTE_MACHINE_DETAILS_FILE_PATH)
        Constant.TOTAL_MONITORS = Constant.MONITORS_CONFIG.sections()
        print("Total number of servers configured for remote installation process is "+str(len(Constant.TOTAL_MONITORS)))
        with open(Constant.REMOTE_INSTALL_STATS, 'w') as fp:
            fp.write("Total number of servers configured for remote installation process is "+str(len(Constant.TOTAL_MONITORS)))
        logger.info("Total number of servers present for remote installation is {}".format(str(len(Constant.TOTAL_MONITORS))))
    except Exception as e:
        traceback.print_exc()
        logger.error("Problem while reading conf files hence quitting {} ".format(repr(e)))

def domainDecider():
    try:
        device_key = str(Constant.API_KEY)
        with open(Constant.SERVER_DOMAINS_FILE, 'r') as f:
            domains_dict = json.load(f)
        prefix = '_'.join(device_key.split('_')[:-1])
        if prefix in domains_dict.keys():
            Constant.STATIC_DOMAIN = domains_dict[prefix][3]
        else:
            logger.info("Device key prefix not found in server_domains.json")
        logger.info("Choosen Domain: "+ Constant.STATIC_DOMAIN)
    except:
        logger.error("Problem while changing domain")
        traceback.print_exc()


def remoteinstallation_executor():
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        for monitor in Constant.TOTAL_MONITORS:
            executor.submit(trigger, monitor, Constant.MONITORS_CONFIG)
            logger.info(monitor+' submitted as job')
    logger.info('final installation status - '+repr(json.dumps(Constant.RESULTPOOL_HANDLER.result)))
    writeDataToFile(Constant.INSTALLER_RESULT_FILE, Constant.RESULTPOOL_HANDLER.result)
    plus_server_handler()
    Constant.IS_REMOTEINSTALLATION_FINISHED = True

def trigger(monitor, config):
    try:
        username = config[monitor]['username'] 
        password = config[monitor]['password'] if 'password' in config[monitor] else None
        pemfile = config[monitor]['pemfile'] if 'pemfile' in config[monitor] else None
        displayname = config[monitor]['displayname'] if 'displayname' in config[monitor] else None
        if pemfile and not os.path.isfile(pemfile):
            logger.error(monitor+" failed | pemfile path not present {}".format(pemfile))
            Constant.RESULTPOOL_HANDLER.hold_result(monitor, "failed", "SSH Connection failed for host | pemfile path {} not present".format(pemfile))
            return
        remote_installer = RemoteInstaller(monitor, username, password, pemfile, displayname)
        with lock:
            remote_installer.ssh_connection_handler()
        if not remote_installer.scp_script_handler():
            time.sleep(0.2)
            remote_installer.os_checker_file_name = remote_installer.os_checker_file_name+str(Constant.CURRENT_MILLI_TIME())
            if not remote_installer.scp_script_handler():
                if not remote_installer.ssh is None:
                    remote_installer.ssh.close()
                del remote_installer
                return
            
        if remote_installer.is_invalid_ssh_object is False:
            remote_installer.os_checker()
            remote_installer.run()
                        
        if not remote_installer.ssh is None:
            remote_installer.ssh.close()
        del remote_installer
    
    except Exception as e:
        traceback.print_exc()

def redirect_stdout_stderr_to_file():
    sys.stderr = StreamtoLogfile.StreamToLogger(stderr_logger)
    #sys.stdout = StreamtoLogfile.StreamToLogger(stdout_logger)


def plus_server_handler():
    #make a post request to plus server
    RequestHandler.downloader(None, post_data=True)

def remoteinstallation_handler():
    _remote_installer = threading.Thread(name= 'REMOTEINSTALLER_EXECUTOR', target=remoteinstallation_executor)
    _remote_installer.setDaemon(True)
    logger.info('REMOTEINSTALLER_EXECUTOR THREAD IS SET AS DAEMON')
    _remote_installer.start()
    logger.info('REMOTEINSTALLER_EXECUTOR THREAD STARTED')

def thread_pool_handler():
    pass

def cleanup_directories():
    try:
        logger.info("--------------------------------------clean up directories invoked -------------------------------------------")
        if os.path.exists(Constant.PARENT_FOLDER+'/conf'):
            shutil.rmtree(Constant.PARENT_FOLDER+'/conf')
        if os.path.exists(Constant.PARENT_FOLDER+'/data'):
            shutil.rmtree(Constant.PARENT_FOLDER+'/data')
        if os.path.exists(Constant.PARENT_FOLDER+'/logs'):
            shutil.rmtree(Constant.PARENT_FOLDER+'/logs')
        if os.path.exists(Constant.PARENT_FOLDER+'/queryconf'):
            shutil.rmtree(Constant.PARENT_FOLDER+'/queryconf')
        if os.path.exists(Constant.PARENT_FOLDER+'/temp'):
            shutil.rmtree(Constant.PARENT_FOLDER+'/temp')
        if os.path.exists(Constant.PARENT_FOLDER+'/upgrade'):
            shutil.rmtree(Constant.PARENT_FOLDER+'/upgrade')
        if os.path.exists(Constant.PARENT_FOLDER+'/upload'):
            shutil.rmtree(Constant.PARENT_FOLDER+'/upload')
    except Exception as e:
        traceback.print_exc()

@TryDecorator.helper
def main():
    cleanup_directories()
    redirect_stdout_stderr_to_file()
    Constant.START_TIME = Constant.CURRENT_MILLI_TIME()
    running = statusmonitor.AgentStatus().calculate_agent_status()
    if not running:
        logger.info("--------------------------------------Site24x7 Remote Agent Installation Started -------------------------------------------")
        logger.info("Build Version : {}".format(Constant.BUILD_VERSION))
        with open(Constant.BUILD_VERSION_FILE, 'w') as fp:
            fp.write(Constant.BUILD_VERSION)
        if os.path.isfile(Constant.INSTALLER_RESULT_FILE):
            os.remove(Constant.INSTALLER_RESULT_FILE)
        if os.path.isfile(Constant.AGENT_ALREADY_RUNNING_FLAG_FILE):
            os.remove(Constant.AGENT_ALREADY_RUNNING_FLAG_FILE)
        if os.path.isfile(Constant.REMOTE_INSTALLER_HERATBEAT_FILE):
            os.remove(Constant.REMOTE_INSTALLER_HERATBEAT_FILE)
        if os.path.isfile(Constant.REMOTE_INSTALL_STATS):
            os.remove(Constant.REMOTE_INSTALL_STATS)
        singleInstance = singleinstance.SingleInstance()
        with open(Constant.AGENT_ALREADY_RUNNING_FLAG_FILE, 'w')as fp:
            fp.write(str(Constant.AGENT_PARAMS))
        prerequesties_handler()
        _print_data = threading.Thread(name= 'PRINT_DATA', target=print_handler.spinning_cursor)
        _print_data.setDaemon(True)
        logger.info('PRINT_DATA THREAD IS SET AS DAEMON')
        _print_data.start()
        CsvHelper.csv_to_configfile_convertor()
        read_conf_files()
        domainDecider()
        remoteinstallation_handler()
        while True:
            try:
                if Constant.IS_64BIT_DOWNLOAD_ATTEMPT is True and Constant.IS_64BIT_DOWNLOADED is False:
                    logger.error("unable to download 64bit install file hence quitting")
                    Constant.RESULTPOOL_HANDLER.hold_result("error", 'failed',"Unable to download 64bit install file hence quitting. Ensure connectivity to {} and try again".format(Constant.STATIC_64BIT_URL))
                    writeDataToFile(Constant.INSTALLER_RESULT_FILE,Constant.RESULTPOOL_HANDLER.result)
                    break
                elif Constant.IS_32BIT_DOWNLOAD_ATTEMPT is True and Constant.IS_32BIT_DOWNLOADED is False:
                    logger.error("unable to download 32bit install file hence quitting")
                    Constant.RESULTPOOL_HANDLER.hold_result("error", 'failed', "unable to download 32bit install file hence quitting. Ensure connectivity to {} and try again".format(Constant.STATIC_32BIT_URL))
                    writeDataToFile(Constant.INSTALLER_RESULT_FILE,Constant.RESULTPOOL_HANDLER.result)
                    break
                elif Constant.IS_REMOTEINSTALLATION_FINISHED is True:
                    dt1 = datetime.datetime.fromtimestamp(Constant.START_TIME/1000) 
                    dt2 = datetime.datetime.fromtimestamp(Constant.CURRENT_MILLI_TIME()/1000) 
                    rd = dateutil.relativedelta.relativedelta (dt2, dt1)
                    Constant.RESULTPOOL_HANDLER.print_summary()
                    logger.info("Remote Installer Using SSH finished successfully")
                    Constant.PRINT_SSH_DATA.append("Remote Installer Using SSH finished successfully ")
                    logger.info("Remote Installer Using SSH finished successfully total time taken for installing in {} servers is {} hrs {} mins {} sec".format(str(len(Constant.TOTAL_MONITORS)), str(rd.hours), str(rd.minutes), str(rd.seconds)))
                    Constant.PRINT_SSH_DATA.append("Remote Installer Using SSH finished successfully total time taken for installing in {} servers is {} hrs {} mins {} sec\n".format(str(len(Constant.TOTAL_MONITORS)),  str(rd.hours), str(rd.minutes), str(rd.seconds)))
                    Constant.PRINT_SSH_DATA.append("\nFor logs check logs/{}/ directory and for stats check results.txt file\n".format(str(Constant.AGENT_PARAMS)))        
                    break
                    
                with open(Constant.REMOTE_INSTALLER_HERATBEAT_FILE, 'w')as f:
                    f.write(str(Constant.CURRENT_MILLI_TIME()))    
                time.sleep(5)
            except KeyboardInterrupt:
                print ("Ctrl+C pressed hence quitting")
                sys.exit()
                
        while Constant.PRINT_SSH_DATA:
            time.sleep(1)
            continue
    else:
        logger.error("Site24x7 Remote Installer already running hence quitting")
        print("Site24x7 Remote Installer already running hence quitting")
        with open(Constant.AGENT_ALREADY_RUNNING_FLAG_FILE, 'w')as fp:
            fp.write("already running")
        
def writeDataToFile(str_fileName, dic_DataToWrite):
    file_obj = None
    try:
        file_obj = open(str_fileName,'w')
        json.dump(dic_DataToWrite, file_obj)        
    except:
        traceback.print_exc()
    finally:        
        if not file_obj == None:
            file_obj.close()

if __name__ == '__main__':
    main()

