#!/bin/bash

# Script is executed by the Unmanic container on startup to auto-install dependencies
TARGET_DIR="/opt/venv"
if [[ -f "$TARGET_DIR/pyvenv.cfg" && -f "$TARGET_DIR/bin/python3" ]]; then
    # Venv case (Ubuntu 24 style or manual venv)
    python_command="$TARGET_DIR/bin/python3"
else
    # System case (Ubuntu 22 style)
    python_command="/usr/bin/python3"
fi


if ! command -v mkvmerge &> /dev/null; then
    echo "**** Installing mkvtools ****"
    apt-get update
    apt-get install mkvtoolnix -y
else
    echo "**** mkvtoolnix already installed ****"
fi

ffopcv=$("${python_command}" -m pip list | grep opencv-python-headless)
if [ ! "$ffopcv" ]; then
    echo "**** Installing opencv-python-headless ****"
    "$python_command" -m pip install opencv-python-headless
else
    echo "**** opencv-python-headless already installed ****"
fi

pil=$("${python_command}" -m pip list | grep pillow)
if [ ! "$pil" ]; then
    echo "**** Installing pillow ****"
    "$python_command" -m pip install pillow
else
    echo "**** pillow already installed ****"
fi
