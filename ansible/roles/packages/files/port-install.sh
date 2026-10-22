#!/bin/sh
# port-install.sh PORT BUILD UPGRADE
# Installs a MacPorts port, or, with UPGRADE=true, upgrades it when it is installed and outdated.
#   BUILD=false  binary archives only
#   BUILD=true   (port_build in packages.yml) the port itself may be compiled, but only after every dependency came
#                from a binary archive, so a missing archive further down never starts a long chain of builds
#   BUILD=any    MacPorts builds whatever has no archive for this macOS (the second try, for a port with no mise
#                replacement)
# Prints "is already installed" or "is up to date" when there was nothing to do.
set -eu
port=/opt/local/bin/port
name=$1 build=$2 upgrade=${3:-false}

if $port -q installed "$name" 2> /dev/null | grep -q '(active)'; then
  if [ "$upgrade" != true ]; then echo "$name is already installed"; exit 0; fi
  if [ -z "$($port -q outdated "$name" 2> /dev/null)" ]; then echo "$name is up to date"; exit 0; fi
  action=upgrade
else
  action=install
fi

if [ "$build" = any ]; then
  exec $port -N "$action" "$name"
fi
if [ "$build" = true ]; then
  deps=$($port -q echo rdepof:"$name" | awk '{print $1}')
  # shellcheck disable=SC2086  # one word per port
  [ -z "$deps" ] || $port -N -b install $deps
  # shellcheck disable=SC2086
  [ -z "$deps" ] || [ "$action" != upgrade ] || $port -N -b upgrade $deps
  exec $port -N "$action" "$name"
fi
exec $port -N -b "$action" "$name"
