#!/usr/bin/env bash
# Prints ABI banner + some dynamic info

# Si NO quieres que se muestre en shells no interactivos, quita FORCE_ABI_MOTD
if [[ -z "${FORCE_ABI_MOTD:-}" ]]; then
  [ -t 1 ] || return 0          # requiere TTY
  [ -n "${PS1:-}" ] || return 0 # requiere shell interactivo
fi

# tput seguro: no revienta si no hay TERM o capability
_safe_tput() {
  command -v tput >/dev/null 2>&1 || return 0
  local term="${TERM:-dumb}"
  tput -T "$term" "$1" 2>/dev/null || true
}

BOLD="$(_safe_tput bold)"
# 'dim' no está en todos los terminfo; si no existe, queda vacío
DIM="$(_safe_tput dim)"
RESET="$(_safe_tput sgr0)"

ROLE="${ABI_ROLE:-Generic}"
NODE="${ABI_NODE:-ABI Node}"
KERNEL="$(uname -r)"
CPU="$(nproc) cores"
TIME="$(date -u '+%a %d %b %Y %H:%M:%S UTC')"
HOSTNAME_SHOW="${HOSTNAME:-$(hostname)}"

# Bloque estático (opcional)
if [[ -f /etc/abi-motd ]]; then
  cat /etc/abi-motd
fi

cat <<EOF
🌐 ${BOLD}${NODE}${RESET} - Connected on ${BOLD}${ROLE}${RESET}
🖥 ${DIM}Host:${RESET} ${HOSTNAME_SHOW}
🧠 ${DIM}CPU :${RESET} ${CPU}
📦 ${DIM}Kernel:${RESET} ${KERNEL}
🕒 ${DIM}Time:${RESET} ${TIME}
------------------------------------------
EOF
