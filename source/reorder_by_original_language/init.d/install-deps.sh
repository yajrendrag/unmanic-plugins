#!/bin/bash
# Install Python dependencies for reorder_by_original_language plugin

/opt/venv/bin/python3 -m pip install --cache-dir /config/.cache/pip langcodes parse-torrent-title requests
