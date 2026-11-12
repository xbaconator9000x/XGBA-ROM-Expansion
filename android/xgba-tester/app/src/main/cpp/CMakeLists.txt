cmake_minimum_required(VERSION 3.22)
project(xgba_android_tester C)
set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)

# mGBA and XGBA revision match the exact pinned native CI runtime.
set(BUILD_QT OFF CACHE BOOL "" FORCE)
set(BUILD_SDL OFF CACHE BOOL "" FORCE)
set(BUILD_LIBRETRO OFF CACHE BOOL "" FORCE)
set(BUILD_TEST OFF CACHE BOOL "" FORCE)
set(BUILD_STATIC ON CACHE BOOL "" FORCE)
set(BUILD_SHARED OFF CACHE BOOL "" FORCE)
set(BUILD_HEADLESS OFF CACHE BOOL "" FORCE)
set(ENABLE_SCRIPTING OFF CACHE BOOL "" FORCE)
set(BUILD_PYTHON OFF CACHE BOOL "" FORCE)
set(BUILD_GL OFF CACHE BOOL "" FORCE)
set(BUILD_GLES2 OFF CACHE BOOL "" FORCE)
set(BUILD_GLES3 OFF CACHE BOOL "" FORCE)
set(USE_PNG OFF CACHE BOOL "" FORCE)
set(USE_ZLIB OFF CACHE BOOL "" FORCE)
set(ENABLE_GDB_STUB OFF CACHE BOOL "" FORCE)
set(ENABLE_VFS ON CACHE BOOL "" FORCE)

get_filename_component(XGBA_ROOT "${CMAKE_CURRENT_LIST_DIR}/../../../../../.." ABSOLUTE)
set(MGBA_ROOT "${XGBA_ROOT}/upstream/mgba")
if(NOT EXISTS "${MGBA_ROOT}/.git")
    message(FATAL_ERROR "Pinned mGBA source checkout must exist at upstream/mgba")
endif()
add_subdirectory("${MGBA_ROOT}" "${CMAKE_BINARY_DIR}/upstream-mgba")
if(NOT TARGET mgba)
    message(FATAL_ERROR "mGBA native core missing")
endif()
target_sources(mgba PRIVATE
    "${XGBA_ROOT}/integration/mgba/xgba_mgba_device.c"
    "${XGBA_ROOT}/tools/xgba_resource_mgba_adapter.c")
target_include_directories(mgba PRIVATE "${XGBA_ROOT}/integration/mgba")

add_library(xgba SHARED "${CMAKE_CURRENT_LIST_DIR}/xgba_android_jni.c")
get_target_property(_mgba_defs mgba COMPILE_DEFINITIONS)
if(NOT _mgba_defs)
    message(FATAL_ERROR "Original mGBA core compile definitions missing")
endif()
target_compile_definitions(xgba PRIVATE ${_mgba_defs})
target_include_directories(xgba PRIVATE
    "${XGBA_ROOT}/integration/mgba"
    "${MGBA_ROOT}/include"
    "${CMAKE_BINARY_DIR}/upstream-mgba/include")
find_library(ANDROID_LOG log)
target_link_libraries(xgba PRIVATE mgba ${ANDROID_LOG})
