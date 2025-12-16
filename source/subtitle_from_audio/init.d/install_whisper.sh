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

if ! "$python_command" -c "import langcodes" > /dev/null 2>&1; then
    echo "langcodes module not found. Installing..."
    "$python_command" -m pip install langcodes==3.5.0
fi
