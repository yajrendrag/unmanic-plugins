#!/bin/bash

# Script is executed by the Unmanic container on startup to auto-install dependencies


ffspy=$(python3 -m pip list | grep ffsubsync)
if [ ! "$ffspy" ]; then 
    echo "**** Installing ffsubsync ****"
    python3 -m pip install ffsubsync
else
    echo "**** ffsubsync already installed ****"
fi
