import { fmtCurrency, fmtPct, fmtNum, fmtDate, fmtTime } from "./format";

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
  it("formats negative", () => {
    expect(fmtCurrency(-2_500_000)).toBe("$-2.50M");
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
});

describe("fmtNum", () => {
  it("formats with default decimals", () => {
    expect(fmtNum(1234.5678)).toMatch(/1.*234\.57/);
  });
  it("formats with custom decimals", () => {
    expect(fmtNum(3.14159, 4)).toMatch(/3\.1416/);
  });
});
