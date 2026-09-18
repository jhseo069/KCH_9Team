const test = require("node:test");
const assert = require("node:assert");
const { buildEconContext } = require("../public/econ_bridge.js");

test("사업명과 좌표만 넘긴다", () => {
  const ctx = buildEconContext({ address: "전남 신안군 안좌면 마명리 152",
                                 project_type: "태양광",
                                 lon: 126.123456, lat: 34.812345 });
  assert.strictEqual(ctx.projName, "전남 신안군 안좌면 마명리 152 태양광");
  assert.strictEqual(ctx.lon, 126.123456);
});

test("계통연계 거리는 넘기지 않는다", () => {
  // 부지 데이터에 없는 값을 추정해서 넣지 않는다 (PRD FR-E2)
  const ctx = buildEconContext({ address: "a", project_type: "태양광", lon: 1, lat: 2 });
  assert.strictEqual(ctx.긍장_m, undefined);
  assert.strictEqual(ctx.계통연계거리, undefined);
});

test("주소가 없으면 사업명을 비운다", () => {
  const ctx = buildEconContext({ project_type: "태양광", lon: 1, lat: 2 });
  assert.strictEqual(ctx.projName, "");
});
