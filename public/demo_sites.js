// 시연용 부지는 좌표를 미리 저장해 둔다. 시연 당일 브이월드 지오코딩이 막혀도
// 이 경로는 좌표 변환 없이 바로 판정으로 들어가므로 화면이 비지 않는다.
(function (root, factory) {
  if (typeof module === "object" && module.exports) module.exports = factory();
  else root.DemoSites = factory();
})(typeof self !== "undefined" ? self : this, function () {
  function buildDemoQuery(site) {
    return {
      address: site.address,
      lon: site.lon,
      lat: site.lat,
      project_type: site.project_type,
      capacity_kw: site.capacity_kw === undefined ? null : site.capacity_kw,
    };
  }
  return { buildDemoQuery: buildDemoQuery };
});
