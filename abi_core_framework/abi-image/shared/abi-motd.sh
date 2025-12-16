#!/usr/bin/env bash
# Prints ABI banner + some dynamic info

# Delete FORCE_ABI_MOTD to not show not interactictive shell
if [[ -z "${FORCE_ABI_MOTD:-}" ]]; then
  [ -t 1 ] || return 0          # requiere TTY
  [ -n "${PS1:-}" ] || return 0 # requiere shell interactivo
fi


_safe_tput() {
  command -v tput >/dev/null 2>&1 || return 0
  local term="${TERM:-dumb}"
  tput -T "$term" "$1" 2>/dev/null || true
}

BOLD="$(_safe_tput bold)"

DIM="$(_safe_tput dim)"
RESET="$(_safe_tput sgr0)"

ROLE="${ABI_ROLE:-Generic}"
NODE="${ABI_NODE:-ABI Node}"
KERNEL="$(uname -r)"
CPU="$(nproc) cores"
TIME="$(date -u '+%a %d %b %Y %H:%M:%S UTC')"
HOSTNAME_SHOW="${HOSTNAME:-$(hostname)}"


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