"use strict";

(function exposeQuantityParser(root) {
  function parseQuantityHint(captionText) {
    const candidates = String(captionText || "")
      .split(/\r?\n/)
      .map((line) => line.trim())
      .filter((line) => /^\d{1,6}(?:[.,]\d{1,3})?$/.test(line))
      .map((line) => Number(line.replace(",", ".")))
      .filter((value) => Number.isFinite(value) && value > 0);
    if (!candidates.length) return null;
    const value = candidates[candidates.length - 1];
    return Number.isInteger(value) ? value : Number(value.toFixed(3));
  }

  root.wlQuantityHint = parseQuantityHint;
  if (typeof module !== "undefined" && module.exports) {
    module.exports = { parseQuantityHint };
  }
})(typeof globalThis !== "undefined" ? globalThis : this);
