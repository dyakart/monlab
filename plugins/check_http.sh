#!/bin/bash
curl --connect-timeout 3 -3 http://$1 > /dev/null 2>&1
if [ "$?" -ne "0" ]; then
    # ERROR
    echo "0"
else
    # OK
    echo "1"
fi
