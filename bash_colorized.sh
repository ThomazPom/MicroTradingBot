#!/usr/bin/env bash
Black='\033[0;30m'
DarkGray='\033[1;30m'
Red='\033[0;31m'
LightRed='\033[1;31m'
Green='\033[0;32m'
LightGreen='\033[1;32m'
BrownOrange='\033[0;33m'
Yellow='\033[1;33m'
Blue='\033[0;34m'
LightBlue='\033[1;34m'
Purple='\033[0;35m'
LightPurple='\033[1;35]m'
Cyan='\033[0;36m'
LightCyan='\033[1;36m'
LightGray='\033[0;37m'
White='\033[1;37m'
NC='\033[0m'

info="${LightCyan}[info] "
warning="${Yellow}[warning]"
danger="${Red}[danger]"
erreur="${LightRed}[erreur]"
success="${Green}[success]"
OK="${LightGreen}[OK]"
executed="${BrownOrange}[executé]"

e () {
 if [ $# -gt  1 ]
 	then
 		prefix=$2
 	else
 		prefix=$info
 fi
 if [ $# -gt  2 ]
 	then
 		suffix=$3
 	else
 		suffix=$NC
 fi
 if [ $# -gt  3 ]
 	then
 		next=$4
 fi

 if [ $# -eq 0 ]
 	then

 		echo -e  "${Purple}--------------------------------------------------------------------------------${NC}"
 	else
 		echo -e  "\\n${prefix} ${suffix} ######## $1 ${next}"
 fi
 if [ $# -gt  3 ]
 	then
 		echo -e  "${suffix}--------------------------------------------------------------------------------${next}"
 fi
}

