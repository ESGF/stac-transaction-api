#!/usr/bin/env bash
set -euo pipefail

proj=$1
esgvoc use "$proj@latest"
ver=$(python scripts/publish/get_schema_version.py "$proj")
echo "$proj -> $ver"

branch=$(git branch --show-current)
git checkout gh-pages

mkdir -p "$proj"
pushd "$proj"

esgvoc schema "$proj" -o schema.json

if [ ! -d "$ver" ]; then
    mkdir "$ver"
    mv schema.json "$ver"
    git add "$ver"
    git commit -m "updating $proj to $ver"
else
    if diff -q schema.json "$ver/schema.json" > /dev/null; then
        echo "Matching schemas $proj/$ver"
        rm schema.json
    else
        echo "Schemas differ for $proj/$ver"
    fi
fi

popd
git checkout "$branch"
