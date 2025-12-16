#!/bin/bash

# Script is executed by the Unmanic container on startup to auto-install dependencies

if ! command -v whisper &> /dev/null; then
    echo "**** Installing whisper ****"
    /opt/venv/bin/python3 -m pip install -U openai-whisper
else
    echo "**** whisper already installed ****"
fi

if ! /opt/venv/bin/python3 -c "import langcodes" > /dev/null 2>&1; then
    echo "langcodes module not found. Installing..."
    /opt/venv/bin/python3 -m pip install langcodes==3.5.0
fi
