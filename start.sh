#!/usr/bin/env bash
source `dirname $0`/bash_colorized.sh
source `dirname $0`/bash_variables.sh


if [ ! -d "$VENV_PATH$VENV_NAME" ]; then
  # install venv if $VENV_PATH$VENV_NAME does not exists.
   "$INSTALLER_PATH"
fi

e "Shell : Deemarrage de $APP_NAME" $info $LightBlue $NC
. $VENV_PATH$VENV_NAME/bin/activate;
e "Version de python de l'installation :" $info $LightBlue $NC
python -V;

e "Passage de python en UTF-8" $info $LightBlue $NC
export PYTHONIOENCODING="utf_8"
export PYTHONUTF8=1
export LC_ALL=C.UTF-8
export LANG=C.UTF-8

export filename=$1
if [ $# -lt 1 ];then
    filename=$DEFAULT_START
fi
e "Execution de $filename" $info $LightBlue $NC
    python `dirname $0`/"${filename//.py}.py"

exit #Important : On quitte le VENV
