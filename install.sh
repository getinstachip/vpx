#!/bin/sh

# Portable shell script for installing VPM
# Works on any POSIX-compliant shell

debug=0
if [ "x$VPM_DEBUG" = "x" ]; then
  (exit 0)
else
  echo "running in debug mode."
  set -o xtrace
  set -o pipefail
  debug=1
fi

# Check for Python installation
python=`which python3 2>&1`
ret=$?
if [ $ret -eq 0 ] && [ -x "$python" ]; then
  if [ $debug -eq 1 ]; then
    echo "found 'python3' at: $python"
    echo -n "version: "
    $python --version
    echo ""
  fi
  (exit 0)
else
  echo "VPM cannot be installed without Python 3." >&2
  echo "Install Python 3 first, and then try again." >&2
  echo "" >&2
  exit $ret
fi

# Check for pip
pip=`which pip3 2>&1`
ret=$?
if [ $ret -eq 0 ] && [ -x "$pip" ]; then
  if [ $debug -eq 1 ]; then
    echo "found 'pip3' at: $pip"
    echo -n "version: "
    $pip --version
    echo ""
  fi
  (exit 0)
else
  echo "VPM requires pip3. Installing pip..." >&2
  curl https://bootstrap.pypa.io/get-pip.py -o get-pip.py
  $python get-pip.py --user
  rm get-pip.py
fi

# Check for git
git=`which git 2>&1`
ret=$?
if [ $ret -eq 0 ] && [ -x "$git" ]; then
  if [ $debug -eq 1 ]; then
    echo "found 'git' at: $git"
    echo -n "version: "
    $git --version
    echo ""
  fi
  (exit 0)
else
  echo "VPM requires git, please install it and try again." >&2
  exit 1
fi

# Set temp directory
TMP="${TMPDIR}"
if [ "x$TMP" = "x" ]; then
  TMP="/tmp"
fi
TMP="${TMP}/vpm.$$"
rm -rf "$TMP" || true
mkdir "$TMP"
if [ $? -ne 0 ]; then
  echo "failed to mkdir $TMP" >&2
  exit 1
fi

BACK="$PWD"

echo "Cloning VPM repository..."
cd "$TMP" \
  && git clone https://github.com/getinstachip/vpm-v2.git \
  && cd vpm-v2 \
  && echo "Installing VPM dependencies..." \
  && $pip install --user -r requirements.txt \
  && echo "Installing VPM..." \
  && $pip install --user -e . \
  && cd "$BACK" \
  && rm -rf "$TMP" \
  && echo "Successfully installed VPM"

ret=$?
if [ $ret -ne 0 ]; then
  echo "Installation failed!" >&2
fi

# Add to PATH if not already there
INSTALL_PATH="$HOME/.local/bin"
case ":$PATH:" in
  *":$INSTALL_PATH:"*) ;;
  *) echo "export PATH=\"\$PATH:$INSTALL_PATH\"" >> "$HOME/.bashrc"
     echo "export PATH=\"\$PATH:$INSTALL_PATH\"" >> "$HOME/.zshrc" 2>/dev/null || true
     echo "Please restart your terminal or run 'source ~/.bashrc' to use VPM" ;;
esac

exit $ret
