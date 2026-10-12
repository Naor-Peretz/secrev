// The target of the relative import in imports.ts, so that the permit half of
// the specifier rule has something to resolve to. A rule that only refuses
// passes by refusing everything.
export const helper = (name: string): string => name;
