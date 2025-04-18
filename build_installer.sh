#!/bin/bash

KUBERNETES_PROJECT=/home/kavin-11438/IdeaProjects/PresentWorkItem/Agent/kubernetes/source/python3.3/src/com/manageengine/monagent/kubernetes
PYTHON_AGENT_FRAMEWORK=/home/kavin-11438/IdeaProjects/PresentWorkItem/Agent/python_agent_framework/source/python3.3/src/com/manageengine/monagent/

SCRIPT_PATH=$(realpath "$0")
PROJECT_DIR=$(dirname "$SCRIPT_PATH")
INSTALL_FILE_LENGTH=$(head -n 100 "$PROJECT_DIR"/Site24x7MonitoringAgent.install | grep "INSTALL_FILE_LENGTH" | cut -d '=' -f2)
INSTALL_FILE_LENGTH=$((INSTALL_FILE_LENGTH - 1))

head -n $INSTALL_FILE_LENGTH "$PROJECT_DIR"/Site24x7MonitoringAgent.install > "$PROJECT_DIR"/Site24x7MonitoringAgent.install.1

TEMP_PROJECT_DIR=$PROJECT_DIR/temp/devops/monagent/lib/devops/source/python3.3/src/com/manageengine/monagent/
cp -rf $PYTHON_AGENT_FRAMEWORK $TEMP_PROJECT_DIR
cp -rf $KUBERNETES_PROJECT $TEMP_PROJECT_DIR

# shellcheck disable=SC2164
cd $PROJECT_DIR/../temp
tar -czvf devops.tar.gz -C devops .

cat devops.tar.gz >> "$PROJECT_DIR"/Site24x7MonitoringAgent.install.1
mv "$PROJECT_DIR"/Site24x7MonitoringAgent.install.1 "$PROJECT_DIR"/Site24x7MonitoringAgent.install

cd $PROJECT_DIR
git add Site24x7MonitoringAgent.install
git commit -m "added"

echo "=========> Pushing Changes to GitHub <========="
git push
