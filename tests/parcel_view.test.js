const test = require("node:test");
const assert = require("node:assert");
const { buildParcelRows } = require("../public/parcel_view.js");

const API = {
  eum: { zone_national_law: ["계획관리지역"], sgg_nm: "신안군", sgg_cd: "12840",
         jimok_code: null, area_sqm: null, source: "gis" },
  vworld: { lon: 126.123456, lat: 34.812345 },
};

function find(rows, label) {
  return rows.find((r) => r.label === label);
}

test("적재된 필지가 있으면 지목과 면적을 채운다", () => {
  const parcel = { 지목: "전", 면적_m2: 2013, 개별공시지가: 12000,
                   데이터출처: ["등기부등본"] };
  const rows = buildParcelRows(API, "전남 신안군 안좌면 마명리 152", parcel);
  assert.strictEqual(find(rows, "지목").value, "전");
  assert.strictEqual(find(rows, "면적").value, "2,013 ㎡");
  assert.strictEqual(find(rows, "지목").source, "등기부등본");
});

test("적재된 필지가 없으면 기존처럼 미제공으로 둔다", () => {
  const rows = buildParcelRows(API, "어딘가", null);
  assert.strictEqual(find(rows, "지목").value, "미제공");
  assert.strictEqual(find(rows, "면적").value, "미제공");
});

test("용도지역은 실시간 조회 값을 그대로 쓴다", () => {
  // 용도지역은 Supabase zoning(실시간)이 권위 있는 출처다. 적재된 필지의
  // 용도지역으로 덮어쓰면 오래된 값이 최신 폴리곤을 이긴다
  const parcel = { 용도지역: "보전관리지역", 데이터출처: ["등기부등본"] };
  const rows = buildParcelRows(API, "어딘가", parcel);
  assert.strictEqual(find(rows, "용도지역").value, "계획관리지역");
});

test("공시지가는 있을 때만 행을 만든다", () => {
  const rows = buildParcelRows(API, "어딘가", null);
  assert.strictEqual(find(rows, "개별공시지가"), undefined);
});

test("좌표가 없으면 하이픈", () => {
  const rows = buildParcelRows({ eum: {}, vworld: {} }, "어딘가", null);
  assert.strictEqual(find(rows, "좌표").value, "-");
});
