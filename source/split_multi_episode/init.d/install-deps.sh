#!/bin/bash
###
# File: install-deps.sh
# Project: split_multi_episode
# File Created: 2026
# Author: yajrendrag
# -----
# Description: Install system and Python dependencies for the split_multi_episode plugin
###

echo "split_multi_episode: Installing dependencies..."

# FFmpeg should already be available in Unmanic
# Check if ffmpeg is available
if ! command -v ffmpeg &> /dev/null; then
    echo "WARNING: ffmpeg not found. This plugin requires ffmpeg."
fi

if ! command -v ffprobe &> /dev/null; then
    echo "WARNING: ffprobe not found. This plugin requires ffprobe."
fi

# Install Chromaprint for audio fingerprinting (fpcalc command)
if ! command -v fpcalc &> /dev/null; then
    echo "split_multi_episode: Installing chromaprint-tools for audio fingerprinting..."
    apt-get update -qq && apt-get install -y -qq libchromaprint-tools 2>/dev/null || \
        echo "WARNING: Could not install chromaprint-tools. Audio fingerprinting will be disabled."
fi

# Install Python dependencies via pip in the Unmanic virtual environment
PIP="/opt/venv/bin/python3 -m pip"

echo "split_multi_episode: Installing Python packages..."

# Image hashing for intro/outro detection
$PIP install --quiet "imagehash>=4.3.1"

# Pillow for image processing
$PIP install --quiet "Pillow>=9.0.0"

# Requests for TMDB API calls
$PIP install --quiet "requests>=2.28.0"

# Ollama client for LLM vision detection (optional)
$PIP install --quiet "ollama>=0.1.0"

# Parse-torrent-title for filename parsing
$PIP install --quiet "parse-torrent-title>=2.8.0"

echo "split_multi_episode: Python dependencies installed"

# Optional: Install Ollama for LLM detection (user must do this manually on the host)
# curl -fsSL https://ollama.com/install.sh | sh
# ollama pull llava:7b-v1.6-mistral-q4_K_M

echo "split_multi_episode: Dependency installation complete"
