#!/bin/bash

# Script is executed by the Unmanic container on startup to auto-install dependencies

if ! command -v whisper &> /dev/null; then
    echo "**** Installing whisper ****"
    python3 -m pip install -U openai-whisper
else
    echo "**** whisper already installed ****"
fi

mpy=$(python3 -m pip list | grep moviepy)
if [ ! "$mpy" ]; then 
    echo "**** Installing moviepy ****"
    python3 -m pip install moviepy==2.1.2
else
    echo "**** moviepy already installed ****"
fi

piso639=$(python3 -m pip list | grep python-iso639)
if [ ! "$piso639" ]; then
    echo "**** Installing python-iso639 ****"
    python3 -m pip install -U python-iso639
else
    echo "**** python-iso639 already installed ****"
fi
