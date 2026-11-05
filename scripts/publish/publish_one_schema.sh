#!/usr/bin/env bash
set -euo pipefail

proj=$1
esgvoc use "$proj@latest"
ver=$(python scripts/publish/get_schema_version.py "$proj")
echo "$proj -> $ver"

tmpdir=$(mktemp -d)
pages_dir="$tmpdir/gh-pages"
schema_file="$tmpdir/schema.json"
cleanup() {
    git worktree remove --force "$pages_dir" > /dev/null 2>&1 || true
    rm -rf "$tmpdir"
}
trap cleanup EXIT

esgvoc schema "$proj" -o "$schema_file"
git worktree add --quiet "$pages_dir" gh-pages

version_dir="$pages_dir/$proj/$ver"
if [ ! -d "$version_dir" ]; then
    mkdir -p "$version_dir"
    mv "$schema_file" "$version_dir/schema.json"
    git -C "$pages_dir" add "$proj/$ver"
    git -C "$pages_dir" commit -m "updating $proj to $ver"
elif diff -q "$schema_file" "$version_dir/schema.json" > /dev/null; then
    echo "Matching schemas $proj/$ver"
else
    echo "Schemas differ for $proj/$ver"
fi
