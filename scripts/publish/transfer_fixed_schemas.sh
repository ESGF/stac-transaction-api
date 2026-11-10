#!/usr/bin/env bash
echo "Transferring fixed schemas"

tmpdir=$(mktemp -d)
pages_dir="$tmpdir/gh-pages"
schema_file="$tmpdir/schema.json"

# Detect new versions
git worktree add --quiet "$pages_dir" gh-pages

changed=0

find schemas/fixed -type f -path '*/schema.json' | while read -r schema_file; do

    # Extract element and version from:
    # schemas/fixed/<element>/<version>/schema.json
    relpath="${schema_file#schemas/fixed/}"
    element=$(dirname "$relpath" | cut -d/ -f1)
    version=$(dirname "$relpath" | cut -d/ -f2)

    target_dir="$pages_dir/$element/$version"
    target_file="$target_dir/schema.json"

    # Create versioned dir as needed
    if [ ! -d "$version_dir" ]; then
        mkdir -p "$target_dir"
    fi

    # New file
    if [ ! -f "$target_file" ]; then
        echo "Adding $element/$version"
        cp "$schema_file" "$target_file"
        changed=1
    # No change
    elif diff -q "$schema_file" "$target_file" >/dev/null; then
        echo "Matching schema $element/$version"
    else
        echo "Schema updating not allowed for a set version"
        exit 1
    fi

done

if [ "$changed" -eq 1 ]; then
    git -C "$pages_dir" add .
    git -C "$pages_dir" commit -m "Update fixed schemas"
else
    echo "No schema changes detected"
fi

