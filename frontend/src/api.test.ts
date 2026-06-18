import { describe, expect, it } from "vitest";
import { daysSince, fmtMoney, fmtPct, fmtTime } from "./api";

describe("formatting helpers", () => {
  it("fmtPct uses a real minus sign and magnitude only", () => {
    expect(fmtPct(0.012)).toBe("+1.2%");
    expect(fmtPct(-0.008)).toBe("−0.8%");
  });

  it("fmtMoney treats gain and loss the same way (sober)", () => {
    expect(fmtMoney(24.4)).toBe("+$24.40");
    expect(fmtMoney(-61.2)).toBe("−$61.20");
  });

  it("fmtTime trims ISO to minutes", () => {
    expect(fmtTime("2024-01-15T14:30:00")).toBe("2024-01-15 14:30");
  });

  it("daysSince is never negative and counts whole days", () => {
    const now = new Date("2024-01-17T16:00:00");
    expect(daysSince("2024-01-12", now)).toBe(5);
    expect(daysSince("2024-01-20", now)).toBe(0); // future -> clamped
  });
});
