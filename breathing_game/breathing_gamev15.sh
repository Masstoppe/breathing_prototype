#!/bin/sh
printf '\033c\033]0;%s\a' breathing_game
base_path="$(dirname "$(realpath "$0")")"
"$base_path/breathing_gamev15.arm64" "$@"
