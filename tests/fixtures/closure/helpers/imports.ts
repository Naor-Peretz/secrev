// An import specifier that is not relative is a package, not a missing file.
//
// The first two resolve out of a dependency directory the walk excludes by name,
// so reporting them as paths the artifact does not contain would be reporting
// dependency resolution as a hole in the artifact — and FR-0.3 puts dependency
// behaviour out of scope by default. The owner found the first shape as the
// commonest false positive in a real TypeScript target.
import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { Tool } from "@modelcontextprotocol/sdk/types.js";

// The permit, and the reason the rule tests the specifier rather than the line:
// a relative specifier is exactly the progressive-load shape the closure exists
// to follow, so it stays a reference and resolves to a member.
import { helper } from "./local.ts";

export { Server, Tool, helper };
