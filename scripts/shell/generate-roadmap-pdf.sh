#!/usr/bin/env bash
# Convert an EO's roadmap markdown variants to clean PDFs.
# Cross-platform: macOS, Linux, and Windows (run from Git Bash or WSL).
# Required tools: pandoc, and a Chromium-based browser (Google Chrome or Microsoft Edge).
# Usage:   generate-roadmap-pdf.sh <eo-slug> <pdfs-dir>
# Example: generate-roadmap-pdf.sh jane-doe "$ROADMAP_OUTPUT_DIR/jane-doe/pdfs"
#
# Looks for <pdfs-dir>/../<eo-slug>-variant-d-long.md and -variant-d-tactical.md.
# Set CHROME_BIN to override browser auto-detection (Chrome or Edge path).
set -euo pipefail

EO_SLUG="${1:?Usage: generate-roadmap-pdf.sh <eo-slug> <pdfs-dir>}"
PDFS_DIR="${2:?Usage: generate-roadmap-pdf.sh <eo-slug> <pdfs-dir>}"

# --- Detect the shell environment so we can hand the browser native paths. ---
case "$(uname -s 2>/dev/null || echo unknown)" in
  MINGW*|MSYS*|CYGWIN*) IS_WIN_POSIX=1 ;;   # Git Bash / MSYS / Cygwin
  *)                    IS_WIN_POSIX=0 ;;
esac
case "$(uname -r 2>/dev/null || echo)" in
  *microsoft*|*Microsoft*|*WSL*) IS_WSL=1 ;;
  *)                             IS_WSL=0 ;;
esac

# --- Find a Chromium-based browser: $CHROME_BIN, then common Chrome/Edge paths. ---
find_browser() {
  if [ -n "${CHROME_BIN:-}" ]; then printf '%s' "$CHROME_BIN"; return 0; fi
  local candidates=(
    # macOS
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"
    "/Applications/Chromium.app/Contents/MacOS/Chromium"
    # Windows via Git Bash (/c/...) or WSL (/mnt/c/...)
    "/c/Program Files/Google/Chrome/Application/chrome.exe"
    "/c/Program Files (x86)/Google/Chrome/Application/chrome.exe"
    "/mnt/c/Program Files/Google/Chrome/Application/chrome.exe"
    "/mnt/c/Program Files (x86)/Google/Chrome/Application/chrome.exe"
    "/c/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"
    "/c/Program Files/Microsoft/Edge/Application/msedge.exe"
    "/mnt/c/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"
  )
  local c
  for c in "${candidates[@]}"; do
    if [ -e "$c" ]; then printf '%s' "$c"; return 0; fi
  done
  # Linux (and WSL with a native browser): search PATH.
  local b
  for b in google-chrome google-chrome-stable chromium chromium-browser microsoft-edge; do
    if command -v "$b" >/dev/null 2>&1; then command -v "$b"; return 0; fi
  done
  return 1
}

if ! CHROME="$(find_browser)"; then
  echo "ERROR: no Chromium-based browser found. Install Google Chrome or Microsoft Edge," >&2
  echo "       or set CHROME_BIN to its path (e.g. chrome.exe / msedge.exe on Windows)." >&2
  exit 1
fi

# --- Decide whether the browser needs Windows-style paths (Git Bash / WSL+exe). ---
WIN_PATHS=0; CONV=""
if [ "$IS_WIN_POSIX" = "1" ] && command -v cygpath >/dev/null 2>&1; then
  WIN_PATHS=1; CONV="cygpath -w"
elif [ "$IS_WSL" = "1" ] && [[ "$CHROME" == *.exe ]] && command -v wslpath >/dev/null 2>&1; then
  WIN_PATHS=1; CONV="wslpath -w"
fi

mkdir -p "$PDFS_DIR"
# Absolutize the path. A relative file:// URL makes headless Chrome emit an error
# page instead of a PDF, and the documented default ($ROADMAP_OUTPUT_DIR=./roadmap-output)
# is relative. `cd && pwd` is portable (no realpath dependency).
PDFS_DIR="$(cd "$PDFS_DIR" && pwd)"
PARENT_DIR="$(dirname "$PDFS_DIR")"

for VARIANT in "variant-d-long" "variant-d-tactical"; do
  MD_FILE="$PARENT_DIR/${EO_SLUG}-${VARIANT}.md"
  HTML_FILE="$PDFS_DIR/${EO_SLUG}-${VARIANT}.html"
  PDF_FILE="$PDFS_DIR/${EO_SLUG}-${VARIANT}.pdf"

  if [ ! -f "$MD_FILE" ]; then
    echo "ERROR: $MD_FILE not found"; exit 1
  fi

  echo "=== Building ${EO_SLUG}-${VARIANT} ==="

  # Markdown to HTML. --metadata pagetitle (not title) suppresses the pandoc title block.
  pandoc "$MD_FILE" -s \
    --metadata pagetitle="${EO_SLUG} Roadmap" \
    -o "$HTML_FILE"

  # Hand the browser OS-native paths. Under Git Bash/WSL a Windows .exe can't read
  # /c/... or /home/... paths, so convert to a Windows path + file:/// URL.
  if [ "$WIN_PATHS" = "1" ]; then
    PDF_ARG="$($CONV "$PDF_FILE")"
    HTML_ARG="file:///$($CONV "$HTML_FILE" | tr '\\' '/')"
  else
    PDF_ARG="$PDF_FILE"
    HTML_ARG="file://$HTML_FILE"
  fi

  # HTML to PDF. --no-pdf-header-footer removes the browser's default URL/date/page-number headers.
  "$CHROME" --headless=new --disable-gpu \
    --no-pdf-header-footer \
    --print-to-pdf="$PDF_ARG" \
    "$HTML_ARG" 2>&1 | tail -1

  ls -la "$PDF_FILE"
done

echo "=== Done. PDFs at $PDFS_DIR ==="
