#!/bin/bash
# -------------------------------------------------------------------
# Auto Lip Sync - dependency installer (sourced at container startup)
# -------------------------------------------------------------------

MODELS_DIR="/config/.unmanic/models/syncnet"
mkdir -p "${MODELS_DIR}"

# --- Ensure torch ecosystem is in the global venv --------------------
# These are expected in the container image; install if missing.
/opt/venv/bin/python3 -c "import torch" 2>/dev/null || \
    /opt/venv/bin/python3 -m pip install torch 2>/dev/null || true
/opt/venv/bin/python3 -c "import torchvision" 2>/dev/null || \
    /opt/venv/bin/python3 -m pip install torchvision 2>/dev/null || true
/opt/venv/bin/python3 -c "import torchaudio" 2>/dev/null || \
    /opt/venv/bin/python3 -m pip install torchaudio 2>/dev/null || true

# --- System dependencies for OpenCV ----------------------------------
[[ "${__apt_updated:-false}" == 'false' ]] && apt-get update && __apt_updated=true
apt-get install -y --no-install-recommends \
    libgl1-mesa-glx libglib2.0-0 2>/dev/null || true

# --- Download model weights from HuggingFace -------------------------
HF_REPO="lithiumice/syncnet"

download_hf_file() {
    local filename="$1"
    local dest="${MODELS_DIR}/${filename}"

    if [ -f "${dest}" ]; then
        echo "[auto_lipsync] ${filename} already present."
        return 0
    fi

    echo "[auto_lipsync] Downloading ${filename} from HuggingFace (${HF_REPO}) ..."

    # Try huggingface-cli first (respects HF_TOKEN env var automatically)
    if command -v huggingface-cli &>/dev/null; then
        huggingface-cli download "${HF_REPO}" "${filename}" \
            --local-dir "${MODELS_DIR}" --local-dir-use-symlinks False && return 0
    fi

    # Fallback: direct curl with optional token
    local auth_header=""
    if [ -n "${HF_TOKEN}" ]; then
        auth_header="Authorization: Bearer ${HF_TOKEN}"
    fi

    curl -fSL --retry 3 \
        ${auth_header:+-H "${auth_header}"} \
        -o "${dest}" \
        "https://huggingface.co/${HF_REPO}/resolve/main/${filename}" && return 0

    echo "[auto_lipsync] WARNING: Failed to download ${filename}."
    return 1
}

download_hf_file "sfd_face.pth"
download_hf_file "syncnet_v2.model"
