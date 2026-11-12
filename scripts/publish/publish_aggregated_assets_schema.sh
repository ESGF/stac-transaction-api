#!/usr/bin/env bash

set -euo pipefail

echo "Generating and transferring schemas"

tmpdir=$(mktemp -d)
pages_dir="$tmpdir/gh-pages"

git worktree add --quiet "$pages_dir" gh-pages

changed=0

# Generate schemas into a temporary directory
python scripts/publish/aggregated_assets_schema.py --outdir "$tmpdir" --schemas "$pages_dir/aggregated_assets"

while read -r schema_file; do

    version=$(basename "$schema_file" .json)

    target_dir="$pages_dir/aggregated_assets/$version"
    target_file="$target_dir/schema.json"

    if [ -d "$target_dir" ]; then
        echo "Schema already exists: aggregated_assets/$version"
        continue
    fi

    echo "Adding aggregated_assets/$version"

    mkdir -p "$target_dir"
    mv "$schema_file" "$target_file"

    changed=1

done < <(find "$tmpdir" -maxdepth 1 -name '*.json')

if [ "$changed" -eq 1 ]; then
    git -C "$pages_dir" add .
    git -C "$pages_dir" commit -m "Add generated schemas"
else
    echo "No new schemas detected"
fi