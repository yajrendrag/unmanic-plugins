#!/bin/bash

# Script is executed by the Unmanic container on startup to auto-install dependencies

if ! command -v apprise &> /dev/null; then
    echo "**** Installing apprise ****"
    python3 -m pip install apprise
else
    echo "**** apprise already installed ****"
fi
