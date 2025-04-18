LINUX_AGENT='linux'
WINDOWS_AGENT='windows'

MYSQL_DATABASE      =   'mysql'
POSTGRES_DATABASE   =   'postgres'
MYSQL_NDB_CLUSTER   =   'mysql_ndb'
ORACLE_DATABASE     =   'oracledb'

CONNECTION_FAILED_ERR_MSG = "Could not connect to database"
# --------------------------- MySQL NDB related constants starts ---------------------------

ClusterVersionCheckCommand          =   "mysql -V"
NDB_CHILD_NODES_PER_FILE            =   5
NDB_FILES_PER_ZIP                   =   10

    # Queries
NDBDiscoveryConectionStringQuery    =   "select variable_name,variable_value from performance_schema.global_variables where variable_name in ('ndb_connectstring','ndb_version_string')"
NDBDiscoverySystemNameQuery         =   "select lower(variable_name),variable_value from performance_schema.global_status where variable_name ='ndb_system_name'"
NDBChildDiscoveryQuery              =   "select concat(c.node_type,'-',c.node_id) as node_name,c.node_id,c.node_type,c.node_hostname,coalesce(p.node_version,'-') from ndbinfo.config_nodes c left outer join ndbinfo.processes p on p.node_id=c.node_id"
NDBDiscoveryCurrentAPINodeQuery     =   "select concat(node_type,'-',node_id) as node_name,node_hostname from ndbinfo.config_nodes where node_type = 'API'"
NDBClusterVersionCheckQuery         =   "select @@Version"

    # NDB Config 
NDBCONFIG                       =   None
NDB_SCHEDULE_OBJECT_MAPPER      =   {}
NDB_CID_MAPPER                  =   {}
NDB_REGISTRATION_TAKES_PLACE    =   None
NDB_DISCOVERY_SCHEDULE_INFO     =   None
# --------------------------- MySQL NDB related constants ends ---------------------------

# --------------------------- MySQL related constants starts ---------------------------

MYSQL_MONITOR_TYPE = "MYSQLDB"
MYSQL_CHILD_TYPE   = "MYSQL_DATABASE"

# --------------------------- MySQL related constants ends ---------------------------

# --------------------------- Postgres related constants starts ---------------------------
POSTGRES_MONITOR_TYPE                 =   "POSTGRESQL"
POSTGRES_CHILD_TYPE                   =   "POSTGRESQL_DATABASE"
POSTGRES_DATABASE_DISCOVERY_QUERY     =   "select datname from pg_stat_database where datname is not null and datname not in ('template1','template0')"

# --------------------------- Postgres related constants ends ---------------------------

# --------------------------- Oracle related constants starts ---------------------------

ORACLE_MONITOR_TYPE                 =   "ORACLE_DB"
ORACLE_CHILD_TYPE                   =   "ORACLE_PDB"
ORACLE_CHILD_TABLESPACE_TYPE        =   "ORACLE_TABLESPACE"
ORACLE_DATABASE_DISCOVERY_QUERY     =   "select name from v$pdbs where name not in ('PDB$SEED')"
ORACLE_TABLESPACES_DISCOVERY_QUERY  =   "select c.name container_name,t.name tablespace_name from v$tablespace t inner join v$containers c on (t.con_id=c.con_id) group by c.name,t.name order by c.name,t.name"
MAX_TABLESPACE_PER_DATABASE         =   200

# --------------------------- Oracle related constants ends ---------------------------

XML_EXECUTOR_OBJECTS            =   {"mysql_ndb":None,"postgres":None,"oracledb":None}