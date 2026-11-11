#!/usr/bin/env bash
# XGBA R24 native CI: reproducible libpng/zlib dependency installation without
# Ubuntu package mirrors. Source pinned GitHub commits, never accept HEAD drift.
# This is a CI dependency shim; original FireRed/Emerald native tests are unchanged.
set -euo pipefail
if pkg-config --exists libpng; then
  echo "PASS_XGBA_LIBPNG_PREINSTALLED"
  exit 0
fi
test -n "${RUNNER_TEMP:-}" || { echo "RUNNER_TEMP required"; exit 1; }
root="$RUNNER_TEMP/xgba-pinned-png"
prefix="$root/installed"
mkdir -p "$root"
git clone --quiet --filter=blob:none https://github.com/madler/zlib.git "$root/zlib"
git -C "$root/zlib" checkout --quiet --detach 51b7f2abdade71cd9bb0e7a373ef2610ec6f9daf
test "$(git -C "$root/zlib" rev-parse HEAD)" = 51b7f2abdade71cd9bb0e7a373ef2610ec6f9daf
cmake -S "$root/zlib" -B "$root/zlib-build" \
  -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX="$prefix" \
  -DBUILD_SHARED_LIBS=OFF -DZLIB_BUILD_TESTING=OFF
cmake --build "$root/zlib-build" --parallel 2
cmake --install "$root/zlib-build"
test -f "$prefix/lib/libz.a"
git clone --quiet --filter=blob:none https://github.com/pnggroup/libpng.git "$root/libpng"
git -C "$root/libpng" checkout --quiet --detach ed217e3e601d8e462f7fd1e04bed43ac42212429
test "$(git -C "$root/libpng" rev-parse HEAD)" = ed217e3e601d8e462f7fd1e04bed43ac42212429
cmake -S "$root/libpng" -B "$root/png-build" \
  -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX="$prefix" \
  -DCMAKE_PREFIX_PATH="$prefix" -DPNG_SHARED=OFF -DPNG_STATIC=ON \
  -DPNG_TESTS=OFF -DPNG_EXECUTABLES=OFF \
  -DZLIB_LIBRARY="$prefix/lib/libz.a" -DZLIB_INCLUDE_DIR="$prefix/include"
cmake --build "$root/png-build" --parallel 2
cmake --install "$root/png-build"
if ! test -f "$prefix/lib/libpng.a" && ! test -f "$prefix/lib/libpng16.a"; then
  echo "::error::Pinned PNG static library missing after source build"
  exit 1
fi
# Both CMake's find_package(PNG) and pkg-config must resolve only the pinned
# source-built library after this step; persist these in all later workflow steps.
if test -n "${GITHUB_ENV:-}"; then
  printf 'CMAKE_PREFIX_PATH=%s\n' "$prefix" >>"$GITHUB_ENV"
  printf 'PKG_CONFIG_PATH=%s/lib/pkgconfig\n' "$prefix" >>"$GITHUB_ENV"
  printf 'CMAKE_LIBRARY_PATH=%s/lib\n' "$prefix" >>"$GITHUB_ENV"
  printf 'CMAKE_INCLUDE_PATH=%s/include\n' "$prefix" >>"$GITHUB_ENV"
fi
PKG_CONFIG_PATH="$prefix/lib/pkgconfig" pkg-config --exists libpng
printf 'PASS_XGBA_SOURCE_BUILT_LIBPNG zlib=1.3.1 png=1.6.43\n'
