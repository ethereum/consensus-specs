#!/bin/bash
# Check that the mainnet preset + config in this repo (which contain Gnosis values)
# match the canonical source at gnosischain/specs

set -e

SPECS_BASE="https://raw.githubusercontent.com/gnosischain/specs/master/consensus"
TMPDIR=$(mktemp -d)
trap 'rm -rf "$TMPDIR"' EXIT
FAIL=0

# Strip commas between digits
normalize() {
    perl -pe 's/(?<=\d),(?=\d)//g'
}

# Extract key-value pairs (ignore comments, blanks, PRESET_BASE)
extract_kvs() {
    grep -v '^\s*#' "$1" | grep -v '^\s*$' | grep ':' | grep -v 'PRESET_BASE' | normalize | sort
}

# Check that all keys in the canonical remote file have matching values locally.
# Extra keys in local (e.g. Heze, EIP stubs) are allowed.
check_sync() {
    local local_file="$1"
    local remote_file="$2"
    local local_kvs=$(extract_kvs "$local_file")
    local remote_kvs=$(extract_kvs "$remote_file")

    # For each canonical key, check it exists with the same value locally
    while IFS= read -r line; do
        local key=$(echo "$line" | sed 's/:.*//')
        local remote_val=$(echo "$line" | sed 's/[^:]*: *//')
        local local_line=$(echo "$local_kvs" | grep "^${key}:" || true)
        if [ -z "$local_line" ]; then
            echo "  MISSING: $key (expected: $remote_val)"
            FAIL=1
        else
            local local_val=$(echo "$local_line" | sed 's/[^:]*: *//')
            if [ "$local_val" != "$remote_val" ]; then
                echo "  MISMATCH: $key: local=$local_val canonical=$remote_val"
                FAIL=1
            fi
        fi
    done <<< "$remote_kvs"
}

# Preset files that exist in canonical specs
PRESET_FILES="phase0 altair bellatrix capella deneb electra fulu"

for f in $PRESET_FILES; do
    echo "Checking presets/mainnet/$f.yaml..."
    curl -sf "$SPECS_BASE/preset/gnosis/$f.yaml" -o "$TMPDIR/$f.yaml"
    check_sync "presets/mainnet/$f.yaml" "$TMPDIR/$f.yaml"
done

echo "Checking configs/mainnet.yaml..."
curl -sf "$SPECS_BASE/config/gnosis.yaml" -o "$TMPDIR/config.yaml"
check_sync "configs/mainnet.yaml" "$TMPDIR/config.yaml"

if [ $FAIL -ne 0 ]; then
    echo "Gnosis preset/config NOT in sync with gnosischain/specs"
    exit 1
else
    echo "Gnosis preset/config in sync."
fi
