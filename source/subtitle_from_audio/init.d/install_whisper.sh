#!/bin/bash

# Script is executed by the Unmanic container on startup to auto-install dependencies

if ! command -v whisper &> /dev/null; then
    echo "**** Installing whisper ****"
    python3 -m pip install -U openai-whisper
else
    echo "**** whisper already installed ****"
fi

lc=$(pip3 list | grep langcodes)
[[ ! $lc ]] && python3 -m pip install langcodes==3.5.0
