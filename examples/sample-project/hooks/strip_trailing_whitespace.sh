#!/usr/bin/env bash
set -u

changed=0
for f in "$@"; do
  before="$(cat "$f")"
  sed -i 's/[ \t]*$//' "$f"
  after="$(cat "$f")"
  if [ "$before" != "$after" ]; then
    echo "- files were modified by this hook"
    echo "  fixed: $f"
    changed=1
  fi
done

exit "$changed"
