/* eslint-disable @typescript-eslint/no-empty-object-type, @typescript-eslint/no-explicit-any, @typescript-eslint/no-unused-vars */
import "vitest";
import type { AxeMatchers } from "vitest-axe";

// Vitest 4 resolves custom matchers from the `vitest` module's `Assertion`
// interface (not the global `Vi` namespace that vitest-axe augments), so we
// re-apply the axe matcher types here. The empty interfaces and `<T = any>`
// signature are required to merge with vitest's own `Assertion` declaration.
// Enables `expect(...).toHaveNoViolations()`.
declare module "vitest" {
  interface Assertion<T = any> extends AxeMatchers {}
  interface AsymmetricMatchersContaining extends AxeMatchers {}
}
