#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
project_dir="$repo_root/Software/App/UnaWatch-CubeIDE"
output="${1:-$project_dir/.embedded-swift/UnaKernelSwift.o}"
compiler="${SWIFTC:-swiftc}"

if ! command -v "$compiler" >/dev/null 2>&1; then
    echo "Embedded Swift compiler not found: $compiler" >&2
    echo "Run Software/Utilities/Scripts/build-embedded-swift.sh on the host before the CubeIDE Docker build, or set SWIFTC to a compatible swiftc." >&2
    exit 1
fi

if (( $# > 1 )); then
    sources=("${@:2}")
else
    sources=("$project_dir"/Core/Swift/*.swift)
fi
mkdir -p "$(dirname "$output")"

"$compiler" --version
echo "Compiling Embedded Swift for Cortex-M33: $output"
"$compiler" \
    -enable-experimental-feature Embedded \
    -whole-module-optimization -parse-as-library -Osize -g \
    -no-allocations -module-name UnaKernelSwift \
    -target armv8m.main-none-none-eabi -target-cpu cortex-m33 \
    -Xcc -mthumb -Xcc -mfloat-abi=hard -Xcc -mfpu=fpv5-sp-d16 \
    -Xcc -fshort-enums \
    -Xfrontend -function-sections \
    -emit-object "${sources[@]}" -o "$output"
