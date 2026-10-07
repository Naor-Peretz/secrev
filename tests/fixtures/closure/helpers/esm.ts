// TypeScript ESM: the specifier names the *emitted* file and the source has a
// different extension, because the compiler rewrites it and the specifier has to
// be what the runtime loads.
//
// One positive case per shape, each importing a `.js`-family path whose
// TypeScript source is what the tree actually contains. Before the rewrite every
// line below was a `missing_reference` *and* the real source never entered the
// closure — the owner measured 42 of these in one real MCP server, which is a
// TypeScript server's own code sitting silently outside the reachable set.
import { toggle } from "./toggle-subscriber-updates.js";
import { modern } from "./modern.mjs";
import { legacy } from "./legacy.cjs";
import { widget } from "./widget.jsx";

// The permit, and it is the reason the rewrite is tried *after* the literal
// path: a repository that commits its compiled output has a real `.js` on disk,
// and the import resolves to that rather than being rewritten.
import { emitted } from "./emitted.js";

export { toggle, modern, legacy, widget, emitted };
