import traceback

from com.manageengine.monagent.logger import AgentLogger
from com.manageengine.monagent.apps import persist_data
from com.manageengine.monagent import AgentConstants
from com.manageengine.monagent.util import AgentUtil

def collect_metrics():
    addm_dict = {}
    try:
        addm_dict.update(addm_data())
        addm_dict['ct'] = ct = str(AgentUtil.getTimeInMillis())
        filename = "_".join(["Agent",AgentUtil.AGENT_CONFIG.get('AGENT_INFO', 'agent_key'),"addm",ct]) + ".txt"
        persist_data.save(AgentConstants.AGENT_UPLOAD_PROPERTIES_MAPPER['015'], addm_dict, AgentLogger.STDOUT, filename)
        AgentLogger.log(AgentLogger.COLLECTOR, "ADDM datacollection completed and added to data directory")
        AgentLogger.log(AgentLogger.COLLECTOR, "ADDM data {}".format(addm_dict))
    except Exception as e:
        AgentLogger.log([AgentLogger.COLLECTOR,AgentLogger.STDERR],"*************************** Exception in collecting metrics for ADDM ***************************")
        traceback.print_exc()

def addm_data():
    result_json  =  {}
    try:
        executorObj = AgentUtil.Executor()
        
        executorObj.setCommand('netstat -antp')
        executorObj.execute_cmd_with_tmp_file_buffer()
        result_json['netstat'] = executorObj.getStdOut() if executorObj.isSuccess() else ''

        executorObj.setCommand('ifconfig')
        executorObj.execute_cmd_with_tmp_file_buffer()
        result_json['ifconfig'] = executorObj.getStdOut() if executorObj.isSuccess() else ''

        executorObj.setCommand('iproute')
        executorObj.execute_cmd_with_tmp_file_buffer()
        result_json['iproute'] = executorObj.getStdOut() if executorObj.isSuccess() else ''

        executorObj.setCommand('cat /etc/os-release')
        executorObj.execute_cmd_with_tmp_file_buffer()
        result_json['os_info'] = executorObj.getStdOut() if executorObj.isSuccess() else ''
        # Fetching the properties from seperate config file
        # result_json_string = json.dumps(result_json, indent=2)
        # current_time = round(time.time()*1000)
        # properties_file_path = 'addm.properties'
        # installed_path_key = 'INSTALLED_PATH'
        # properties = read_properties_file(properties_file_path)
        # if installed_path_key in properties:
        #     output_file_path = properties[installed_path_key]
        # output_file_path = output_file_path+'/S247ADDMOutput_'+str(current_time)+'.txt'  # Specify the desired file path
        # with open(output_file_path, 'w') as output_file:
        #     output_file.write(result_json_string)
    except Exception as e:
        AgentLogger.log([AgentLogger.COLLECTOR,AgentLogger.STDERR],"*************************** Exception in netstat_data for ADDM ***************************")
        traceback.print_exc()
    finally:
        return result_json


# def get_netstat_output():
#     # Run netstat command
#     return run_command(['netstat', '-antp'])

# def get_ifconfig_output():
#     # Run ifconfig command
#     return run_command(['ifconfig'])
    
# def get_iproute_output():
#     # Run iproute command
#     return run_command(['ip', 'route'])

# def get_os_info():
#     #Run cat etc/os-release
#     return run_command(['cat', '/etc/os-release'])

# def run_command(command):
#     try:
#         # Run the command and capture the output
#         result = subprocess.run(command, capture_output=True, text=True, check=True)
        
#         # Access the output as a string
#         output = result.stdout

#         return output
#     except subprocess.CalledProcessError as e:
#         # Handle the case where the command fails
#        AgentLogger.log([AgentLogger.STDOUT,AgentLogger.STDERR],"*************************** Exception in Netstat commands while collecting metrics for ADDM ] ***************************")
#        traceback.print_exc()
#        return None
       

# Fetching the properties from seperate config file
# def read_properties_file(file_path):
#     properties = {}

#     with open(file_path, 'r') as file:
#         for line in file:
#             line = line.strip()

#             # Ignore comments and empty lines
#             if not line or line.startswith('#') or line.startswith(';'):
#                 continue

#             # Split the line into key and value
#             key, value = map(str.strip, line.split('=', 1))

#             # Store the key-value pair in the properties dictionary
#             properties[key] = value

#     return properties