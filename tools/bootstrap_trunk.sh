#!/usr/bin/env bash

if ! command -v trunk >/dev/null; then
  echo "Trunk is not installed, bootstrapping trunk..."
  curl -fsSL https://get.trunk.io | bash
  if command -v trunk >/dev/null; then
    echo "Trunk installed successfully."
  else
    echo "Failed to install trunk. Please install manually."
    exit 1
  fi
else
  echo "Trunk is already installed, updating trunk..."
  trunk upgrade
  ret=$?
  if [[ ${ret} -eq 0 ]] || [[ ${ret} -eq 143 ]]; then
    echo "Trunk updated successfully."
  else
    echo "Failed to update trunk. Please update manually."
    exit 1
  fi
fi

exit 0
