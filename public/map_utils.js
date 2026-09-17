// 지도 표시용 순수 함수. 판정에는 관여하지 않는다.
// 브라우저(<script>)와 Node 테스트(require) 양쪽에서 쓰기 위해 UMD 형태로 노출한다.
(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  else root.MapUtils = api;
})(typeof self !== "undefined" ? self : this, function () {
  // 줌 11 이하(전남 전체 조망)에서는 아예 로드하지 않는다. 8만 폴리곤을 한 화면에
  // 그리면 뭉개져서 읽을 수 없고 브라우저만 멈춘다.
  const MIN_ZONING_ZOOM = 12;

  // 단순화 강도(도 단위). 0.0001도 ~= 11m.
  // 확대할수록 작게 줘서 경계선을 정확히 보여준다.
  const TOLERANCE_BY_ZOOM = [
    { minZoom: 16, tolerance: 0.00005 },  // 필지 단위 (~5.5m)
    { minZoom: 14, tolerance: 0.0002 },   // 읍면 단위 (~22m)
    { minZoom: 12, tolerance: 0.0005 },   // 시군 단위 (~55m)
  ];

  // 국토계획법 용도지역 체계에 맞춘 6색 + 중립 회색.
  // 위성사진 위에 얹히므로 채도가 높고 서로 명도가 충분히 다른 색을 고른다.
  const CATEGORY_COLORS = {
    "주거지역": "#e8913a",
    "상업지역": "#d6455d",
    "공업지역": "#8a5bd6",
    "녹지지역": "#4ba35a",
    "관리지역": "#2f8fd0",
    "농림·자연환경보전지역": "#1d6b52",
    "미분류": "#8a8f98",
  };
  const FALLBACK_COLOR = "#8a8f98";
  const ZONE_CATEGORIES = Object.keys(CATEGORY_COLORS);

  function shouldLoadZoning(zoom) {
    return zoom >= MIN_ZONING_ZOOM;
  }

  function toleranceForZoom(zoom) {
    for (const step of TOLERANCE_BY_ZOOM) {
      if (zoom >= step.minZoom) return step.tolerance;
    }
    return TOLERANCE_BY_ZOOM[TOLERANCE_BY_ZOOM.length - 1].tolerance;
  }

  function categoryColor(category) {
    return CATEGORY_COLORS[category] || FALLBACK_COLOR;
  }

  return {
    MIN_ZONING_ZOOM, ZONE_CATEGORIES,
    shouldLoadZoning, toleranceForZoom, categoryColor,
  };
});
