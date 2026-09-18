const test = require("node:test");
const assert = require("node:assert");
const { buildDemoQuery } = require("../public/demo_sites.js");

test("시연 부지를 조회 파라미터로 바꾼다", () => {
  const site = { site_name: "마명리 12필지", address: "전남 신안군 안좌면 마명리 152",
                 lon: 126.123456, lat: 34.812345,
                 project_type: "태양광", capacity_kw: 3000 };
  assert.deepStrictEqual(buildDemoQuery(site), {
    address: "전남 신안군 안좌면 마명리 152",
    lon: 126.123456, lat: 34.812345,
    project_type: "태양광", capacity_kw: 3000,
  });
});

test("용량이 없으면 null로 넘긴다", () => {
  const site = { site_name: "a", address: "b", lon: 1, lat: 2,
                 project_type: "풍력", capacity_kw: null };
  assert.strictEqual(buildDemoQuery(site).capacity_kw, null);
});
