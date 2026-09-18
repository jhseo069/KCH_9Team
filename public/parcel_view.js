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
      // parcel에 지목이 없어 eum.jimok_code로 떨어지는 경우 값을 그대로 내보낸다.
      // eum이 주는 건 코드값("02" 등)이라 사람이 읽는 이름으로 바꾸려면 코드→이름
      // 매핑표가 필요한데 이 저장소엔 없다. 없는 매핑을 지어내느니 코드 그대로
      // 보여주는 편이 "값을 지어내지 않는다"는 원칙에 맞는다. parcel 쪽(지목·면적_m2)은
      // 우리가 직접 포맷하므로 여기 해당 안 됨.
      { label: "지목",
        value: (parcel && parcel["지목"]) || eum.jimok_code || "미제공",
        source: parcel && parcel["지목"] ? src : null },
      { label: "면적",
        value: (parcel && fmtArea(parcel["면적_m2"])) || eum.area_sqm || "미제공",
        source: parcel && parcel["면적_m2"] ? src : null },
      // lon/lat 둘 다 있어야만 좌표를 보여준다. 지오코더가 부분 응답(lon만 오고 lat
      // 누락 등)을 줄 수 있는데, lon만 보고 lat.toFixed를 호출하면 TypeError로 필지
      // 탭 전체가 안 그려진다 — 외부 서비스 장애가 화면을 통째로 날리면 안 된다는
      // 원칙 위반. truthiness가 아니라 != null로 검사하는 이유: 경도/위도 0은 실제로
      // 있을 수 있는 유효한 좌표라 falsy로 버리면 안 된다.
      { label: "좌표",
        value: v.lon != null && v.lat != null
          ? v.lon.toFixed(6) + ", " + v.lat.toFixed(6) : "-",
        source: null },
    ];

    // 개별공시지가가 정말 0원인 필지는 실무상 없으므로, falsy 체크로 "값 없음"과
    // "0원"을 구분하지 않는다. 0을 구분해야 하는 사례가 실제로 나오면 그때 != null로
    // 바꾼다.
    if (parcel && parcel["개별공시지가"]) {
      rows.push({ label: "개별공시지가",
                  value: Number(parcel["개별공시지가"]).toLocaleString("ko-KR") + " 원/㎡",
                  source: src });
    }
    return rows;
  }

  return { buildParcelRows: buildParcelRows };
});
