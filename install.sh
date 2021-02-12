#!/usr/bin/env bash
source `dirname $0`/bash_colorized.sh
source `dirname $0`/bash_variables.sh


e "Installation de $APP_NAME" $info $LightBlue $NC

sudo apt-get install virtualenv;
virtualenv -p python3 $VENV_PATH$VENV_NAME --no-download;
. $VENV_PATH$VENV_NAME/bin/activate;


e "Installation avec PIP" $info $LightBlue $NC

pip install --upgrade -r "requirements.txt"

e "Version de python de l'installation :" $info $LightBlue $NC
python -V;
e "Fin d'Installation" $executed $LightBlue $NC
exit #Important : On quitte le VENV
