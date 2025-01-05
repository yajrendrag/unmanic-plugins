#!/bin/bash

# Script is executed by the Unmanic container on startup to auto-install dependencies


ffspy=$(python3 -m pip list | grep ffsubsync)
if [ ! "$ffspy" ]; then 
    echo "**** Installing ffsubsync ****"
    python3 -m pip install ffsubsync
else
    echo "**** ffsubsync already installed ****"
fi

piso639=$(python3 -m pip list | grep python-iso639)
if [ ! "$piso639" ]; then
    echo "**** Installing python-iso639 ****"
    python3 -m pip install -U python-iso639
else
    echo "**** python-iso639 already installed ****"
fi
