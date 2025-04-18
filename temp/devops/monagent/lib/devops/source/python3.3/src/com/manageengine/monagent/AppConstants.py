#$Id$

namenode_app = 'hadoop_namenode'
datanode_app = 'hadoop_datanode'
yarn_app = 'hadoop_yarn'
zookeeper_app = 'zookeeper'
docker_app='docker'
app_conf_file_name = {'hadoop_namenode':'namenode.conf','hadoop_datanode':'datanode.conf','hadoop_yarn':'yarn.conf','zookeeper':'zookeeper.conf','docker':'docker.conf','kubernetes':'kubernetes.conf'}
app_metrics_conf_file_name = {'hadoop_namenode':'namenode.json','hadoop_datanode':'datanode.json','hadoop_yarn':'yarn.json'}
port_checker = {"hadoop_namenode":["9870","50070"],"hadoop_datanode":["50075","9868"],"hadoop_yarn":["8088"]}
app_checker = {'hadoop_namenode':"/jmx?qry=Hadoop:service=NameNode,name=NameNodeInfo","hadoop_datanode":"/jmx?qry=Hadoop:service=DataNode,name=DataNodeInfo","hadoop_yarn":"/cluster"}
docker_base_url = "unix://var/run/docker.sock"
podman_base_url = "unix://var/run/podman/podman.sock"
isPodmanPresent = False
skip_dc_for_nodes = []
hadoop_yarn_xml='yarn-site.xml'
hadoop_yarn_locate_xml='/etc/hadoop/yarn-site.xml'
hadoop_zk_xml='hdfs-site.xml'
hadoop_zk_locate_xml='/hadoop/etc/hadoop/hdfs-site.xml'
API_FAILURE='1000'
nn_state=None
app_vs_mids = {}
docker_client_cnxn_obj = None
APPS_CLASS_VS_METHOD={'hadoop':{'path':'com.manageengine.monagent.hadoop.hadoop_monitoring','method_name':'initialize'},
                      'zookeeper':{'path':'com.manageengine.monagent.hadoop.zookeeper_monitoring','method_name':'initialize'},
                      'docker': {'path':'com.manageengine.monagent.container.container_monitoring','method_name':'initialize'},
                      'kubernetes':{'path':'com.manageengine.monagent.kubernetes_monitoring.KubernetesExecutor','method_name':'schedule'}
                      }
APP_DISCOVERY_DATA_SIZE=40000
CONTAINER_DISCOVERY_INTERVAL = "1800"