const test = require("node:test");
const assert = require("node:assert");
const {
  shouldLoadZoning, toleranceForZoom, categoryColor,
  ZONE_CATEGORIES, MIN_ZONING_ZOOM,
} = require("../public/map_utils.js");

test("줌 11 이하에서는 용도지역을 불러오지 않는다", () => {
  // 전남 전체에 폴리곤 83,660건. 그려도 뭉개져 안 보이고 브라우저만 느려진다.
  assert.strictEqual(shouldLoadZoning(9), false);
  assert.strictEqual(shouldLoadZoning(11), false);
});

test("줌 12부터 용도지역을 불러온다", () => {
  assert.strictEqual(shouldLoadZoning(12), true);
  assert.strictEqual(shouldLoadZoning(18), true);
  assert.strictEqual(MIN_ZONING_ZOOM, 12);
});

test("확대할수록 경계선을 덜 뭉뚱그린다", () => {
  const far = toleranceForZoom(12);
  const mid = toleranceForZoom(14);
  const near = toleranceForZoom(17);
  assert.ok(far > mid, "줌 12가 14보다 크게 단순화되어야 한다");
  assert.ok(mid > near, "줌 14가 17보다 크게 단순화되어야 한다");
});

test("단순화 강도는 설계서 표와 일치한다", () => {
  assert.strictEqual(toleranceForZoom(12), 0.0005);
  assert.strictEqual(toleranceForZoom(13), 0.0005);
  assert.strictEqual(toleranceForZoom(14), 0.0002);
  assert.strictEqual(toleranceForZoom(15), 0.0002);
  assert.strictEqual(toleranceForZoom(16), 0.00005);
  assert.strictEqual(toleranceForZoom(19), 0.00005);
});

test("모든 대분류가 색을 갖는다", () => {
  assert.strictEqual(ZONE_CATEGORIES.length, 7);
  for (const category of ZONE_CATEGORIES) {
    assert.match(categoryColor(category), /^#[0-9a-f]{6}$/i, category + " 색 없음");
  }
});

test("모르는 분류도 투명해지지 않고 회색으로 떨어진다", () => {
  // 색이 undefined면 Leaflet이 폴리곤을 투명하게 그려서, 사용자는 그 땅에
  // 용도지역이 없다고 오해한다. 모르는 값이 와도 반드시 보이게 한다.
  assert.match(categoryColor("존재하지않는분류"), /^#[0-9a-f]{6}$/i);
  assert.match(categoryColor(undefined), /^#[0-9a-f]{6}$/i);
});

test("관리지역과 농림·자연환경보전지역은 서로 다른 색이다", () => {
  // 전남 폴리곤의 95%가 이 둘이라 구분이 안 되면 지도가 단색이 된다.
  assert.notStrictEqual(categoryColor("관리지역"), categoryColor("농림·자연환경보전지역"));
});
