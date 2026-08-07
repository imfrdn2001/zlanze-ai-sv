import { expect, it, vi } from "vitest";
import { generateId } from "./id";

it("creates a UUID when randomUUID is unavailable", () => {
  const original = crypto.randomUUID;
  Object.defineProperty(crypto, "randomUUID", {
    configurable: true,
    value: undefined,
  });

  expect(generateId()).toMatch(
    /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/,
  );

  Object.defineProperty(crypto, "randomUUID", {
    configurable: true,
    value: original,
  });
  vi.restoreAllMocks();
});
