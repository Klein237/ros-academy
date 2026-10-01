import { expect, it } from "vitest";
import { Backoff } from "../../src/backoff";

it("double le délai jusqu'au plafond, puis repart du minimum", () => {
  const b = new Backoff(500, 4000);
  expect([b.next(), b.next(), b.next(), b.next(), b.next()]).toEqual([500, 1000, 2000, 4000, 4000]);
  b.reset();
  expect(b.next()).toBe(500);
});
