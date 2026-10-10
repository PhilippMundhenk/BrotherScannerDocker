#!/usr/bin/env bash
# shellcheck shell=bash
# Configuration file support (#124). Sourced by runScanner.sh and testable
# with bats.
#
# The file holds KEY=VALUE lines with the same names as the environment
# variables in the README. Precedence: a variable set in the container
# environment (compose file) wins over the file, the file wins over the
# built-in default. Lines starting with # and blank lines are ignored; one
# pair of surrounding double quotes is stripped from a value.

config_file_path() {
  echo "${SCANNER_CONFIG_FILE:-/scans/.config/scanner.conf}"
}

config_key_valid() {
  [[ "$1" =~ ^[A-Z][A-Z0-9_]*$ ]]
}

# record_locked_keys <file>: write the names of every variable that is set in
# the environment right now, one per line. The settings page shows these as
# read-only and the scripts never let the file override them.
record_locked_keys() {
  env | cut -d= -f1 | grep -E '^[A-Z][A-Z0-9_]*$' | sort >"$1"
}

# load_config_file <file> <locked-list>: export every valid KEY=VALUE from the
# file whose KEY is not listed in <locked-list>. Prints what it did.
load_config_file() {
  local file="$1" locked="$2" line key value loaded=0 ignored=0
  if [[ ! -r "$file" ]]; then
    echo "config: no configuration file at $file"
    return 0
  fi
  while IFS= read -r line || [[ -n "$line" ]]; do
    line="${line%$'\r'}"
    [[ -z "${line// /}" || "$line" == \#* ]] && continue
    if [[ "$line" != *=* ]]; then
      echo "config: ignoring line without '=': $line"
      continue
    fi
    key="${line%%=*}"
    value="${line#*=}"
    key="${key// /}"
    if ! config_key_valid "$key"; then
      echo "config: ignoring invalid key: $key"
      continue
    fi
    if [[ "$value" == \"*\" && ${#value} -ge 2 ]]; then
      value="${value:1:${#value}-2}"
    fi
    if [[ -r "$locked" ]] && grep -qx "$key" "$locked"; then
      echo "config: $key is set by the environment, file value ignored"
      ignored=$((ignored + 1))
      continue
    fi
    export "$key=$value"
    loaded=$((loaded + 1))
  done <"$file"
  echo "config: $loaded setting(s) loaded from $file, $ignored overridden by the environment"
}
