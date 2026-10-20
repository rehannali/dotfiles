#!/bin/sh
# port-install.sh PORT BUILD
# Installs a MacPorts port from binary archives only. BUILD=true (port_build in packages.yml): the port itself may be
# compiled, but only after every dependency came from a binary archive, so a missing archive further down never starts
# a long chain of builds.
set -eu
port=/opt/local/bin/port
if [ "$2" = true ]; then
  deps=$($port -q echo rdepof:"$1" | awk '{print $1}')
  # shellcheck disable=SC2086  # one word per port
  [ -z "$deps" ] || $port -N -b install $deps
  exec $port -N install "$1"
fi
exec $port -N -b install "$1"
