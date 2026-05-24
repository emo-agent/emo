#!/usr/bin/env bash
# emo installer — standalone, curl-pipe friendly
#
# Quick install (latest release binary, no Python required):
#   curl -fsSL https://raw.githubusercontent.com/javedh-dev/emo/main/install.sh | bash
#
# With options via env vars (works with curl pipe):
#   curl -fsSL .../install.sh | EMO_VERSION=v0.2.0 bash
#   curl -fsSL .../install.sh | EMO_METHOD=pip bash      # force pip install
#   curl -fsSL .../install.sh | EMO_PREFIX=/usr/local bash
#
# Or download and run directly:
#   bash install.sh [--version v0.2.0] [--method binary|pip] [--prefix <dir>]

set -euo pipefail

# ── Configuration ─────────────────────────────────────────────────────────────
EMO_GITHUB_REPO="javedh-dev/emo"
EMO_BINARY_NAME="emo"

# Defaults — all overridable via env vars or CLI flags
VERSION="${EMO_VERSION:-latest}"   # "latest" resolves to the newest GH release
METHOD="${EMO_METHOD:-binary}"     # binary | pip
PREFIX="${EMO_PREFIX:-}"           # install dir; derived from method if empty

# Global — set by install_binary / install_pip, used by _first_run
EMO_BIN=""

# ── Parse CLI flags ───────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
  case "$1" in
    --version)  VERSION="$2";  shift 2 ;;
    --method)   METHOD="$2";   shift 2 ;;
    --prefix)   PREFIX="$2";   shift 2 ;;
    -h|--help)
      echo "Usage: bash install.sh [--version v0.x.x] [--method binary|pip] [--prefix <dir>]"
      echo ""
      echo "Env var equivalents (usable with curl | bash):"
      echo "  EMO_VERSION=v0.2.0      install a specific release"
      echo "  EMO_METHOD=pip          force pip-based install (requires Python 3.9+)"
      echo "  EMO_PREFIX=/usr/local   install prefix"
      exit 0 ;;
    *) echo "Unknown option: $1" >&2; exit 1 ;;
  esac
done

# ── Pretty output ─────────────────────────────────────────────────────────────
if [[ -t 1 ]]; then
  BOLD="\033[1m"; GREEN="\033[32m"; YELLOW="\033[33m"; RED="\033[31m"; RESET="\033[0m"
else
  BOLD=""; GREEN=""; YELLOW=""; RED=""; RESET=""
fi
info()    { echo -e "${BOLD}[emo]${RESET} $*"; }
success() { echo -e "${GREEN}[emo]${RESET} $*"; }
warn()    { echo -e "${YELLOW}[emo]${RESET} $*"; }
die()     { echo -e "${RED}[emo] ERROR:${RESET} $*" >&2; exit 1; }

# ── Detect OS / arch ──────────────────────────────────────────────────────────
OS="$(uname -s)"
ARCH="$(uname -m)"

case "$OS" in
  Linux)  OS_KEY="linux" ;;
  Darwin) OS_KEY="macos" ;;
  *)      OS_KEY="" ;;
esac

case "$ARCH" in
  x86_64|amd64)          ARCH_KEY="x86_64" ;;
  aarch64|arm64)         ARCH_KEY="arm64" ;; # normalise; release uses arm64 for macos, aarch64 for linux
  *)                     ARCH_KEY="" ;;
esac

# Linux aarch64 release asset uses "aarch64" not "arm64"
if [[ "$OS_KEY" == "linux" && "$ARCH_KEY" == "arm64" ]]; then
  ARCH_KEY="aarch64"
fi

PLATFORM="${OS_KEY}-${ARCH_KEY}"

# Determine if a prebuilt binary exists for this platform
SUPPORTED_PLATFORMS="linux-x86_64 linux-aarch64 macos-arm64"
HAS_BINARY=0
for p in $SUPPORTED_PLATFORMS; do
  if [[ "$p" == "$PLATFORM" ]]; then HAS_BINARY=1; break; fi
done

if [[ $HAS_BINARY -eq 0 && "$METHOD" == "binary" ]]; then
  warn "No prebuilt binary for ${PLATFORM}. Falling back to pip install."
  METHOD="pip"
fi

if [[ -z "$OS_KEY" ]]; then
  die "Unsupported OS: $(uname -s). Supported: Linux, macOS."
fi

need() { command -v "$1" &>/dev/null || die "'$1' is required but not installed."; }
need curl

# ════════════════════════════════════════════════════════════════════════════════
# METHOD: binary
# ════════════════════════════════════════════════════════════════════════════════
install_binary() {
  BIN_DIR="${PREFIX:-${HOME}/.local/bin}"

  # Resolve "latest" to the actual tag via GitHub API
  if [[ "$VERSION" == "latest" ]]; then
    info "Resolving latest release ..."
    VERSION="$(curl -fsSL "https://api.github.com/repos/${EMO_GITHUB_REPO}/releases/latest" \
      | grep '"tag_name"' | head -n1 | sed 's/.*"tag_name": *"\([^"]*\)".*/\1/')"
    [[ -n "$VERSION" ]] || die "Could not resolve latest release. Check your internet connection."
  fi

  ASSET="emo-${PLATFORM}.tar.gz"
  ASSET_URL="https://github.com/${EMO_GITHUB_REPO}/releases/download/${VERSION}/${ASSET}"
  CHECKSUM_URL="${ASSET_URL}.sha256"

  TMP_DIR="$(mktemp -d)"
  trap 'rm -rf "$TMP_DIR"' EXIT

  info "Downloading emo ${VERSION} for ${PLATFORM} ..."
  curl -fsSL "$ASSET_URL"     -o "${TMP_DIR}/${ASSET}"        || die "Download failed: ${ASSET_URL}"
  curl -fsSL "$CHECKSUM_URL"  -o "${TMP_DIR}/${ASSET}.sha256" || warn "Could not download checksum — skipping verification."

  if [[ -f "${TMP_DIR}/${ASSET}.sha256" ]]; then
    EXPECTED="$(cat "${TMP_DIR}/${ASSET}.sha256")"
    if command -v shasum &>/dev/null; then
      ACTUAL="$(shasum -a 256 "${TMP_DIR}/${ASSET}" | awk '{print $1}')"
    elif command -v sha256sum &>/dev/null; then
      ACTUAL="$(sha256sum "${TMP_DIR}/${ASSET}" | awk '{print $1}')"
    else
      warn "Neither shasum nor sha256sum found — skipping checksum verification."
      ACTUAL="$EXPECTED"
    fi
    [[ "$ACTUAL" == "$EXPECTED" ]] || die "Checksum mismatch! Expected ${EXPECTED}, got ${ACTUAL}. Aborting."
    info "Checksum verified."
  fi

  info "Installing to ${BIN_DIR} ..."
  mkdir -p "$BIN_DIR"
  tar -xzf "${TMP_DIR}/${ASSET}" -C "$BIN_DIR"
  chmod +x "${BIN_DIR}/emo"

  EMO_BIN="${BIN_DIR}/emo"   # global
  [[ -x "$EMO_BIN" ]] || die "Install failed — binary not found at ${EMO_BIN}."

  _patch_shell_path "$BIN_DIR"

  export PATH="${BIN_DIR}:${PATH}"
}

# ════════════════════════════════════════════════════════════════════════════════
# METHOD: pip (fallback — requires Python 3.9+)
# ════════════════════════════════════════════════════════════════════════════════
install_pip() {
  VENV_DIR="${PREFIX:-${HOME}/.emo/venv}"
  BIN_DIR="${VENV_DIR}/bin"

  PYTHON=""
  for candidate in python3.12 python3.11 python3.10 python3.9 python3 python; do
    if command -v "$candidate" &>/dev/null; then
      if "$candidate" -c 'import sys; sys.exit(0 if sys.version_info >= (3,9) else 1)' 2>/dev/null; then
        PYTHON="$candidate"
        break
      fi
    fi
  done
  [[ -z "$PYTHON" ]] && die "Python 3.9+ is required for pip install but was not found."
  info "Using $("$PYTHON" --version)"

  need tar

  # Determine install source — EMO_ARCHIVE_URL can override for testing
  if [[ -n "${EMO_ARCHIVE_URL:-}" ]]; then
    _ARCHIVE="$EMO_ARCHIVE_URL"
    info "Downloading emo source ..."
  elif [[ "$VERSION" == "latest" ]]; then
    _ARCHIVE="https://github.com/${EMO_GITHUB_REPO}/archive/refs/heads/main.tar.gz"
    info "Downloading emo (latest source) ..."
  else
    _ARCHIVE="https://github.com/${EMO_GITHUB_REPO}/archive/refs/tags/${VERSION}.tar.gz"
    info "Downloading emo ${VERSION} source ..."
  fi

  TMP_DIR="$(mktemp -d)"
  trap 'rm -rf "$TMP_DIR"' EXIT

  curl -fsSL "$_ARCHIVE" -o "${TMP_DIR}/emo.tar.gz" \
    || die "Download failed. Check your internet connection."

  tar -xzf "${TMP_DIR}/emo.tar.gz" -C "$TMP_DIR"
  SRC_DIR="$(find "$TMP_DIR" -maxdepth 1 -mindepth 1 -type d | head -n1)"
  [[ -f "${SRC_DIR}/pyproject.toml" ]] || die "Unexpected archive layout."

  info "Creating virtual environment at ${VENV_DIR} ..."
  mkdir -p "$VENV_DIR"
  "$PYTHON" -m venv "$VENV_DIR"

  info "Installing emo ..."
  "${VENV_DIR}/bin/pip" install --quiet --upgrade pip
  "${VENV_DIR}/bin/pip" install --no-input "$SRC_DIR"

  EMO_BIN="${BIN_DIR}/emo"   # global
  [[ -x "$EMO_BIN" ]] || die "Install failed — emo binary not found at ${EMO_BIN}."

  _patch_shell_path "$BIN_DIR"

  export PATH="${BIN_DIR}:${PATH}"
}

# ── Shell PATH integration ────────────────────────────────────────────────────
_patch_shell_path() {
  local bin_dir="$1"
  local export_line="export PATH=\"${bin_dir}:\$PATH\""

  _add_to_rc() {
    local rc="$1"
    if [[ -f "$rc" ]] && grep -qF "$bin_dir" "$rc" 2>/dev/null; then return; fi
    printf '\n# emo — added by installer\n%s\n' "$export_line" >> "$rc"
    warn "Added PATH entry to ${rc}"
  }

  local shell_name
  shell_name="$(basename "${SHELL:-}")"
  case "$shell_name" in
    zsh)
      _add_to_rc "${ZDOTDIR:-$HOME}/.zshrc" ;;
    bash)
      _add_to_rc "${HOME}/.bashrc"
      if [[ "$OS_KEY" == "macos" ]]; then _add_to_rc "${HOME}/.bash_profile"; fi ;;
    fish)
      local fish_rc="${HOME}/.config/fish/config.fish"
      mkdir -p "$(dirname "$fish_rc")"
      if ! grep -qF "$bin_dir" "$fish_rc" 2>/dev/null; then
        printf '\n# emo — added by installer\nfish_add_path %s\n' "$bin_dir" >> "$fish_rc"
        warn "Added fish_add_path to ${fish_rc}"
      fi ;;
    *)
      warn "Unrecognised shell. Add this to your shell rc manually:"
      echo "  $export_line" ;;
  esac
}

# ── First-run config wizard ───────────────────────────────────────────────────
_first_run() {
  [[ -x "$EMO_BIN" ]] || die "Internal error: EMO_BIN not set after install."
  echo ""
  success "emo installed  (method: ${METHOD}, platform: ${PLATFORM})"
  echo ""

  local config_file="${HOME}/.emo/config.yaml"
  if [[ ! -f "$config_file" ]]; then
    if [[ -t 0 ]]; then
      read -rp "[emo] Run 'emo setup' now to configure your model and API key? [Y/n] " yn </dev/tty
      case "${yn:-Y}" in
        [Yy]*|"") "$EMO_BIN" setup ;;
        *)         warn "Skipped. Run 'emo setup' when you're ready." ;;
      esac
    else
      info "Non-interactive install. Run 'emo setup' to configure before first use."
    fi
  else
    info "Existing config found at ${config_file} — skipping setup."
  fi

  echo ""
  success "Done!  Start a session: emo"
  echo ""
  info "If 'emo' is not found after opening a new shell, add it to PATH manually:"
  echo "  export PATH=\"$(dirname "$EMO_BIN"):\$PATH\""
}

# ── Main ──────────────────────────────────────────────────────────────────────
info "emo installer  (os: ${OS_KEY}, arch: ${ARCH_KEY}, method: ${METHOD})"

case "$METHOD" in
  binary) install_binary ;;
  pip)    install_pip    ;;
  *)      die "Unknown method '${METHOD}'. Use 'binary' or 'pip'." ;;
esac

_first_run
