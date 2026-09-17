"""
[데이터 수집 스크립트] eum.go.kr 데이터개방에서 "(도시계획)용도지역정보" SHP 원본을 내려받는다.

이 스크립트가 존재하는 이유:
2026-09-17에 data/zoning_jeonnam.geojson에 비도시지역(관리/농림/자연환경보전)이 통째로
빠져있는 것을 발견했는데, 원본 SHP를 이미 지운 뒤라 "원본에 없었는지, 빌드가 버렸는지"를
확인할 수 없었다. 원본은 1GB라 저장소에 커밋할 수 없으므로, 대신 **받는 절차를 코드로
남겨서** 언제든 같은 원본을 다시 재현할 수 있게 한다.

사이트가 쓰는 비공개 AJAX를 그대로 따라간다(공식 공개 API가 아님, 개편 시 깨질 수 있음):
  1) svItemDet.jsp  (POST dataCd, dataTypeCd)      -> 기준일자별 파일 목록 HTML
  2) svItemAjaxXml.jsp function=selectFileInfo      -> 다운로드 key + 실제 파일명
  3) svItemAjaxXml.jsp function=insertStatInfo      -> 이용목적 통계 등록(사이트가 요구하는 절차)
  4) map.eum.go.kr:8002/OpenData/opDownloader.jsp   -> 실제 파일 스트리밍

사용 예:
  python scripts/download_zoning_shp.py                 # 최신 기준일자 SHP 내려받기
  python scripts/download_zoning_shp.py --list          # 받지 않고 목록만 보기
  python scripts/download_zoning_shp.py --file-id 663   # 특정 파일 지정
"""
import argparse
import os
import re
import sys
import xml.etree.ElementTree as ET

import requests
from bs4 import BeautifulSoup

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(BASE_DIR, "_gis_raw")

WEB = "https://www.eum.go.kr/web"
DET_URL = f"{WEB}/op/sv/svItemDet.jsp"
AJAX_URL = f"{WEB}/op/sv/svItemAjaxXml.jsp"
DOWN_BASE = "https://map.eum.go.kr:8002"

DATA_CD = "004"          # (도시계획)용도지역정보
DATA_TYPE_CD = "SHP"     # CSV는 도형(geometry)이 없어서 좌표 판정에 쓸 수 없다

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": DET_URL,
}
AJAX_HEADERS = {**HEADERS, "X-Requested-With": "XMLHttpRequest"}


def list_files(session, data_cd=DATA_CD, data_type_cd=DATA_TYPE_CD):
    """기준일자별 파일 목록을 [{file_id, ref_dt, name, size_text}] 로 돌려준다."""
    res = session.post(DET_URL, data={"dataCd": data_cd, "dataTypeCd": data_type_cd},
                       headers=HEADERS, timeout=30)
    res.encoding = "euc-kr"
    soup = BeautifulSoup(res.text, "lxml")

    rows = []
    for tr in soup.select("#fileTb tbody tr"):
        tds = [td.get_text(strip=True) for td in tr.select("td")]
        link = tr.select_one("a[onclick]")
        if link is None or len(tds) < 4:
            continue
        m = re.search(r"dataDownload\('(\d+)'\)", link.get("onclick", ""))
        if not m:
            continue
        rows.append({"file_id": m.group(1), "ref_dt": tds[1], "name": tds[2], "size_text": tds[3]})
    return rows


def get_file_info(session, file_id, data_cd=DATA_CD, data_type_cd=DATA_TYPE_CD):
    """다운로드에 필요한 key/실제 파일명/바이트 크기를 받아온다."""
    res = session.post(AJAX_URL, headers=AJAX_HEADERS, timeout=30, data={
        "function": "selectFileInfo", "dataCd": data_cd,
        "dataTypeCd": data_type_cd, "refDt": "", "fileId": file_id,
    })
    res.encoding = "euc-kr"
    payload = res.json()
    xml_text = payload.get("fileList") or ""
    if not xml_text:
        raise RuntimeError(f"파일 정보를 받지 못했습니다(빈 응답). eum.go.kr 요청 제한일 수 있습니다: {payload!r}")

    node = ET.fromstring(xml_text).find("node")
    if node is None:
        raise RuntimeError(f"파일 정보 XML에 node가 없습니다: {xml_text[:200]!r}")

    def text(tag):
        el = node.find(tag)
        return el.text if el is not None else None

    return {
        "key": text("key"),
        "file_nm": text("fileNm"),
        "file_nm_kr": text("fileNmKr"),
        "size": int(text("fileSize") or 0),
        "ref_dt": text("refDt"),
    }


def register_use_stat(session, use_type="연구목적", use_desc="용도지역 기반 부지 규제 판정 자동화",
                      data_cd=DATA_CD, data_type_cd=DATA_TYPE_CD):
    """사이트가 다운로드 전에 요구하는 '활용 목적' 등록. 실패해도 다운로드 자체는 시도한다."""
    try:
        session.post(AJAX_URL, headers=AJAX_HEADERS, timeout=30, data={
            "function": "insertStatInfo", "dataCd": data_cd, "dataTypeCd": data_type_cd,
            "useType": use_type, "useDesc": use_desc,
        })
    except Exception as e:
        print(f"  (활용목적 등록 실패, 계속 진행합니다: {e})")


def download(session, info, out_dir=OUT_DIR):
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, info["file_nm_kr"] or info["file_nm"])

    if os.path.isfile(out_path) and os.path.getsize(out_path) == info["size"]:
        print(f"이미 받아둔 파일이 있습니다(크기 일치): {out_path}")
        return out_path

    url = f"{DOWN_BASE}/OpenData/opDownloader.jsp"
    params = {"key": info["key"], "filename": info["file_nm"]}
    expected = info["size"]
    done = 0
    step = 0

    with session.get(url, params=params, headers=HEADERS, stream=True, timeout=(30, 300)) as res:
        res.raise_for_status()
        with open(out_path, "wb") as f:
            for chunk in res.iter_content(chunk_size=1024 * 1024):
                if not chunk:
                    continue
                f.write(chunk)
                done += len(chunk)
                if expected and done // (50 * 1024 * 1024) > step:
                    step = done // (50 * 1024 * 1024)
                    print(f"  {done / 1048576:.0f}MB / {expected / 1048576:.0f}MB "
                          f"({done * 100 / expected:.0f}%)", flush=True)

    actual = os.path.getsize(out_path)
    if expected and actual != expected:
        # 받다 끊긴 파일을 그대로 두면 다음 실행에서 정상 파일로 오인할 수 있다
        raise RuntimeError(f"크기 불일치: 받은 {actual} != 기대 {expected} (파일 유지: {out_path})")

    print(f"완료: {out_path} ({actual / 1048576:.1f}MB)")
    return out_path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true", help="목록만 출력하고 종료")
    ap.add_argument("--file-id", help="특정 fileId 지정(미지정 시 목록 첫 행 = 최신)")
    ap.add_argument("--out-dir", default=OUT_DIR)
    args = ap.parse_args()

    session = requests.Session()
    files = list_files(session)
    if not files:
        print("파일 목록이 비어 있습니다. eum.go.kr 요청 제한이거나 사이트가 개편된 경우입니다.")
        return 1

    print(f"기준일자별 파일 {len(files)}건 (최신순):")
    for f in files[:5]:
        print(f"  fileId={f['file_id']}  {f['ref_dt']}  {f['name']}  {f['size_text']}")
    if args.list:
        return 0

    file_id = args.file_id or files[0]["file_id"]
    print(f"\n선택: fileId={file_id}")

    info = get_file_info(session, file_id)
    print(f"  파일명: {info['file_nm_kr']}  기준일자: {info['ref_dt']}  크기: {info['size'] / 1048576:.1f}MB")

    register_use_stat(session)
    download(session, info, out_dir=args.out_dir)
    print("\n다음 단계: scripts/extract_jeonnam_shp.py 로 전남·광주(12000) 부분만 풀어낸다")
    return 0


if __name__ == "__main__":
    sys.exit(main())
