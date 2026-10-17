#!/bin/bash
# -
# File: install-mkvtoolnix.sh
# Project: plugins
# -

# Script is executed by the Unmanic container on startup to auto-install dependencies

if ! command -v mkvmerge &> /dev/null; then
    echo "**** Installing mkvtoolnix (mkvmerge) ****"
    [[ "${__apt_updated:-false}" == 'false' ]] && apt-get update && __apt_updated=true
    apt-get install -y --no-install-recommends mkvtoolnix
else
    echo "**** mkvmerge already installed ****"
fi
