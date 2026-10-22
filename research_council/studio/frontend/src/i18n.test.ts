import { describe, it, expect } from "vitest";
import { en, vi } from "./i18n";
import { money } from "./api";
describe("local presentation contracts", () => {
  it("covers every English key in Vietnamese", () => {
    expect(Object.keys(vi).sort()).toEqual(Object.keys(en).sort());
    expect(vi.synthetic).toContain("TỔNG HỢP");
  });
  it("formats tiny research costs", () =>
    expect(money(0.00012)).toBe("$0.0001"));
});
