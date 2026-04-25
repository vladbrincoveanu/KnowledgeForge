#!/bin/bash
# scripts/clone_airbyte.sh
set -e
AIRBYTE_TAG="v0.63.1"  # pinned release tag
TARGET_DIR="$(dirname "$0")/../sources/demo/airbyte"

if [ -d "$TARGET_DIR/.git" ]; then
    echo "Airbyte fixture already exists at $TARGET_DIR"
    exit 0
fi

git clone --depth 1 --branch "$AIRBYTE_TAG" https://github.com/airbytehq/airbyte.git "$TARGET_DIR"
echo "Airbyte $AIRBYTE_TAG cloned to $TARGET_DIR"