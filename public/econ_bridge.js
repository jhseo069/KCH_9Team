// 공사비산출기로 넘길 값을 만든다.
//
// 이 계산기는 발전용량이 아니라 계통연계 선로 구간(긍장·전압·철탑 수) 중심이라,
// 부지 데이터에서 자동으로 채울 수 있는 값이 사실상 사업명뿐이다. 긍장·연계지점을
// 추정해서 넣으면 근거 없는 숫자가 보고서에 남는다 - 사람이 입력하게 둔다.
(function (root, factory) {
  if (typeof module === "object" && module.exports) module.exports = factory();
  else root.EconBridge = factory();
})(typeof self !== "undefined" ? self : this, function () {
  function buildEconContext(siteMeta) {
    const s = siteMeta || {};
    const name = s.address ? (s.address + " " + (s.project_type || "")).trim() : "";
    return { projName: name, lon: s.lon, lat: s.lat };
  }
  return { buildEconContext: buildEconContext };
});
