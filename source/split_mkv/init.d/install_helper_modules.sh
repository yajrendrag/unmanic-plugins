#!/bin/bash

# Script is executed by the Unmanic container on startup to auto-install dependencies

if ! command -v mkvmerge &> /dev/null; then
    echo "**** Installing mkvtools ****"
    apt-get update
    apt-get install mkvtoolnix -y
else
    echo "**** mkvtoolnix already installed ****"
fi

if [[ -d /config/.unmanic/userdata/split_mkv ]]; then
    if [[ ! -f /config/.unmanic/userdata/split_mkv/credits_dictionary ]]; then
        echo "**** moving credits_dictionary into place ****"
        mv /config/.unmanic/plugins/split_mkv/credits_dictionary  /config/.unmanic/userdata/split_mkv/credits_dictionary
    fi
fi
