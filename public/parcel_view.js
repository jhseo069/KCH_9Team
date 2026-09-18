// 필지 탭의 표시 행을 만든다.
//
// 용도지역은 실시간 조회(Supabase zoning)가 권위 있는 출처이고, 지목·면적·공시지가는
// 사전 적재한 parcels가 유일한 출처다. 둘을 섞되 어느 쪽이 이기는지를 여기서 한 번만
// 정해둔다 - 화면 여기저기서 각자 정하면 값이 달라진다.
(function (root, factory) {
  if (typeof module === "object" && module.exports) module.exports = factory();
  else root.ParcelView = factory();
})(typeof self !== "undefined" ? self : this, function () {
  function fmtArea(v) {
    if (v === null || v === undefined || v === "") return null;
    return Number(v).toLocaleString("ko-KR") + " ㎡";
  }

  function sourceOf(parcel) {
    if (!parcel) return null;
    const s = parcel["데이터출처"] || [];
    return s.length ? s.join(", ") : null;
  }

  function buildParcelRows(data, label, parcel) {
    const eum = (data && data.eum) || {};
    const v = (data && data.vworld) || {};
    const src = sourceOf(parcel);

    const rows = [
      { label: "주소", value: label, source: null },
      { label: "용도지역",
        value: (eum.zone_national_law || []).join(", ") || "-",
        source: eum.source === "gis" ? "용도지역 DB (GIS)" : "토지이음" },
      { label: "시군구",
        value: (eum.sgg_nm || "-") + " (" + (eum.sgg_cd || "-") + ")",
        source: null },
      { label: "지목",
        value: (parcel && parcel["지목"]) || eum.jimok_code || "미제공",
        source: parcel && parcel["지목"] ? src : null },
      { label: "면적",
        value: (parcel && fmtArea(parcel["면적_m2"])) || eum.area_sqm || "미제공",
        source: parcel && parcel["면적_m2"] ? src : null },
      { label: "좌표",
        value: v.lon ? v.lon.toFixed(6) + ", " + v.lat.toFixed(6) : "-",
        source: null },
    ];

    if (parcel && parcel["개별공시지가"]) {
      rows.push({ label: "개별공시지가",
                  value: Number(parcel["개별공시지가"]).toLocaleString("ko-KR") + " 원/㎡",
                  source: src });
    }
    return rows;
  }

  return { buildParcelRows: buildParcelRows };
});
