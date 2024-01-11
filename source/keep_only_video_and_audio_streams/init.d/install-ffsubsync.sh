#!/bin/bash

# Script is executed by the Unmanic container on startup to auto-install dependencies

if ! command -v ffsubsync &> /dev/null; then
    echo "**** Installing ffsubsync ****"
    python3 -m pip install ffsubsync
else
    echo "**** ffsubsync already installed ****"
fi
