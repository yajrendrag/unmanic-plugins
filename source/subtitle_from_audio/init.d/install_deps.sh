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

porta=$(apt-cache policy portaudio19-dev)
regex="portaudio19-dev:"$'\n'"[[:space:]]*Installed: \(none\)"$'\n'"[[:space:]]*Candidate:.*"
[[ "$porta" =~ $regex ]] && apt-get update && apt-get install -y portaudio19-dev

regex="python3-pyaudio:"$'\n'"[[:space:]]*Installed: \(none\)"$'\n'"[[:space:]]*Candidate:.*"
pypa=$(apt-cache policy python3-pyaudio)
[[ "$pypa" =~ $regex ]] && apt-get update && apt-get install -y python3-pyaudio

tch=$("${python_command}" -m pip list | grep "^torch " | grep "2.8.0")
tcha=$("${python_command}" -m pip list | grep "^torchaudio " | grep "2.8.0")
[[ ! $tch ]] || [[ ! $tcha ]] && "$python_command" -m pip install torch==2.8.0 torchaudio==2.8.0

wx=$("${python_command}" -m pip list | grep "^whisperx ")
if [[ ! $wx ]]; then
    echo "**** Installing whisperx ****"
    "$python_command" -m pip install whisperx
else
    echo "**** whisperx already installed ****"
fi

lc=$("${python_command}" -m pip list | grep "^langcodes ")
[[ ! $lc ]] && "$python_command" -m pip install langcodes
