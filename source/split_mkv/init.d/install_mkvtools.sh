#!/bin/bash

# Script is executed by the Unmanic container on startup to auto-install dependencies

if ! command -v mkvmerge &> /dev/null; then
    echo "**** Installing mkvtools ****"
    apt-get update
    apt-get install mkvtoolnix -y
else
    echo "**** mkvtoolnix already installed ****"

if ! command -v scenedetect &> /dev/null; then
    echo "**** Installing pyscenedetect ****"
    python3 -m pip install --upgrade scenedetect[opencv-headless]
else
    echo "**** pyscenedetect already installed ****"
