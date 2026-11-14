# Shared by the firmware build and the Swift-only preset used by CI/CubeIDE.
function(una_add_embedded_swift target object)
    find_program(SWIFTC_EXECUTABLE NAMES swiftc REQUIRED)

    file(GLOB swift_sources CONFIGURE_DEPENDS
        "${UNA_PROJECT_DIR}/Core/Swift/*.swift")
    if(NOT swift_sources)
        message(FATAL_ERROR "No Embedded Swift sources found in Core/Swift")
    endif()
    get_filename_component(object_dir "${object}" DIRECTORY)

    add_custom_command(OUTPUT "${object}"
        COMMAND "${CMAKE_COMMAND}" -E make_directory "${object_dir}"
        COMMAND "${SWIFTC_EXECUTABLE}"
            -enable-experimental-feature Embedded
            -whole-module-optimization -parse-as-library -Osize -g
            -no-allocations -module-name UnaKernelSwift
            -target armv8m.main-none-none-eabi -target-cpu cortex-m33
            -Xcc -mthumb -Xcc -mfloat-abi=hard -Xcc -mfpu=fpv5-sp-d16
            -Xcc -fshort-enums
            -Xfrontend -function-sections
            -emit-object ${swift_sources} -o "${object}"
        DEPENDS ${swift_sources} "${CMAKE_CURRENT_FUNCTION_LIST_FILE}"
        COMMENT "Compiling Embedded Swift for Cortex-M33" VERBATIM)
    add_custom_target(${target} DEPENDS "${object}")
endfunction()
