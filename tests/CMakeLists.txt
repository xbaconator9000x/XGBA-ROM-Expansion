cmake_minimum_required(VERSION 3.16)
project(XGBA_Pinned_Native_mGBA_Matrix_Boundary C)
set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)
enable_testing()

# Build exact unchanged pinned mGBA and keep XGBA probe external to emulator.
set(BUILD_QT OFF CACHE BOOL "" FORCE)
set(BUILD_SDL OFF CACHE BOOL "" FORCE)
set(BUILD_LIBRETRO OFF CACHE BOOL "" FORCE)
set(BUILD_TEST OFF CACHE BOOL "" FORCE)
set(BUILD_STATIC ON CACHE BOOL "" FORCE)
set(BUILD_SHARED OFF CACHE BOOL "" FORCE)
set(BUILD_HEADLESS OFF CACHE BOOL "" FORCE)
set(ENABLE_SCRIPTING OFF CACHE BOOL "" FORCE)
set(BUILD_PYTHON OFF CACHE BOOL "" FORCE)
set(USE_PNG OFF CACHE BOOL "" FORCE)
set(USE_ZLIB OFF CACHE BOOL "" FORCE)
set(ENABLE_GDB_STUB OFF CACHE BOOL "" FORCE)

set(PINNED_MGBA_ROOT "${CMAKE_CURRENT_SOURCE_DIR}/../upstream/mgba")
if(NOT EXISTS "${PINNED_MGBA_ROOT}/src/gba/cart/matrix.c")
    message(FATAL_ERROR "Clone pinned mGBA into upstream/mgba before configuring")
endif()
add_subdirectory("${PINNED_MGBA_ROOT}" "${CMAKE_BINARY_DIR}/pinned-mgba")
add_executable(xgba_mgba_bank_boundary "${CMAKE_CURRENT_SOURCE_DIR}/mgba_bank_boundary.c")
target_link_libraries(xgba_mgba_bank_boundary PRIVATE mgba)
# mGBA exposes layout-changing definitions such as ENABLE_VFS and
# ENABLE_DEBUGGERS as private target definitions. Internal structs differ
# between configurations; the test MUST inherit the same definitions
# instead of guessing the host's feature toggles.
get_target_property(_mgba_compile_defs mgba COMPILE_DEFINITIONS)
if(NOT _mgba_compile_defs)
  message(FATAL_ERROR "Pinned mGBA target has no compiler definitions; unsafe ABI")
endif()
target_compile_definitions(xgba_mgba_bank_boundary PRIVATE ${_mgba_compile_defs})
target_include_directories(xgba_mgba_bank_boundary PRIVATE
  "${PINNED_MGBA_ROOT}/include" "${CMAKE_BINARY_DIR}/pinned-mgba/include")
add_test(NAME xgba_mgba_bank_boundary COMMAND xgba_mgba_bank_boundary)
