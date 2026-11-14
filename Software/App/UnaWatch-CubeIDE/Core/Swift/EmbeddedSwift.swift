// Compiled for Cortex-M33 in Embedded Swift mode and linked by the C++ build.
// Keep exported interfaces C-compatible; declarations live in EmbeddedSwift.h.
@_cdecl("una_swift_add")
public func unaSwiftAdd(_ lhs: UInt32, _ rhs: UInt32) -> UInt32 {
    lhs &+ rhs
}
