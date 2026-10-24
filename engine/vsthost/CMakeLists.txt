# D127 (proto01_animate 30 §16, AU3): loom2's own VST3 host — a sidecar on Steinberg's MIT-licensed VST 3 SDK. Built by
# scripts/build_vsthost.py (the SDK fetched at its pinned tag into engine/tools/vst3sdk, never in git), with two of the SDK's own sample
# plug-ins (again-sample-accurate, adelay) for the tests; nothing is installed or linked into the system's VST3 folders.
cmake_minimum_required(VERSION 3.25.0)

set(VST3_SDK_ROOT "${CMAKE_CURRENT_SOURCE_DIR}/../tools/vst3sdk" CACHE PATH "The VST 3 SDK checkout")
set(SMTG_ENABLE_VSTGUI_SUPPORT OFF CACHE BOOL "" FORCE)            # a host needs no plug-in GUI toolkit
set(SMTG_ENABLE_VST3_HOSTING_EXAMPLES OFF CACHE BOOL "" FORCE)
set(SMTG_ENABLE_VST3_PLUGIN_EXAMPLES ON CACHE BOOL "" FORCE)        # the test plug-ins
set(SMTG_CREATE_PLUGIN_LINK OFF CACHE BOOL "" FORCE)                 # never into C:/Program Files/Common Files/VST3
set(SMTG_RUN_VST_VALIDATOR OFF CACHE BOOL "" FORCE)
set(SMTG_USE_STATIC_CRT ON CACHE BOOL "" FORCE)                      # the sidecar stands alone

project(loom2_vsthost VERSION 1.0.0 LANGUAGES CXX)

add_subdirectory(${VST3_SDK_ROOT} ${PROJECT_BINARY_DIR}/vst3sdk)

add_executable(loom2-vsthost
    src/main.cpp
    src/host.cpp
    src/host.h
    src/editor.cpp
    src/wav.cpp
    src/wav.h
    ${VST3_SDK_ROOT}/public.sdk/source/vst/hosting/plugprovider.cpp
    ${VST3_SDK_ROOT}/public.sdk/source/vst/hosting/module_win32.cpp
    ${VST3_SDK_ROOT}/public.sdk/source/common/memorystream.cpp
)
target_compile_features(loom2-vsthost PRIVATE cxx_std_17)
set_property(TARGET loom2-vsthost PROPERTY MSVC_RUNTIME_LIBRARY "MultiThreaded$<$<CONFIG:Debug>:Debug>")   # as the SDK's libraries (SMTG_USE_STATIC_CRT)
target_compile_definitions(loom2-vsthost PRIVATE UNICODE _UNICODE NOMINMAX)
target_link_libraries(loom2-vsthost PRIVATE sdk_hosting ole32 user32 gdi32)
