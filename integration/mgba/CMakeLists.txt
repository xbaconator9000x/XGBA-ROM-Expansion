cmake_minimum_required(VERSION 3.16)
project(XGBA_R7_mGBA_core C)

# Builds the actual pinned mGBA library with an optional per-instance guest
# mailbox in its native GBA memory.c read/write path. It is not a test-only
# host-side injection wrapper. The emulator is otherwise standard.
set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)
set(BUILD_QT OFF CACHE BOOL "" FORCE)
set(BUILD_SDL OFF CACHE BOOL "" FORCE)
set(BUILD_LIBRETRO OFF CACHE BOOL "" FORCE)
set(BUILD_TEST OFF CACHE BOOL "" FORCE)
set(BUILD_STATIC ON CACHE BOOL "" FORCE)
set(BUILD_SHARED OFF CACHE BOOL "" FORCE)
set(BUILD_HEADLESS OFF CACHE BOOL "" FORCE)
set(ENABLE_SCRIPTING OFF CACHE BOOL "" FORCE)
set(BUILD_PYTHON OFF CACHE BOOL "" FORCE)
set(USE_PNG ON CACHE BOOL "" FORCE)  # R8: real framebuffer screenshot via libpng
set(USE_ZLIB OFF CACHE BOOL "" FORCE)
set(ENABLE_GDB_STUB OFF CACHE BOOL "" FORCE)

get_filename_component(XGBA_ROOT "${CMAKE_CURRENT_LIST_DIR}/../.." ABSOLUTE)
set(XGBA_MGBA_CHECKOUT "${XGBA_ROOT}/upstream/mgba"
    CACHE PATH "Pinned patched native mGBA checkout")
if(NOT EXISTS "${XGBA_MGBA_CHECKOUT}/.git")
    message(FATAL_ERROR "Pinned mGBA checkout missing")
endif()

add_subdirectory("${XGBA_MGBA_CHECKOUT}" upstream-mgba)
if(NOT TARGET mgba)
    message(FATAL_ERROR "Pinned mGBA native library target unavailable")
endif()
target_sources(mgba PRIVATE
    "${XGBA_ROOT}/integration/mgba/xgba_mgba_device.c"
    "${XGBA_ROOT}/tools/xgba_resource_mgba_adapter.c"
)
target_include_directories(mgba PRIVATE
    "${XGBA_ROOT}/integration/mgba")

add_executable(xgba-mgba-headless
    "${XGBA_ROOT}/integration/mgba/xgba_mgba_headless.c")
target_link_libraries(xgba-mgba-headless PRIVATE mgba)
get_target_property(_mgba_defs mgba COMPILE_DEFINITIONS)
if(NOT _mgba_defs)
    message(FATAL_ERROR "Pinned mGBA native compile definitions unavailable")
endif()
target_compile_definitions(xgba-mgba-headless PRIVATE ${_mgba_defs})
target_include_directories(xgba-mgba-headless PRIVATE
    "${XGBA_ROOT}/integration/mgba"
    "${XGBA_MGBA_CHECKOUT}/include"
    "${CMAKE_BINARY_DIR}/upstream-mgba/include")
install(TARGETS xgba-mgba-headless RUNTIME DESTINATION bin)
