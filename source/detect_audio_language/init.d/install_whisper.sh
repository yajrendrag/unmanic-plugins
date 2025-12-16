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

if ! command -v whisper &> /dev/null; then
    echo "**** Installing whisper ****"
    "$python_command" -m pip install -U openai-whisper
else
    echo "**** whisper already installed ****"
fi

#mpy=$(python3 -m pip list | grep moviepy)
#if [ ! "$mpy" ]; then 
#    echo "**** Installing moviepy ****"
#    python3 -m pip install moviepy==2.1.2
#else
#    echo "**** moviepy already installed ****"
#fi
