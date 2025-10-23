#!/usr/bin/env bash
set -euo pipefail

# Install VS Code and the Anthropic Claude extension, then configure ~/.claude
# Supported OS: macOS, Linux

YES=0
REINSTALL=0
TOKEN=""
BASE_URL=""
EXT_ID="anthropic.claude-code"
CODE_CMD=""
OS_NAME=""
ARCH_NAME=""
BREW_CMD=""
CODE_APP_PATH=""
CLI_APP_PATH=""
CLI_BUNDLE_ID=""
RUNNING_UNDER_ROSETTA=0
CODE_CMD_RESOLVED=""

print_help() {
  cat <<USAGE
Usage: install-claude-vscode.sh [--token <token>] [--base-url <url>] [-y|--yes] [--reinstall|-r]

This script will:
  - Install Visual Studio Code (macOS/Linux)
  - Install VS Code extension: anthropic.claude-code
  - Write ~/.claude/settings.json and ~/.claude/config.json for Claude

Options:
  --token, -t       ANTHROPIC_AUTH_TOKEN. If omitted, prompt interactively.
  --base-url, -u    ANTHROPIC_BASE_URL (e.g. https://api.anthropic.com). Trailing slash will be removed.
  --yes, -y         Non-interactive; assume 'yes' to install/changes.
  --reinstall, -r   Reinstall/upgrade VS Code (if possible) and reinstall/update the extension.
  --help, -h        Show this help.

You can also set env vars before running:
  ANTHROPIC_AUTH_TOKEN, ANTHROPIC_BASE_URL
USAGE
}

# Parse args
while [[ ${#} -gt 0 ]]; do
  case "$1" in
    --token|-t) TOKEN="$2"; shift 2;;
    --base-url|-u) BASE_URL="$2"; shift 2;;
    --yes|-y) YES=1; shift;;
    --reinstall|-r) REINSTALL=1; shift;;
    --help|-h) print_help; exit 0;;
    *) echo "Unknown option: $1" >&2; print_help; exit 1;;
  esac
done

# Fallback to env vars
TOKEN="${TOKEN:-${ANTHROPIC_AUTH_TOKEN:-}}"
BASE_URL="${BASE_URL:-${ANTHROPIC_BASE_URL:-}}"

require_command() {
  local binary="$1" guidance="${2:-}"
  if ! command -v "$binary" >/dev/null 2>&1; then
    if [[ -n "$guidance" ]]; then
      echo "Missing '$binary'. $guidance" >&2
    else
      echo "Missing required command: $binary" >&2
    fi
    return 1
  fi
}

confirm_action() {
  local prompt="$1"
  if [[ $YES -eq 1 ]]; then return 0; fi
  read -r -p "$prompt [y/N]: " reply
  case "$reply" in
    y|Y|yes|YES) return 0;;
    *) return 1;;
  esac
}

detect_platform() {
  local u a
  u=$(uname -s 2>/dev/null || echo unknown)
  a=$(uname -m 2>/dev/null || echo unknown)
  case "$u" in
    Darwin) OS_NAME="macOS" ;;
    Linux) OS_NAME="Linux" ;;
    *) echo "Unsupported OS: $u" >&2; exit 12;;
  esac
  ARCH_NAME="$a"
  if [[ "$OS_NAME" == "macOS" ]]; then
    # If running under Rosetta on Apple Silicon, prefer arm64 for downloads/installs
    local hw_arm
    hw_arm=$(/usr/sbin/sysctl -in hw.optional.arm64 2>/dev/null || echo 0)
    local proc_trans
    proc_trans=$(/usr/sbin/sysctl -in sysctl.proc_translated 2>/dev/null || echo 0)
    if [[ "$hw_arm" == "1" ]]; then
      if [[ "$a" == "x86_64" && "$proc_trans" == "1" ]]; then
        RUNNING_UNDER_ROSETTA=1
        ARCH_NAME="arm64"
      else
        ARCH_NAME="arm64"
      fi
    fi
    if [[ "$RUNNING_UNDER_ROSETTA" -eq 1 ]]; then
      echo "Detected $OS_NAME ($a via Rosetta -> using arm64)."
    else
      echo "Detected $OS_NAME ($ARCH_NAME)."
    fi
  else
    echo "Detected $OS_NAME ($ARCH_NAME)."
  fi
}

normalize_base_url() {
  if [[ -z "${BASE_URL:-}" ]]; then return; fi
  local normalized="$BASE_URL"
  while [[ "$normalized" == */ ]]; do normalized="${normalized%/}"; done
  BASE_URL="$normalized"
}

find_code_cli() {
  # Prefer existing PATH resolution
  if command -v code >/dev/null 2>&1; then CODE_CMD="code"; return 0; fi
  if command -v code-insiders >/dev/null 2>&1; then CODE_CMD="code-insiders"; return 0; fi
  # macOS app bundle path
  if [[ "${OS_NAME:-}" == "macOS" ]]; then
    # System Applications
    local mac_code="/Applications/Visual Studio Code.app/Contents/Resources/app/bin/code"
    if [[ -x "$mac_code" ]]; then CODE_CMD="$mac_code"; return 0; fi
    # System Applications (Insiders)
    mac_code="/Applications/Visual Studio Code - Insiders.app/Contents/Resources/app/bin/code"
    if [[ -x "$mac_code" ]]; then CODE_CMD="$mac_code"; return 0; fi
    # User Applications
    mac_code="$HOME/Applications/Visual Studio Code.app/Contents/Resources/app/bin/code"
    if [[ -x "$mac_code" ]]; then CODE_CMD="$mac_code"; return 0; fi
    # User Applications (Insiders)
    mac_code="$HOME/Applications/Visual Studio Code - Insiders.app/Contents/Resources/app/bin/code"
    if [[ -x "$mac_code" ]]; then CODE_CMD="$mac_code"; return 0; fi
  fi
  return 1
}

# Resolve a path to an absolute final destination by following symlinks (macOS readlink lacks -f)
resolve_to_absolute() {
  local p="$1"
  # If relative or bare command name, resolve via PATH first
  if [[ "${p#/}" == "$p" ]]; then
    p="$(command -v "$p" 2>/dev/null || echo "$p")"
  fi
  # Follow symlink chain
  local dir target
  while [[ -L "$p" ]]; do
    target="$(readlink "$p" 2>/dev/null || true)"
    [[ -z "$target" ]] && break
    if [[ "${target#/}" == "$target" ]]; then
      dir="$(cd "$(dirname "$p")" && pwd)"
      p="$dir/$target"
    else
      p="$target"
    fi
  done
  echo "$p"
}

# On macOS, try to discover the .app bundle for VS Code corresponding to the CLI
detect_macos_app_bundle() {
  CODE_APP_PATH=""
  [[ "${OS_NAME}" != "macOS" ]] && return 1
  local p
  p="$(resolve_to_absolute "$CODE_CMD" 2>/dev/null || true)"
  if [[ "$p" == *.app/Contents/* ]]; then
    local app="${p%%.app/Contents/*}.app"
    if [[ -d "$app" ]] && is_vscode_bundle "$app"; then CODE_APP_PATH="$app"; return 0; fi
  fi
  # Common install locations
  local cand
  for cand in \
    "/Applications/Visual Studio Code.app" \
    "/Applications/Visual Studio Code - Insiders.app" \
    "$HOME/Applications/Visual Studio Code.app" \
    "$HOME/Applications/Visual Studio Code - Insiders.app"; do
    if [[ -d "$cand" ]] && is_vscode_bundle "$cand"; then CODE_APP_PATH="$cand"; return 0; fi
  done
  # Spotlight search by bundle id if available
  if command -v mdfind >/dev/null 2>&1; then
    local found
    found="$(mdfind "kMDItemCFBundleIdentifier == 'com.microsoft.VSCode'" | head -n1 || true)"
    if [[ -d "$found" ]] && is_vscode_bundle "$found"; then CODE_APP_PATH="$found"; return 0; fi
    found="$(mdfind "kMDItemCFBundleIdentifier == 'com.microsoft.VSCodeInsiders'" | head -n1 || true)"
    if [[ -d "$found" ]] && is_vscode_bundle "$found"; then CODE_APP_PATH="$found"; return 0; fi
  fi
  return 1
}

# Read CFBundleIdentifier from an app bundle
get_macos_bundle_id() {
  local app="$1"
  local id=""
  if [[ -f "$app/Contents/Info.plist" ]]; then
    id=$(/usr/libexec/PlistBuddy -c "Print:CFBundleIdentifier" "$app/Contents/Info.plist" 2>/dev/null || true)
  fi
  echo "$id"
}

# True if the app bundle is official VS Code (stable or insiders)
is_vscode_bundle() {
  local app="$1"
  local id
  id="$(get_macos_bundle_id "$app")"
  case "$id" in
    com.microsoft.VSCode|com.microsoft.VSCodeInsiders) return 0 ;;
    *) return 1 ;;
  esac
}

# Determine the CPU arch for a macOS .app bundle (arm64/x86_64/universal/unknown)
get_macos_app_arch() {
  local app="$1" bin f info
  bin=""
  for f in "$app/Contents/MacOS"/*; do
    if [[ -f "$f" && -x "$f" ]]; then bin="$f"; break; fi
  done
  if [[ -z "$bin" ]]; then echo "unknown"; return; fi
  if command -v file >/dev/null 2>&1; then
    info=$(file -b "$bin" 2>/dev/null || true)
    case "$info" in
      *arm64*|*aarch64*) echo "arm64"; return ;;
      *x86_64*|*i386*) echo "x86_64"; return ;;
      *universal*|*fat*) echo "universal"; return ;;
    esac
  fi
  echo "unknown"
}

# Discover the host .app (any app) that owns the current CLI on macOS
detect_macos_cli_host_app() {
  CLI_APP_PATH=""; CLI_BUNDLE_ID=""
  [[ "${OS_NAME}" != "macOS" ]] && return 1
  local p app
  p="$(resolve_to_absolute "$CODE_CMD" 2>/dev/null || true)"
  if [[ "$p" == *.app/Contents/* ]]; then
    app="${p%%.app/Contents/*}.app"
    if [[ -d "$app" ]]; then
      CLI_APP_PATH="$app"
      CLI_BUNDLE_ID="$(get_macos_bundle_id "$app")"
      return 0
    fi
  fi
  return 1
}

# Prefer the official VS Code CLI binary if installed (stable or insiders)
set_official_vscode_cli() {
  [[ "${OS_NAME}" != "macOS" ]] && return 1
  local p
  for p in \
    "/Applications/Visual Studio Code.app/Contents/Resources/app/bin/code" \
    "$HOME/Applications/Visual Studio Code.app/Contents/Resources/app/bin/code" \
    "/Applications/Visual Studio Code - Insiders.app/Contents/Resources/app/bin/code" \
    "$HOME/Applications/Visual Studio Code - Insiders.app/Contents/Resources/app/bin/code"; do
    if [[ -x "$p" ]]; then
      CODE_CMD="$p"
      echo "Switching to official VS Code CLI: $p"
      return 0
    fi
  done
  return 1
}

# Choose Homebrew binary that matches the host CPU arch on macOS.
# On Apple Silicon prefer /opt/homebrew; on Intel prefer /usr/local.
resolve_brew_for_arch() {
  if [[ "${OS_NAME:-}" != "macOS" ]]; then return 1; fi
  local candidate=""
  # Prefer Apple Silicon Homebrew if present on Apple Silicon hardware
  if [[ "${ARCH_NAME:-}" == "arm64" ]]; then
    if [[ -x /opt/homebrew/bin/brew ]]; then candidate="/opt/homebrew/bin/brew"; fi
  fi
  # Fallbacks
  if [[ -z "$candidate" && -x /usr/local/bin/brew ]]; then candidate="/usr/local/bin/brew"; fi
  if [[ -z "$candidate" ]] && command -v brew >/dev/null 2>&1; then
    candidate="$(command -v brew)"
  fi
  if [[ -n "$candidate" ]]; then
    BREW_CMD="$candidate"
    return 0
  fi
  return 1
}

install_vscode_macos() {
  if find_code_cli; then return 0; fi
  # Ensure Homebrew exists; offer to install if missing
  if ! resolve_brew_for_arch; then
    echo "Homebrew not found."
    if confirm_action "Install Homebrew now via official script? (requires network; may prompt for password)"; then
      /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
      # Bring brew into current shell session (prefer arch-correct path)
      if [[ -x /opt/homebrew/bin/brew ]]; then
        eval "$(/opt/homebrew/bin/brew shellenv)" 2>/dev/null || true
      elif [[ -x /usr/local/bin/brew ]]; then
        eval "$(/usr/local/bin/brew shellenv)" 2>/dev/null || true
      fi
    else
      echo "VS Code installation requires Homebrew on macOS in this script path. Aborting per user choice." >&2
      return 1
    fi
  fi
  # Re-resolve brew after potential installation
  resolve_brew_for_arch || { echo "Homebrew still not available after attempted install. Install VS Code from https://code.visualstudio.com/ and re-run this script." >&2; return 1; }
  # On Apple Silicon, prefer /opt/homebrew; warn if Intel brew is selected
  if [[ "${ARCH_NAME}" == "arm64" && "${BREW_CMD}" == "/usr/local/bin/brew" ]]; then
    echo "Warning: Intel Homebrew detected on Apple Silicon; this may install x64 VS Code (Rosetta)."
    if [[ -x /opt/homebrew/bin/brew ]]; then
      BREW_CMD="/opt/homebrew/bin/brew"
    fi
  fi
  if confirm_action "Install VS Code via Homebrew cask using ${BREW_CMD}?"; then
    "${BREW_CMD}" install --cask visual-studio-code
  else
    echo "VS Code installation declined."; return 1
  fi
  find_code_cli || { echo "VS Code installed, but 'code' CLI not found. Launch VS Code and run 'Shell Command: Install \"code\" command in PATH' from Command Palette, then re-run." >&2; return 1; }
}

# Direct download + install (zip) for macOS, when Homebrew path fails or is declined
install_vscode_macos_direct_download() {
  require_command curl "Install curl to download VS Code."
  require_command unzip "Install unzip to extract VS Code."
  local channel="stable" arch="darwin"
  case "${ARCH_NAME:-}" in
    arm64|aarch64) arch="darwin-arm64" ;;
    *) arch="darwin" ;;
  esac
  local url="https://update.code.visualstudio.com/latest/$arch/$channel"
  local zip="/tmp/vscode_latest.zip"
  echo "Downloading $url ..."
  curl -fsSL "$url" -o "$zip"
  local tmpdir
  tmpdir=$(mktemp -d 2>/dev/null || mktemp -d -t vscode)
  unzip -q -o "$zip" -d "$tmpdir"
  local app_src="$tmpdir/Visual Studio Code.app"
  if [[ ! -d "$app_src" ]]; then
    echo "Unexpected archive contents; could not find 'Visual Studio Code.app' in archive." >&2
    return 1
  fi
  local app_dst="/Applications/Visual Studio Code.app"
  if [[ -d "$app_dst" ]]; then
    if confirm_action "'/Applications/Visual Studio Code.app' exists. Replace it?"; then
      rm -rf "$app_dst"
    else
      echo "Aborted replacing existing VS Code app."; return 1
    fi
  fi
  echo "Installing Visual Studio Code to /Applications ..."
  cp -R "$app_src" "/Applications/"
  # Prefer the app's CLI for this session
  CODE_CMD="/Applications/Visual Studio Code.app/Contents/Resources/app/bin/code"
  return 0
}

# Try Homebrew first; if it fails (e.g., binary conflict), fall back to direct download
install_official_vscode_macos() {
  local installed=0
  if resolve_brew_for_arch; then
    if confirm_action "Install VS Code via Homebrew cask using ${BREW_CMD}?"; then
      if "${BREW_CMD}" install --cask visual-studio-code; then
        installed=1
      else
        echo "Homebrew cask install failed; will attempt direct download." >&2
      fi
    fi
  fi
  if [[ $installed -ne 1 ]]; then
    install_vscode_macos_direct_download || return 1
  fi
  return 0
}

install_vscode_linux() {
  if find_code_cli; then return 0; fi
  # Try snap first
  if command -v snap >/dev/null 2>&1; then
    if confirm_action "Install VS Code via snap? (requires sudo)"; then
      sudo snap install code --classic || true
    fi
  fi
  if find_code_cli; then return 0; fi

  # Try apt (Debian/Ubuntu)
  if command -v apt-get >/dev/null 2>&1; then
    if confirm_action "Install VS Code via Microsoft apt repo? (requires sudo)"; then
      sudo apt-get update -y
      sudo apt-get install -y ca-certificates curl gnupg
      sudo install -m 0755 -d /etc/apt/keyrings
      curl -fsSL https://packages.microsoft.com/keys/microsoft.asc | sudo gpg --dearmor -o /etc/apt/keyrings/microsoft.gpg
      sudo chmod go+r /etc/apt/keyrings/microsoft.gpg
      echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/microsoft.gpg] https://packages.microsoft.com/repos/code stable main" | sudo tee /etc/apt/sources.list.d/vscode.list >/dev/null
      sudo apt-get update -y
      sudo apt-get install -y code
    fi
  fi
  if find_code_cli; then return 0; fi

  # Try dnf (Fedora/RHEL)
  if command -v dnf >/dev/null 2>&1 || command -v yum >/dev/null 2>&1; then
    local dnf_cmd="dnf"; command -v dnf >/dev/null 2>&1 || dnf_cmd="yum"
    if confirm_action "Install VS Code via Microsoft repo using $dnf_cmd? (requires sudo)"; then
      sudo rpm --import https://packages.microsoft.com/keys/microsoft.asc
      sudo sh -c 'cat > /etc/yum.repos.d/vscode.repo <<EOF2
[code]
name=Visual Studio Code
baseurl=https://packages.microsoft.com/yumrepos/vscode
enabled=1
gpgcheck=1
gpgkey=https://packages.microsoft.com/keys/microsoft.asc
EOF2'
      sudo $dnf_cmd check-update || true
      sudo $dnf_cmd -y install code
    fi
  fi

  if find_code_cli; then return 0; fi

  # Fallback: download package directly and install via dpkg/rpm
  if confirm_action "Download VS Code package directly and install? (requires sudo)"; then
    local arch="x64"
    case "$(uname -m)" in
      x86_64|amd64) arch="x64" ;;
      arm64|aarch64) arch="arm64" ;;
    esac
    if command -v dpkg >/dev/null 2>&1; then
      require_command curl "Install curl to download VS Code."
      local deb="/tmp/code_latest.deb"
      local url="https://update.code.visualstudio.com/latest/linux-deb-$arch/stable"
      echo "Downloading $url ..."
      curl -fsSL "$url" -o "$deb"
      sudo apt-get update -y || true
      if ! sudo apt-get install -y "$deb"; then
        sudo dpkg -i "$deb" || true
        sudo apt-get -f install -y || true
      fi
    elif command -v rpm >/dev/null 2>&1; then
      require_command curl "Install curl to download VS Code."
      local rpmf="/tmp/code_latest.rpm"
      local url="https://update.code.visualstudio.com/latest/linux-rpm-$arch/stable"
      echo "Downloading $url ..."
      curl -fsSL "$url" -o "$rpmf"
      if command -v dnf >/dev/null 2>&1; then
        sudo dnf -y install "$rpmf" || sudo dnf -y localinstall "$rpmf" || sudo rpm -Uvh --replacepkgs "$rpmf" || true
      else
        sudo yum -y localinstall "$rpmf" || sudo rpm -Uvh --replacepkgs "$rpmf" || true
      fi
    else
      echo "Neither dpkg nor rpm found. Please install VS Code manually from https://code.visualstudio.com/"
    fi
  fi

  find_code_cli || { echo "Unable to locate VS Code CLI after installation attempts. Install VS Code manually and re-run." >&2; return 1; }
}

install_vscode() {
  if [[ "${OS_NAME}" == "macOS" ]]; then
    install_vscode_macos
  else
    install_vscode_linux
  fi
}

# Try to reinstall/update VS Code based on platform and available package manager
reinstall_vscode() {
  echo "Attempting to reinstall/update VS Code..."
  if [[ "${OS_NAME}" == "macOS" ]]; then
    if ! resolve_brew_for_arch; then
      echo "Homebrew not found."
      if confirm_action "Install Homebrew now via official script? (requires network; may prompt for password)"; then
        /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
        if [[ -x /opt/homebrew/bin/brew ]]; then
          eval "$(/opt/homebrew/bin/brew shellenv)" 2>/dev/null || true
        elif [[ -x /usr/local/bin/brew ]]; then
          eval "$(/usr/local/bin/brew shellenv)" 2>/dev/null || true
        fi
        resolve_brew_for_arch || true
      fi
    fi
    if [[ -n "${BREW_CMD}" ]]; then
      if confirm_action "Reinstall VS Code via Homebrew cask using ${BREW_CMD}?"; then
        "${BREW_CMD}" update || true
        # Prefer reinstall if available; otherwise upgrade
        if "${BREW_CMD}" help reinstall >/dev/null 2>&1; then
          "${BREW_CMD}" reinstall --cask visual-studio-code || "${BREW_CMD}" upgrade --cask visual-studio-code || true
        else
          "${BREW_CMD}" upgrade --cask visual-studio-code || true
        fi
      fi
    else
      echo "Homebrew not available; cannot auto-reinstall VS Code on macOS. Please reinstall from https://code.visualstudio.com/"
    fi
    return 0
  fi

  # Linux
  if command -v snap >/dev/null 2>&1 && snap list code >/dev/null 2>&1; then
    if confirm_action "Reinstall VS Code via snap? (requires sudo)"; then
      sudo snap remove code || true
      sudo snap install code --classic || true
    fi
    return 0
  fi

  if command -v apt-get >/dev/null 2>&1 && dpkg -s code >/dev/null 2>&1; then
    if confirm_action "Reinstall VS Code via apt-get? (requires sudo)"; then
      sudo apt-get update -y || true
      sudo apt-get install -y --reinstall code || sudo apt-get install -y code || true
    fi
    return 0
  fi

  local dnf_cmd=""
  if command -v dnf >/dev/null 2>&1; then dnf_cmd="dnf"; fi
  if command -v yum >/dev/null 2>&1; then dnf_cmd="${dnf_cmd:-yum}"; fi
  if [[ -n "$dnf_cmd" ]] && rpm -q code >/dev/null 2>&1; then
    if confirm_action "Reinstall VS Code via $dnf_cmd? (requires sudo)"; then
      sudo $dnf_cmd -y reinstall code || sudo $dnf_cmd -y upgrade code || true
    fi
    return 0
  fi

  # Fallback: download latest package and install over existing
  if confirm_action "Download latest VS Code package and reinstall directly? (requires sudo)"; then
    local arch="x64"
    case "$(uname -m)" in
      x86_64|amd64) arch="x64" ;;
      arm64|aarch64) arch="arm64" ;;
    esac
    if command -v dpkg >/dev/null 2>&1; then
      require_command curl "Install curl to download VS Code."
      local deb="/tmp/code_latest.deb"
      local url="https://update.code.visualstudio.com/latest/linux-deb-$arch/stable"
      echo "Downloading $url ..."
      curl -fsSL "$url" -o "$deb"
      sudo apt-get install -y "$deb" || { sudo dpkg -i "$deb" || true; sudo apt-get -f install -y || true; }
    elif command -v rpm >/dev/null 2>&1; then
      require_command curl "Install curl to download VS Code."
      local rpmf="/tmp/code_latest.rpm"
      local url="https://update.code.visualstudio.com/latest/linux-rpm-$arch/stable"
      echo "Downloading $url ..."
      curl -fsSL "$url" -o "$rpmf"
      if command -v dnf >/dev/null 2>&1; then
        sudo dnf -y install "$rpmf" || sudo dnf -y localinstall "$rpmf" || sudo rpm -Uvh --replacepkgs "$rpmf" || true
      else
        sudo yum -y localinstall "$rpmf" || sudo rpm -Uvh --replacepkgs "$rpmf" || true
      fi
    fi
  fi

  echo "Could not determine package manager for VS Code; skipping VS Code reinstall."
}

# Determine whether a CLI path belongs to official VS Code (app bundle id check)
is_cli_official() {
  [[ "${OS_NAME}" != "macOS" ]] && return 0
  local cli="$1" p app
  p="$(resolve_to_absolute "$cli" 2>/dev/null || true)"
  if [[ "$p" == *.app/Contents/* ]]; then
    app="${p%%.app/Contents/*}.app"
    if is_vscode_bundle "$app"; then return 0; fi
  fi
  return 1
}

# Offer to replace /usr/local/bin/code with official VS Code CLI symlink
offer_replace_system_code() {
  [[ "${OS_NAME}" != "macOS" ]] && return 1
  local sys_cli="/usr/local/bin/code"
  [[ -e "$sys_cli" ]] || return 1
  if is_cli_official "$sys_cli"; then return 1; fi
  if confirm_action "Replace $sys_cli to point to official VS Code CLI? (current will be backed up)"; then
    local backup="/usr/local/bin/code.backup.$(date +%Y%m%d%H%M%S)"
    local target_cli="$CODE_CMD"
    if [[ ! -x "$target_cli" ]]; then
      set_official_vscode_cli || true
      target_cli="$CODE_CMD"
    fi
    if [[ -w "/usr/local/bin" ]]; then
      mv "$sys_cli" "$backup" 2>/dev/null || true
      ln -s "$target_cli" "$sys_cli" 2>/dev/null || true
    else
      sudo mv "$sys_cli" "$backup" 2>/dev/null || true
      sudo ln -s "$target_cli" "$sys_cli" 2>/dev/null || true
    fi
    echo "Replaced $sys_cli -> $target_cli (backup: $backup)"
  fi
}

install_extension() {
  find_code_cli || install_vscode
  find_code_cli || { echo "VS Code CLI 'code' not found; cannot install extension." >&2; exit 20; }
  # Show which VS Code CLI we are going to use
  local resolved_path
  resolved_path=$(command -v "$CODE_CMD" 2>/dev/null || echo "$CODE_CMD")
  echo "Using VS Code CLI: $resolved_path"
  CODE_CMD_RESOLVED="$resolved_path"
  # Reinstall path: try to uninstall first, then install
  if [[ "$REINSTALL" -eq 1 ]]; then
    echo "Reinstalling VS Code extension: $EXT_ID"
    "$CODE_CMD" --uninstall-extension "$EXT_ID" || true
  else
    # Check if extension is already installed (case-insensitive)
    if "$CODE_CMD" --list-extensions | awk '{print tolower($0)}' | grep -qx "$(echo "$EXT_ID" | tr '[:upper:]' '[:lower:]')"; then
      echo "Extension '$EXT_ID' already installed. Skipping."
      return 0
    fi
    echo "Installing VS Code extension: $EXT_ID"
  fi
  "$CODE_CMD" --install-extension "$EXT_ID" --force || {
    echo "Failed to install extension '$EXT_ID' via $CODE_CMD." >&2; exit 21
  }
}

prompt_if_needed() {
  if [[ -z "$TOKEN" ]]; then
    read -r -s -p "Enter ANTHROPIC_AUTH_TOKEN (input hidden): " TOKEN; echo
    if [[ -z "$TOKEN" ]]; then echo "Error: token is required." >&2; exit 2; fi
  fi
  if [[ -z "$BASE_URL" ]]; then
    read -r -p "Enter ANTHROPIC_BASE_URL (e.g. https://api.anthropic.com): " BASE_URL || true
    if [[ -z "$BASE_URL" ]]; then echo "Error: base URL is required." >&2; exit 2; fi
  fi
}

write_claude_files() {
  normalize_base_url
  local target_dir="$HOME/.claude"
  local settings_file="$target_dir/settings.json"
  local config_file="$target_dir/config.json"
  mkdir -p "$target_dir"

  cat > "$settings_file" <<JSON
{
  "env": {
    "ANTHROPIC_AUTH_TOKEN": "$TOKEN",
    "ANTHROPIC_BASE_URL": "$BASE_URL",
    "CLAUDE_CODE_MAX_OUTPUT_TOKENS": "64000",
    "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
    "API_TIMEOUT_MS": "600000",
    "BASH_DEFAULT_TIMEOUT_MS": "600000",
    "BASH_MAX_TIMEOUT_MS": "600000",
    "MCP_TIMEOUT": "30000",
    "MCP_TOOL_TIMEOUT": "600000",
    "CLAUDE_API_TIMEOUT": "600000"
  },
  "permissions": {
    "allow": [],
    "deny": []
  }
}
JSON

  cat > "$config_file" <<CFG
{
  "primaryApiKey": "default"
}
CFG

  chmod 600 "$settings_file" "$config_file" 2>/dev/null || true
  echo "✅ Wrote $settings_file"
  echo "✅ Wrote $config_file"
}

main() {
  detect_platform
  # Explicitly report whether VS Code is already available before doing anything else
  if find_code_cli; then
    # Resolve full path if it's on PATH; otherwise show the detected path
    resolved_path=$(command -v "$CODE_CMD" 2>/dev/null || echo "$CODE_CMD")
    code_ver=$("$CODE_CMD" --version 2>/dev/null | head -n1 || true)
    if [[ -n "$code_ver" ]]; then
      echo "VS Code detected: $code_ver ($resolved_path)"
    else
      echo "VS Code CLI detected at: $resolved_path"
    fi
    # On macOS, show the .app that owns the CLI and whether it's official VS Code
    if [[ "${OS_NAME}" == "macOS" ]]; then
      if detect_macos_cli_host_app; then
        if is_vscode_bundle "$CLI_APP_PATH"; then
          echo "VS Code app bundle: $CLI_APP_PATH"
          # Warn if official app arch mismatches hardware
          local app_arch
          app_arch="$(get_macos_app_arch "$CLI_APP_PATH")"
          if [[ "${ARCH_NAME}" == "arm64" && "$app_arch" == "x86_64" ]]; then
            echo "Warning: Installed VS Code appears to be Intel (x86_64) on Apple Silicon; this may run under Rosetta."
            if confirm_action "Reinstall native arm64 VS Code now?"; then
              install_official_vscode_macos || true
              set_official_vscode_cli || true
              offer_replace_system_code || true
            fi
          fi
        else
          echo "Note: 'code' CLI is provided by a different app: $CLI_APP_PATH (bundle id: ${CLI_BUNDLE_ID:-unknown})"
          echo "      Extension commands will target that app. To install official VS Code under /Applications, run with --reinstall."
          if [[ $YES -eq 0 ]]; then
            if confirm_action "Install official Visual Studio Code to /Applications now?"; then
              install_official_vscode_macos || true
              # After installation, prefer the official CLI even if PATH still resolves to another app
              set_official_vscode_cli || true
              # Optionally offer to replace /usr/local/bin/code symlink
              offer_replace_system_code || true
            fi
          fi
        fi
      elif detect_macos_app_bundle; then
        echo "VS Code app bundle: $CODE_APP_PATH"
      else
        echo "Note: VS Code CLI is present, but the official app bundle was not found."
        echo "      To install official VS Code under /Applications, run with --reinstall."
        if [[ $YES -eq 0 ]]; then
          if confirm_action "Install official Visual Studio Code to /Applications now?"; then
            install_official_vscode_macos || true
            set_official_vscode_cli || true
            offer_replace_system_code || true
          fi
        fi
      fi
    fi
  else
    echo "VS Code not detected; will attempt installation if needed."
  fi
  if [[ "$REINSTALL" -eq 1 ]]; then
    # Ensure VS Code exists or install it first
    if ! find_code_cli; then install_vscode || true; fi
    # Then try to reinstall/update VS Code
    reinstall_vscode || true
    # Refresh code CLI path
    find_code_cli || true
  fi
  install_extension
  if [[ $YES -eq 0 ]]; then
    prompt_if_needed
    echo "About to update ~/.claude with provided settings."
    if ! confirm_action "Proceed with writing ~/.claude files?"; then echo "Aborted."; exit 3; fi
  else
    if [[ -z "$TOKEN" || -z "$BASE_URL" ]]; then
      echo "Error: --token and --base-url are required in non-interactive mode." >&2; exit 2
    fi
  fi
  write_claude_files
  echo "✅ Installed extension '$EXT_ID'"
  # Summarize like install-claude.sh
  echo "   ANTHROPIC_AUTH_TOKEN=$TOKEN"
  echo "   ANTHROPIC_BASE_URL=$BASE_URL"
  if [[ -n "$CODE_CMD_RESOLVED" ]]; then echo "   VS Code CLI=$CODE_CMD_RESOLVED"; fi
  if [[ -n "$CLI_APP_PATH" ]]; then echo "   CLI Host App=$CLI_APP_PATH ($CLI_BUNDLE_ID)"; elif [[ -n "$CODE_APP_PATH" ]]; then echo "   VS Code App=$CODE_APP_PATH"; fi
  echo "✅ Configuration complete."
}

main "$@"
