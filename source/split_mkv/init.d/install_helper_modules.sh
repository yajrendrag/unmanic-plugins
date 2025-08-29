#!/bin/bash

# Script is executed by the Unmanic container on startup to auto-install dependencies

if ! command -v mkvmerge &> /dev/null; then
    echo "**** Installing mkvtools ****"
    apt-get update
    apt-get install mkvtoolnix -y
else
    echo "**** mkvtoolnix already installed ****"
fi

ffopcv=$(python3 -m pip list | grep opencv-python-headless)
if [ ! "$ffopcv" ]; then 
    echo "**** Installing opencv-python-headless ****"
    python3 -m pip install opencv-python-headless
else
    echo "**** opencv-python-headless already installed ****"
fi
