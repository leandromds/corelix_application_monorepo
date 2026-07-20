/**
 * Global test setup — runs before every test file.
 *
 * Responsibilities:
 * 1. Extend Vitest's expect with @testing-library/jest-dom matchers
 * 2. Stub browser APIs that jsdom does not implement (needed by Radix UI)
 */

import "@testing-library/jest-dom";

// ---------------------------------------------------------------------------
// ResizeObserver — used internally by Radix UI primitives (Select, Dialog…)
// ---------------------------------------------------------------------------

class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}

Object.defineProperty(globalThis, "ResizeObserver", {
  writable: true,
  configurable: true,
  value: ResizeObserverStub,
});

// ---------------------------------------------------------------------------
// window.matchMedia — called by some Radix animation utilities
// ---------------------------------------------------------------------------

Object.defineProperty(window, "matchMedia", {
  writable: true,
  value: vi.fn().mockImplementation((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })),
});

// ---------------------------------------------------------------------------
// window.scrollTo — jsdom stub (Radix Dialog calls this on open)
// ---------------------------------------------------------------------------

Object.defineProperty(window, "scrollTo", {
  writable: true,
  value: vi.fn(),
});

// ---------------------------------------------------------------------------
// PointerEvent — needed for @testing-library/user-event v14
// ---------------------------------------------------------------------------

if (typeof window.PointerEvent === "undefined") {
  // @ts-expect-error – jsdom does not include PointerEvent
  window.PointerEvent = class PointerEvent extends MouseEvent {
    constructor(type: string, init?: PointerEventInit) {
      super(type, init);
    }
  };
}

// ---------------------------------------------------------------------------
// jest-axe — extend expect with toHaveNoViolations
// ---------------------------------------------------------------------------

import { toHaveNoViolations } from "jest-axe";
expect.extend(toHaveNoViolations);
