# Branch scope

- Target the UNA Watch's STM32U5A5 ARM Cortex-M33. Keep C/C++ and Swift compatible with its Thumb, hard-float, FPv5-SP-D16, and short-enum ABI.
- Keep changes minimal: Embedded Swift through a C-compatible interface, CubeIDE integration, and a full CMake firmware build.
- Limit edits to files already changed on this branch relative to `main`, plus this explicitly requested `AGENTS.md`.
- Keep `.project` and `.cproject` authoritative for source selection and settings. Reuse the existing startup code, libraries, linker script, and firmware packer.
- Keep the Swift compiler invocation in `cmake/EmbeddedSwift.cmake`, shared by the `firmware` and `embedded-swift` presets. Keep the initial Swift code allocation-free.
- Avoid unrelated refactors, extra build systems, architecture support, or duplicate CI jobs. Preserve the existing CI skip for the exploratory `swift` branch.
- Build Swift from source in CMake and CI; do not add a precompiled-object override. Verify build changes with both CMake presets.
