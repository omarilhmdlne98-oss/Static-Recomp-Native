cmake_minimum_required(VERSION 3.20)
project(StaticRecompNative VERSION 0.1.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

add_library(static_recomp_runtime STATIC
    runtime/NativeRuntime.cpp
    runtime/NativeRuntime.h
)

target_include_directories(static_recomp_runtime PUBLIC
    ${CMAKE_CURRENT_SOURCE_DIR}/runtime
    ${CMAKE_CURRENT_SOURCE_DIR}/generated_code
)

if(WIN32)
    target_compile_definitions(static_recomp_runtime PUBLIC
        WIN32_LEAN_AND_MEAN
        NOMINMAX
        UNICODE
        _UNICODE
    )
    target_link_libraries(static_recomp_runtime PUBLIC user32 gdi32)
endif()

if(MSVC)
    target_compile_options(static_recomp_runtime PRIVATE /W4 /permissive-)
else()
    target_compile_options(static_recomp_runtime PRIVATE -Wall -Wextra -Wpedantic)
endif()

add_executable(StaticRecompNative
    runtime/main.cpp
)

target_link_libraries(StaticRecompNative PRIVATE static_recomp_runtime)

if(MSVC)
    target_compile_options(StaticRecompNative PRIVATE /W4 /permissive-)
else()
    target_compile_options(StaticRecompNative PRIVATE -Wall -Wextra -Wpedantic)
endif()
