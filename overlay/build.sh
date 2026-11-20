#!/bin/bash
# Builds the overlay with the Command Line Tools swiftc already on this Mac. Installs nothing; output stays in overlay/build/.
cd "$(dirname "$0")" && mkdir -p build && swiftc -O TZOverlay.swift -o build/TZOverlay && echo "built overlay/build/TZOverlay"
