cmake_minimum_required(VERSION 3.16)
project(prom82s123-reader VERSION 0.1.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

set(CMAKE_AUTOMOC ON)
set(CMAKE_AUTORCC ON)
set(CMAKE_AUTOUIC ON)

find_package(Qt6 REQUIRED COMPONENTS Widgets SerialPort)

if(COMMAND qt_standard_project_setup)
    qt_standard_project_setup()
endif()

# --- Embed the Arduino firmware sketch -------------------------------------
# The "Flash Firmware" feature compiles/uploads the exact sketch this GUI was
# built against, so it is baked into the binary as a generated header instead
# of being read from disk at run time (which would break once the app is
# copied elsewhere). Editing the .ino and reconfiguring regenerates it.
get_filename_component(FIRMWARE_INO_PATH
    "${CMAKE_CURRENT_SOURCE_DIR}/../arduino/82s123-reader/82s123-reader.ino" ABSOLUTE)

if(NOT EXISTS "${FIRMWARE_INO_PATH}")
    message(FATAL_ERROR "Could not find firmware sketch at ${FIRMWARE_INO_PATH}")
endif()

file(READ "${FIRMWARE_INO_PATH}" FIRMWARE_INO_CONTENT)

set(FIRMWARE_HEADER_DIR "${CMAKE_CURRENT_BINARY_DIR}/generated")
file(MAKE_DIRECTORY "${FIRMWARE_HEADER_DIR}")
configure_file(
    "${CMAKE_CURRENT_SOURCE_DIR}/src/firmware_source.h.in"
    "${FIRMWARE_HEADER_DIR}/firmware_source.h"
    @ONLY
)

# Re-run CMake's configure step whenever the sketch changes, so the embedded
# copy never goes stale.
set_property(DIRECTORY APPEND PROPERTY CMAKE_CONFIGURE_DEPENDS "${FIRMWARE_INO_PATH}")

# --- App icon ---------------------------------------------------------------
# resources/app.qrc embeds the PNGs for the in-app window/taskbar icon
# (AUTORCC compiles it automatically). On Windows, resources/app.ico is also
# baked into the .exe itself via a generated resource script, so the icon
# shows up in Explorer/taskbar/Alt-Tab even before the app runs.
set(APP_ICON_SOURCES "")
if(WIN32)
    enable_language(RC)
    configure_file(
        "${CMAKE_CURRENT_SOURCE_DIR}/resources/app.rc.in"
        "${CMAKE_CURRENT_BINARY_DIR}/app.rc"
        @ONLY
    )
    list(APPEND APP_ICON_SOURCES "${CMAKE_CURRENT_BINARY_DIR}/app.rc")
endif()

qt_add_executable(prom82s123-reader
    src/main.cpp
    src/mainwindow.cpp
    src/mainwindow.h
    src/romreader.cpp
    src/romreader.h
    src/firmwareflasher.cpp
    src/firmwareflasher.h
    resources/app.qrc
    ${APP_ICON_SOURCES}
)

target_include_directories(prom82s123-reader PRIVATE "${CMAKE_CURRENT_BINARY_DIR}")

target_link_libraries(prom82s123-reader PRIVATE Qt6::Widgets Qt6::SerialPort)

set_target_properties(prom82s123-reader PROPERTIES
    WIN32_EXECUTABLE ON
    MACOSX_BUNDLE ON
)
