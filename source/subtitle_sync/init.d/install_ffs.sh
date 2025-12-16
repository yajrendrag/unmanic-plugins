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

ffspy=$("${python_command}" -m pip list | grep ffsubsync)
if [ ! "$ffspy" ]; then
    echo "**** Installing ffsubsync ****"
    "python_command" -m pip install ffsubsync
else
    echo "**** ffsubsync already installed ****"
fi
