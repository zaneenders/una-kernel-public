cmake_minimum_required(VERSION 3.21)
project(UnaWatch-Kernel LANGUAGES NONE)

set(CMAKE_EXPORT_COMPILE_COMMANDS ON)
set(UNA_PROJECT_DIR "${CMAKE_CURRENT_SOURCE_DIR}/Software/App/UnaWatch-CubeIDE")
set(UNA_SDK "${CMAKE_CURRENT_SOURCE_DIR}/SDK")

include(cmake/EmbeddedSwift.cmake)
option(UNA_SWIFT_ONLY "Configure only the Embedded Swift object target" OFF)
if(UNA_SWIFT_ONLY)
    una_add_embedded_swift(embedded-swift "${CMAKE_CURRENT_BINARY_DIR}/UnaKernelSwift.o")
    return()
endif()
enable_language(C CXX ASM)

# Prefer the project's optional Python environment for the firmware packer.
if(NOT DEFINED Python3_EXECUTABLE AND EXISTS "${CMAKE_CURRENT_SOURCE_DIR}/.venv/bin/python3")
    set(Python3_EXECUTABLE "${CMAKE_CURRENT_SOURCE_DIR}/.venv/bin/python3")
endif()
find_package(Python3 REQUIRED COMPONENTS Interpreter)
execute_process(COMMAND "${Python3_EXECUTABLE}" -c "import bincopy"
    RESULT_VARIABLE packer_dependencies OUTPUT_QUIET ERROR_QUIET)
if(NOT packer_dependencies EQUAL 0)
    message(FATAL_ERROR "The firmware packer needs bincopy. Install cmake/requirements.txt into a Python environment and set Python3_EXECUTABLE to its python3.")
endif()

# Read build metadata directly; CubeIDE itself is not invoked.
set_property(DIRECTORY APPEND PROPERTY CMAKE_CONFIGURE_DEPENDS
    "${UNA_PROJECT_DIR}/.project" "${UNA_PROJECT_DIR}/.cproject"
    "${CMAKE_CURRENT_SOURCE_DIR}/cmake/import_cube_project.py")
execute_process(COMMAND "${Python3_EXECUTABLE}"
    "${CMAKE_CURRENT_SOURCE_DIR}/cmake/import_cube_project.py"
    "${UNA_PROJECT_DIR}" "${CMAKE_CURRENT_BINARY_DIR}/CubeProject.cmake"
    COMMAND_ERROR_IS_FATAL ANY)
include("${CMAKE_CURRENT_BINARY_DIR}/CubeProject.cmake")
foreach(folder IN LISTS UNA_CUBE_SCAN_ROOTS)
    file(GLOB_RECURSE source_scan CONFIGURE_DEPENDS
        "${folder}/*.c" "${folder}/*.cpp" "${folder}/*.s" "${folder}/*.S")
endforeach()

set(BUILD_VERSION "" CACHE STRING "Firmware version; defaults to git describe")
if(BUILD_VERSION STREQUAL "")
    find_program(BASH_EXECUTABLE bash REQUIRED)
    execute_process(COMMAND "${BASH_EXECUTABLE}"
        "${UNA_SDK}/Utilities/Scripts/build-cube/una-version.sh" "${UNA_PROJECT_DIR}"
        WORKING_DIRECTORY "${CMAKE_CURRENT_SOURCE_DIR}"
        OUTPUT_VARIABLE version_output ERROR_VARIABLE version_log
        COMMAND_ERROR_IS_FATAL ANY)
    string(REGEX MATCH "BUILD_VERSION=([^\n\r]+)" version_match "${version_output}")
    if(NOT version_match)
        message(FATAL_ERROR "Could not determine firmware version: ${version_log}")
    endif()
    set(UNA_BUILD_VERSION "${CMAKE_MATCH_1}")
else()
    set(UNA_BUILD_VERSION "${BUILD_VERSION}")
endif()
message(STATUS "Firmware version: ${UNA_BUILD_VERSION}")

set(UNA_CPU_FLAGS -mcpu=cortex-m33 -mthumb -mfpu=fpv5-sp-d16 -mfloat-abi=hard)
execute_process(COMMAND "${CMAKE_C_COMPILER}" -print-file-name=standard_c_nano_cpp.specs
    OUTPUT_VARIABLE runtime_specs OUTPUT_STRIP_TRAILING_WHITESPACE
    COMMAND_ERROR_IS_FATAL ANY)
if(NOT EXISTS "${runtime_specs}")
    message(FATAL_ERROR "Use the GNU Tools for STM32 compiler from STM32CubeCLT or CubeIDE; standard_c_nano_cpp.specs was not found.")
endif()

# A prepared ARM object can be supplied by CI. Otherwise CMake builds Swift
# automatically, with its normal dependency tracking and clean behavior.
set(UNA_SWIFT_OBJECT "" CACHE FILEPATH "Optional precompiled Embedded Swift ARM object")
if(UNA_SWIFT_OBJECT STREQUAL "")
    set(UNA_SWIFT_OBJECT "${CMAKE_CURRENT_BINARY_DIR}/Swift/UnaKernelSwift.o")
    una_add_embedded_swift(embedded-swift "${UNA_SWIFT_OBJECT}")
elseif(NOT EXISTS "${UNA_SWIFT_OBJECT}")
    message(FATAL_ERROR "UNA_SWIFT_OBJECT does not exist: ${UNA_SWIFT_OBJECT}")
endif()
set_source_files_properties("${UNA_SWIFT_OBJECT}" PROPERTIES EXTERNAL_OBJECT TRUE)

add_executable(UnaWatch-Kernel ${UNA_CUBE_SOURCES} "${UNA_SWIFT_OBJECT}")
if(TARGET embedded-swift)
    add_dependencies(UnaWatch-Kernel embedded-swift)
endif()
set_target_properties(UnaWatch-Kernel PROPERTIES SUFFIX ".elf"
    C_STANDARD 17 C_STANDARD_REQUIRED YES C_EXTENSIONS NO
    CXX_STANDARD 17 CXX_STANDARD_REQUIRED YES CXX_EXTENSIONS YES)
target_include_directories(UnaWatch-Kernel PRIVATE
    "$<$<COMPILE_LANGUAGE:C>:${UNA_CUBE_C_INCLUDES}>"
    "$<$<COMPILE_LANGUAGE:CXX>:${UNA_CUBE_CXX_INCLUDES}>"
    "$<$<COMPILE_LANGUAGE:ASM>:${UNA_PROJECT_DIR}/Core/Inc>")
target_compile_definitions(UnaWatch-Kernel PRIVATE
    "$<$<COMPILE_LANGUAGE:C>:${UNA_CUBE_C_DEFINES}>"
    "$<$<COMPILE_LANGUAGE:CXX>:${UNA_CUBE_CXX_DEFINES}>"
    "$<$<COMPILE_LANGUAGE:ASM>:DEBUG>"
    "BUILD_VERSION=\"${UNA_BUILD_VERSION}\"" "PROJECT_NAME=\"UNA Watch\"")
target_compile_options(UnaWatch-Kernel PRIVATE ${UNA_CPU_FLAGS} -g3
    "--specs=${runtime_specs}"
    "$<$<COMPILE_LANGUAGE:C,CXX>:-Os;-UNDEBUG;-ffunction-sections;-fdata-sections;-Wall;-fstack-usage;-fcyclomatic-complexity;-fmacro-prefix-map=${CMAKE_CURRENT_SOURCE_DIR}/=>"
    "$<$<COMPILE_LANGUAGE:CXX>:-fno-exceptions;-fno-rtti;-fno-use-cxa-atexit;-Wno-psabi>"
    "$<$<COMPILE_LANGUAGE:ASM>:-x;assembler-with-cpp>")

set(linker_script "${UNA_PROJECT_DIR}/STM32U5A5QJIXQ_FLASH.ld")
target_link_directories(UnaWatch-Kernel PRIVATE
    "${CMAKE_CURRENT_SOURCE_DIR}/Software/ThirdParty/VendorLib/lib"
    "${CMAKE_CURRENT_SOURCE_DIR}/Software/App/TouchGFX-GUI/touchgfx/lib/core/cortex_m33/gcc"
    "${UNA_SDK}/Libs/Source/AppSystem/linker"
    "${CMAKE_CURRENT_SOURCE_DIR}/Software/Utilities/Scripts/linker")
target_link_options(UnaWatch-Kernel PRIVATE ${UNA_CPU_FLAGS}
    "--specs=${runtime_specs}" "-T${linker_script}"
    -static -nostartfiles -nodefaultlibs -nostdlib
    "-Wl,-Map=${CMAKE_CURRENT_BINARY_DIR}/UnaWatch-Kernel.map"
    -Wl,--gc-sections -Wl,-z,noexecstack
    -Wl,--wrap=malloc -Wl,--wrap=_malloc_r -Wl,--wrap=_free_r)
target_link_libraries(UnaWatch-Kernel PRIVATE :libstdc++.a :libtouchgfx-float-abi-hard.a una_vendor)
set_property(TARGET UnaWatch-Kernel APPEND PROPERTY LINK_DEPENDS
    "${linker_script}"
    "${CMAKE_CURRENT_SOURCE_DIR}/Software/Utilities/Scripts/linker/libc_exports_kernel_0.0.3.ld"
    "${UNA_SDK}/Libs/Source/AppSystem/linker/LibC/libc_exports_0.0.3.ld")

set(packed_images
    "${CMAKE_CURRENT_BINARY_DIR}/UnaWatch-Kernel.bin"
    "${CMAKE_CURRENT_BINARY_DIR}/UnaWatch-Kernel.hex"
    "${CMAKE_CURRENT_BINARY_DIR}/Exe/UnaWatch-Kernel_${UNA_BUILD_VERSION}.hex"
    "${CMAKE_CURRENT_BINARY_DIR}/Exe/UnaWatch-Kernel_${UNA_BUILD_VERSION}.ota"
    "${CMAKE_CURRENT_BINARY_DIR}/Exe/UnaWatch-Kernel_${UNA_BUILD_VERSION}.gld")
file(GLOB bootloader_images "${CMAKE_CURRENT_SOURCE_DIR}/una-bootloader/Exe/*.hex")
file(GLOB libc_images "${CMAKE_CURRENT_SOURCE_DIR}/una-libs/Exe/*.hex")
add_custom_command(OUTPUT ${packed_images}
    COMMAND "${CMAKE_OBJCOPY}" -O binary "$<TARGET_FILE:UnaWatch-Kernel>" "${CMAKE_CURRENT_BINARY_DIR}/UnaWatch-Kernel.bin"
    COMMAND "${CMAKE_OBJCOPY}" -O ihex "$<TARGET_FILE:UnaWatch-Kernel>" "${CMAKE_CURRENT_BINARY_DIR}/UnaWatch-Kernel.hex"
    COMMAND "${Python3_EXECUTABLE}" "${CMAKE_CURRENT_SOURCE_DIR}/Software/Utilities/Scripts/firmware_packer/post_build.py"
        -n UnaWatch-Kernel -v "${UNA_BUILD_VERSION}" -d "${CMAKE_CURRENT_BINARY_DIR}"
        -o "${CMAKE_CURRENT_BINARY_DIR}/Exe" -m 2
    COMMAND "${CMAKE_SIZE}" "$<TARGET_FILE:UnaWatch-Kernel>"
    DEPENDS UnaWatch-Kernel ${bootloader_images} ${libc_images}
        "${CMAKE_CURRENT_SOURCE_DIR}/una-bootloader/Software/Keys/SecurityKeys.pem"
        "${CMAKE_CURRENT_SOURCE_DIR}/Software/Utilities/Scripts/firmware_packer/post_build.py"
        "${CMAKE_CURRENT_SOURCE_DIR}/Software/Utilities/Scripts/firmware_packer/encrypt_firmware.py"
    WORKING_DIRECTORY "${CMAKE_CURRENT_SOURCE_DIR}"
    COMMENT "Packing HEX, OTA and factory images" VERBATIM)
add_custom_target(firmware-images ALL DEPENDS ${packed_images})
