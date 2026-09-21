#!/usr/bin/env bash
###
# Install Tesseract OCR and language packs for bitmap subtitle extraction
###

set -e

TESSERACT_PACKAGES=(
    tesseract-ocr
    tesseract-ocr-eng
    tesseract-ocr-deu
    tesseract-ocr-fra
    tesseract-ocr-spa
    tesseract-ocr-ita
    tesseract-ocr-por
    tesseract-ocr-nld
    tesseract-ocr-pol
    tesseract-ocr-rus
    tesseract-ocr-jpn
    tesseract-ocr-chi-sim
    tesseract-ocr-chi-tra
    tesseract-ocr-kor
    tesseract-ocr-ara
)

# Check if all packages are already installed
missing=()
for pkg in "${TESSERACT_PACKAGES[@]}"; do
    if ! dpkg-query -W -f='${Status}' "${pkg}" 2>/dev/null | grep -q "install ok installed"; then
        missing+=("${pkg}")
    fi
done

if [[ ${#missing[@]} -eq 0 ]]; then
    echo "Tesseract OCR already installed"
    exit 0
fi

echo "Installing Tesseract OCR packages: ${missing[*]}"

# Update apt only once
[[ "${__apt_updated:-false}" == 'false' ]] && apt-get update && __apt_updated=true

DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends "${missing[@]}"

# Verify installation
if command -v tesseract &> /dev/null; then
    echo "Tesseract OCR installed successfully"
    tesseract --list-langs || true
else
    echo "ERROR: Tesseract OCR installation failed"
    exit 1
fi

echo "Installation complete."
