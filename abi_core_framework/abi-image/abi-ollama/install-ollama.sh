#!/bin/sh
set -eu

status(){ printf ">>> %s\n" "$*" >&2; }
error(){ printf "ERROR: %s\n" "$*" >&2; exit 1; }
warning(){ printf "WARNING: %s\n" "$*" >&2; }

TEMP_DIR=$(mktemp -d)
trap 'rm -rf "$TEMP_DIR"' EXIT

available(){ command -v "$1" >/dev/null 2>&1; }
require(){
  miss=""
  for t in "$@"; do available "$t" || miss="$miss $t"; done
  printf "%s" "$miss"
}

[ "$(uname -s)" = "Linux" ] || error "Linux only"
case "$(uname -m)" in x86_64) ARCH=amd64;; aarch64|arm64) ARCH=arm64;; *) error "Unsupported arch";; esac
VER_PARAM="${OLLAMA_VERSION:+?version=$OLLAMA_VERSION}"

SUDO=""
[ "$(id -u)" -ne 0 ] && { available sudo || error "Run as root or install sudo"; SUDO=sudo; }

need=$(require curl tar)
[ -n "$need" ] && { status "Missing:$need"; exit 1; }

# quick opt-out for prebuilt images
[ "${OLLAMA_SKIP_INSTALL:-0}" = "1" ] && { status "Skipping Ollama install (OLLAMA_SKIP_INSTALL=1)"; exit 0; }

# find install dir
for d in /usr/local/bin /usr/bin /bin; do echo "$PATH" | grep -q "$d" && BINDIR=$d && break; done
[ -z "${BINDIR:-}" ] && BINDIR=/usr/local/bin
OLLAMA_INSTALL_DIR="$(dirname "$BINDIR")"

$SUDO install -d -m755 "$BINDIR" "$OLLAMA_INSTALL_DIR/lib/ollama"

fetch_and_extract(){
  dst=$1
  if [ -n "${2:-}" ] && [ -f "$2" ]; then
    status "Using local tarball: $2"
    $SUDO tar -xzf "$2" -C "$dst"
  else
    url=$3
    status "Downloading $url"
    curl --fail --show-error --location --compressed --retry 3 --retry-delay 5 --retry-connrefused "$url" | $SUDO tar -xzf - -C "$dst"
  fi
}

# main bundle: prefer OLLAMA_TARBALL if set
if [ -n "${OLLAMA_TARBALL:-}" ] && [ -f "$OLLAMA_TARBALL" ]; then
  fetch_and_extract "$OLLAMA_INSTALL_DIR" "$OLLAMA_TARBALL"
else
  fetch_and_extract "$OLLAMA_INSTALL_DIR" "" "https://ollama.com/download/ollama-linux-${ARCH}.tgz${VER_PARAM}"
fi

# optional extras (jetpack/rocm) using env vars OLLAMA_TARBALL_JETPACK / OLLAMA_TARBALL_ROCM
if [ -f /etc/nv_tegra_release ]; then
  if grep -q R36 /etc/nv_tegra_release 2>/dev/null; then
    [ -n "${OLLAMA_TARBALL_JETPACK:-}" ] && tb="$OLLAMA_TARBALL_JETPACK" || tb=""
    fetch_and_extract "$OLLAMA_INSTALL_DIR" "$tb" "https://ollama.com/download/ollama-linux-${ARCH}-jetpack6.tgz${VER_PARAM}"
  elif grep -q R35 /etc/nv_tegra_release 2>/dev/null; then
    [ -n "${OLLAMA_TARBALL_JETPACK:-}" ] && tb="$OLLAMA_TARBALL_JETPACK" || tb=""
    fetch_and_extract "$OLLAMA_INSTALL_DIR" "$tb" "https://ollama.com/download/ollama-linux-${ARCH}-jetpack5.tgz${VER_PARAM}"
  else
    warning "Unknown JetPack; skipping"
  fi
fi

# make accessible
$SUDO ln -sf "$OLLAMA_INSTALL_DIR/ollama" "$BINDIR/ollama"

status "Ollama installed at $OLLAMA_INSTALL_DIR (command: $BINDIR/ollama)"