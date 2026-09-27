cmake_minimum_required(VERSION 3.22.1)
project(s12_player LANGUAGES CXX)

if(NOT APP1_REPO_ROOT)
    get_filename_component(APP1_REPO_ROOT "${CMAKE_CURRENT_LIST_DIR}/../../../../.." ABSOLUTE)
endif()

find_package(oboe REQUIRED CONFIG)
add_subdirectory("${APP1_REPO_ROOT}/runtime/s12_core" "${CMAKE_CURRENT_BINARY_DIR}/s12_core")

add_library(player-native SHARED native_player.cpp)
target_compile_features(player-native PRIVATE cxx_std_17)
target_compile_options(player-native PRIVATE -fno-exceptions -fno-rtti -Wall -Wextra)
target_link_libraries(player-native PRIVATE s12_core oboe::oboe android log)
