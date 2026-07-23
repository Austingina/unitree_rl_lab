cmake_minimum_required(VERSION 3.12)
project(g1_29dof_controller)

# Declared as CACHE so `cmake -DONNXRUNTIME_ROOT=...` is always a known option (no "unused variable" warning).
set(ONNXRUNTIME_ROOT "" CACHE PATH
  "ONNX Runtime root (include/ and lib/). Empty: x64 uses repo thirdparty; aarch64 defaults to ~/unitree/onnxruntime-linux-aarch64-1.23.1")

set(CMAKE_CXX_STANDARD 17)

find_package(Boost REQUIRED COMPONENTS program_options)
find_package(yaml-cpp REQUIRED)

# ONNX Runtime: x64 uses bundled thirdparty; ARM64 uses aarch64 tarball (see doc).
# Some board images report CMAKE_SYSTEM_PROCESSOR oddly; fall back to `uname -m`.
string(TOLOWER "${CMAKE_SYSTEM_PROCESSOR}" _ort_cpu)
if(_ort_cpu STREQUAL "" OR _ort_cpu STREQUAL "unknown")
  execute_process(
    COMMAND uname -m
    OUTPUT_VARIABLE _ort_uname_m
    OUTPUT_STRIP_TRAILING_WHITESPACE
    ERROR_QUIET
  )
  string(TOLOWER "${_ort_uname_m}" _ort_cpu)
endif()
set(_ORT_ARM64 FALSE)
if(_ort_cpu MATCHES "^(aarch64|arm64|armv8)")
  set(_ORT_ARM64 TRUE)
endif()
message(STATUS "ORT host cpu: CMAKE_SYSTEM_PROCESSOR=${CMAKE_SYSTEM_PROCESSOR} -> ${_ort_cpu} (arm64=${_ORT_ARM64})")

# Override: cmake .. -DONNXRUNTIME_ROOT=/home/unitree/onnxruntime-linux-aarch64-1.23.1  (leading / required)
if(_ORT_ARM64)
  if(NOT ONNXRUNTIME_ROOT)
    set(ONNXRUNTIME_ROOT "$ENV{HOME}/unitree/onnxruntime-linux-aarch64-1.23.1")
  endif()
else()
  if(NOT ONNXRUNTIME_ROOT)
    set(ONNXRUNTIME_ROOT "${CMAKE_CURRENT_SOURCE_DIR}/../../thirdparty/onnxruntime-linux-x64-1.22.0")
  endif()
endif()

if(NOT EXISTS "${ONNXRUNTIME_ROOT}/include/onnxruntime_cxx_api.h")
  message(FATAL_ERROR
    "ONNX Runtime not found at:\n  ${ONNXRUNTIME_ROOT}\n"
    "Expected: ${ONNXRUNTIME_ROOT}/include/onnxruntime_cxx_api.h\n"
    "aarch64: if you ran 'cd ~/unitree' then tar xf, root is usually:\n"
    "  $ENV{HOME}/unitree/onnxruntime-linux-aarch64-1.23.1\n"
    "(not $ENV{HOME}/onnxruntime-... — note the extra 'unitree' segment.)\n"
    "Find on device: find \"$ENV{HOME}\" -name onnxruntime_cxx_api.h 2>/dev/null\n"
    "x86_64: ensure thirdparty/onnxruntime-linux-x64-1.22.0 exists.")
endif()

file(GLOB _ort_libs "${ONNXRUNTIME_ROOT}/lib/libonnxruntime.so*")
if(NOT _ort_libs)
  file(GLOB _ort_libs "${ONNXRUNTIME_ROOT}/lib64/libonnxruntime.so*")
endif()
if(NOT _ort_libs)
  message(FATAL_ERROR "No libonnxruntime.so* under ${ONNXRUNTIME_ROOT}/lib or .../lib64")
endif()
list(GET _ort_libs 0 ONNXRUNTIME_LIB)

message(STATUS "ONNXRUNTIME_ROOT=${ONNXRUNTIME_ROOT}")
message(STATUS "ONNXRUNTIME_LIB=${ONNXRUNTIME_LIB}")

include_directories(
  /usr/include/eigen3
  /usr/local/include
  /usr/local/include/ddscxx # dds
  /usr/local/include/iceoryx/v2.0.2 # dds
  include
  ${ONNXRUNTIME_ROOT}/include
  ${CMAKE_CURRENT_SOURCE_DIR}/../../include/
)
link_libraries(
  unitree_sdk2
  /usr/local/lib/libddscxx.so
  /usr/local/lib/libddsc.so
  rt pthread
  libboost_program_options.a libyaml-cpp.a fmt
  ${ONNXRUNTIME_LIB}
)

file(GLOB_RECURSE ADD_SRC_LIST
  ${CMAKE_CURRENT_SOURCE_DIR}/src/*.cpp
)

add_library(${PROJECT_NAME}_lib ${ADD_SRC_LIST})
link_libraries(${PROJECT_NAME}_lib)

add_executable(g1_ctrl main.cpp)
target_link_libraries(g1_ctrl PRIVATE
  g1_29dof_controller_lib
  unitree_sdk2
  /usr/local/lib/libddscxx.so
  /usr/local/lib/libddsc.so
  rt
  pthread
  boost_program_options
  yaml-cpp
  fmt
  ${ONNXRUNTIME_LIB}
)
