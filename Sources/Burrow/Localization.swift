import SwiftUI

/// Looks up a string that reached a view as a plain `String`.
///
/// SwiftUI localizes string *literals* in `Text`, `Button`, `Label` and friends
/// automatically, but values stored in a model or passed through a helper view
/// do not go through the localization table. Wrapping them with `L(...)` at the
/// display boundary fixes that without changing where the text comes from.
///
/// Missing entries return the original string, so paths, file names and Mole's
/// terminal output are never rewritten.
@inline(__always)
func L(_ key: String) -> LocalizedStringKey { LocalizedStringKey(key) }
