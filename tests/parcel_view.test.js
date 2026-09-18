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

test("좌표가 부분적으로만 오면(lon만 있고 lat 누락) 하이픈 - 탭 전체가 죽으면 안 된다", () => {
  // 지오코더 부분 응답을 lon만 보고 판단하면 lat.toFixed()가 undefined에서 던져
  // 필지 탭 렌더링 전체가 실패한다. 여기서 고정해둔다.
  const rows = buildParcelRows({ eum: {}, vworld: { lon: 126.1 } }, "어딘가", null);
  assert.strictEqual(find(rows, "좌표").value, "-");
});

test("적재된 필지가 없어 eum 값으로 떨어지면 원본 그대로 보여준다(재포맷하지 않음)", () => {
  // eum.jimok_code는 코드값, eum.area_sqm은 단위/구분자 없는 raw 값이다. 이 저장소에는
  // 코드→이름 매핑표가 없어 재포맷하면 값을 지어내는 셈이 된다. 현재의 그대로-통과
  // 동작을 고정한다 - renderParcel(index.html)과 같은 동작이며 그쪽은 이 태스크 범위가
  // 아니다.
  const data = {
    eum: { zone_national_law: [], sgg_nm: null, sgg_cd: null,
           jimok_code: "02", area_sqm: 1500, source: "eum" },
    vworld: {},
  };
  const rows = buildParcelRows(data, "어딘가", null);
  assert.strictEqual(find(rows, "지목").value, "02");
  assert.strictEqual(find(rows, "면적").value, 1500);
});
