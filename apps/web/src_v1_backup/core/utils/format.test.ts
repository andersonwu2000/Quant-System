import { describe, it, expect } from "vitest";
import { fmtCurrency, fmtPct, fmtNum } from "./format";
import { pnlColor, pnlBg } from "./format";

describe("fmtCurrency", () => {
  it("formats millions", () => {
    expect(fmtCurrency(1_500_000)).toBe("$1.50M");
  });
  it("formats thousands", () => {
    expect(fmtCurrency(12_300)).toBe("$12.3K");
  });
  it("formats small values", () => {
    expect(fmtCurrency(42)).toBe("$42.00");
  });
  it("formats zero", () => {
    expect(fmtCurrency(0)).toBe("$0.00");
  });
  it("formats negative", () => {
    const result = fmtCurrency(-5_000);
    expect(result).toContain("5");
  });
  it("formats large millions", () => {
    const result = fmtCurrency(10_000_000);
    expect(result).toContain("10");
    expect(result).toContain("M");
  });
});

describe("fmtPct", () => {
  it("formats positive", () => {
    expect(fmtPct(0.125)).toBe("+12.50%");
  });
  it("formats negative", () => {
    expect(fmtPct(-0.03)).toBe("-3.00%");
  });
  it("formats zero", () => {
    expect(fmtPct(0)).toBe("+0.00%");
  });
  it("formats small positive", () => {
    expect(fmtPct(0.001)).toBe("+0.10%");
  });
  it("formats large positive", () => {
    expect(fmtPct(1.5)).toBe("+150.00%");
  });
});

describe("fmtNum", () => {
  it("formats with defaults", () => {
    const result = fmtNum(1234.5678);
    expect(result).toContain("1");
    expect(result).toContain("234");
  });
  it("formats zero", () => {
    const result = fmtNum(0);
    expect(result).toBe("0.00");
  });
  it("formats negative", () => {
    const result = fmtNum(-42.5);
    expect(result).toContain("42");
  });
});

describe("pnlColor", () => {
  it("returns green class for positive", () => {
    expect(pnlColor(100)).toBe("text-emerald-600 dark:text-emerald-400");
  });
  it("returns red class for negative", () => {
    expect(pnlColor(-50)).toBe("text-red-600 dark:text-red-400");
  });
  it("returns slate class for zero", () => {
    expect(pnlColor(0)).toBe("text-slate-500 dark:text-slate-400");
  });
});

describe("pnlBg", () => {
  it("returns green bg for positive", () => {
    expect(pnlBg(1)).toContain("emerald");
  });
  it("returns red bg for negative", () => {
    expect(pnlBg(-1)).toContain("red");
  });
  it("returns slate bg for zero", () => {
    expect(pnlBg(0)).toContain("slate");
  });
});
