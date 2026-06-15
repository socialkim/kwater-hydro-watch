# -*- coding: utf-8 -*-
"""
K-water 수문(水文) 브리핑 MCP 서버 v2 (강의 시연용)
═══════════════════════════════════════════════════════════
김덕진 소장 × Claude 공동 제작 | 2026.06

데이터 출처
  - 한강홍수통제소(HRFCO) Open API : 댐·하천수위·강수량 실측
  - Open-Meteo                      : 강수 예보·현재 기상 (키 불필요)

────────────────────────────────────────────────────────────
[인증키 발급 안내]
  HRFCO Open API 인증키는 아래에서 무료 발급합니다.
    https://www.hrfco.go.kr/web/openapiPage/certifyKey.do
  발급 후 환경변수 HRFCO_API_KEY 에 넣어 주세요.
    - Windows : setx HRFCO_API_KEY "발급받은-키"
    - mac/Linux: export HRFCO_API_KEY="발급받은-키"
  미설정 시에는 한국 PC에서 실제 호출로 검증된 '데모 공개키'를
  기본값으로 사용합니다(요청량 제한이 있을 수 있어 운영용으로는
  반드시 본인 키 발급을 권장합니다).
────────────────────────────────────────────────────────────

제공 도구 (9종)
  [A] 키 불필요 — Open-Meteo
    1. rain_forecast(place, days)          강수 예보
    2. weather_now(place)                  현재 기상 실황
  [B] HRFCO — 댐
    3. dam_observatory(keyword)            댐 관측소 검색
    4. dam_status(obs_code, hours_back)    댐 수위·유입·방류 + 위험도 판정
  [C] HRFCO — 하천 수위
    5. waterlevel_observatory(keyword)     수위관측소 검색
    6. waterlevel_status(obs_code, ...)    수위·유량 + 주의/경계/경보/심각 단계
  [D] HRFCO — 강수량
    7. rainfall_observatory(keyword)       강수량관측소 검색
    8. rainfall_status(obs_code, ...)      강수량 시계열 + 누적
  [E] 종합
    9. flood_briefing(dam_name)            ★ 킬러 도구: 관측소검색→수문데이터→
                                              유역 강수예보를 한 번에 종합 브리핑
"""
import os
import json
import time
import gzip
import urllib.request
import urllib.error
from datetime import datetime, timedelta

from fastmcp import FastMCP

mcp = FastMCP("kwater-hydro")

# ══════════════════════════════════════════════════════════
# 설정
# ══════════════════════════════════════════════════════════

# 한국 PC에서 실제 호출로 검증된 데모 공개키. 운영 시 본인 키로 교체 권장.
_DEMO_KEY = "9A3A6678-2E77-43F0-841B-F2368978107B"
HRFCO_API_KEY = os.environ.get("HRFCO_API_KEY", "").strip() or _DEMO_KEY
# https 사용: 대용량 목록(waterlevel/rainfall info.json)이 http에서는
# 간헐적으로 연결 리셋되지만 https에서는 안정적으로 전송된다(검증 완료).
HRFCO_BASE = "https://api.hrfco.go.kr"

_HTTP_TIMEOUT = 30      # 초
_HTTP_RETRIES = 4       # ConnectionReset 등 일시 오류 재시도 횟수
_UA = "kwater-hydro-mcp/2.0"

# 주요 댐·지역 좌표 (Open-Meteo 예보용 / 유역 강수 폴백)
PLACES = {
    "대전":     (36.351, 127.385),
    "소양강댐": (37.948, 127.818),
    "충주댐":   (37.000, 127.997),
    "대청댐":   (36.476, 127.480),
    "안동댐":   (36.572, 128.770),
    "합천댐":   (35.523, 128.034),
    "섬진강댐": (35.594, 127.121),
    "주암댐":   (35.057, 127.236),
    "서울":     (37.566, 126.978),
}


# ══════════════════════════════════════════════════════════
# 공용 헬퍼
# ══════════════════════════════════════════════════════════

def _fetch_bytes(url: str) -> bytes:
    """URL을 견고하게 GET 한다.

    HRFCO 서버는 대용량 목록(info.json) 응답 시 간헐적으로 연결을
    리셋(WinError 10054)하므로, 청크 단위로 끝까지 읽고 재시도한다.
    """
    last_err = None
    for attempt in range(_HTTP_RETRIES):
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": _UA, "Accept-Encoding": "gzip"},
            )
            resp = urllib.request.urlopen(req, timeout=_HTTP_TIMEOUT)
            buf = bytearray()
            while True:
                chunk = resp.read(8192)
                if not chunk:
                    break
                buf += chunk
            raw = bytes(buf)
            if resp.headers.get("Content-Encoding") == "gzip":
                raw = gzip.decompress(raw)
            return raw
        except Exception as e:          # noqa: BLE001 (일시 오류 모두 재시도)
            last_err = e
            time.sleep(1.0 + attempt)   # 점증 백오프
    raise last_err


def _get_json(url: str) -> dict:
    """URL을 GET 하여 JSON(dict)으로 반환."""
    return json.loads(_fetch_bytes(url).decode("utf-8"))


def _content(data: dict) -> list:
    """HRFCO 응답에서 content 배열을 안전하게 추출.

    응답 content 안에 None(빈 슬롯)이 섞여 오는 경우가 있어 제거한다.
    """
    if isinstance(data, list):
        rows = data
    else:
        rows = data.get("content", []) or []
    return [r for r in rows if isinstance(r, dict)]


def _num(v):
    """문자/공백 섞인 값을 float로. 빈칸·None·비수치는 None 반환."""
    if v is None:
        return None
    s = str(v).strip()
    if s == "":
        return None
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


def _blank(v) -> bool:
    """임계값 등이 비어있는지(공백·None) 판정."""
    return v is None or str(v).strip() == ""


def dms_to_dec(s: str):
    """DMS 좌표 문자열("127-59-44")을 십진수로 변환. 실패 시 None.

    HRFCO lon/lat 는 "도-분-초" 형식이며 끝에 공백이 붙기도 한다.
    """
    if not s:
        return None
    try:
        parts = str(s).strip().split("-")
        d = float(parts[0])
        m = float(parts[1]) if len(parts) > 1 and parts[1].strip() else 0.0
        sec = float(parts[2]) if len(parts) > 2 and parts[2].strip() else 0.0
        return round(d + m / 60 + sec / 3600, 5)
    except (ValueError, IndexError):
        return None


def _bar(value, scale: float, max_len: int = 30) -> str:
    """막대(■) 시각화. value/scale 개수만큼, max_len 으로 상한."""
    v = _num(value)
    if v is None or v <= 0:
        return ""
    n = int(v / scale)
    return "■" * min(n, max_len)


def _sorted_by_time(rows: list) -> list:
    """시계열 행을 ymdhm 오름차순으로 정렬(HRFCO는 내림차순으로 줄 때가 있음)."""
    return sorted(rows, key=lambda r: str(r.get("ymdhm", "")))


def _latest_valued(rows: list, key: str) -> dict:
    """`key` 값이 실제로 채워진 가장 최근 행을 반환.

    HRFCO는 현재 시각(부분 집계 중인 시간대) 행을 빈 값으로 먼저 내보낸다.
    rows[-1]을 그대로 쓰면 '데이터 없음'으로 보이므로, 값이 있는 최신 행을 찾는다.
    오름차순 정렬된 rows 가정. 값 있는 행이 없으면 마지막 행을 그대로 돌려준다.
    """
    for r in reversed(rows):
        if _num(r.get(key)) is not None:
            return r
    return rows[-1] if rows else {}


def _fmt_dt(ymdhm: str) -> str:
    """YYYYMMDDHHmm → 'MM-DD HH:mm' (표 가독성용)."""
    s = str(ymdhm)
    if len(s) >= 12:
        return f"{s[4:6]}-{s[6:8]} {s[8:10]}:{s[10:12]}"
    return s


def _time_window(hours_back: int):
    """(sdt, edt) YYYYMMDDHHmm 문자열 쌍 반환."""
    now = datetime.now()
    sdt = (now - timedelta(hours=hours_back)).strftime("%Y%m%d%H%M")
    edt = now.strftime("%Y%m%d%H%M")
    return sdt, edt


def _safe_url(url: str) -> str:
    """오류 메시지에 키 노출 방지."""
    return url.replace(HRFCO_API_KEY, "***KEY***")


# ══════════════════════════════════════════════════════════
# [A] 키 불필요 — Open-Meteo
# ══════════════════════════════════════════════════════════

def _resolve_place(place: str):
    """place 문자열을 (lat, lon)으로. 미등록이면 None."""
    if place in PLACES:
        return PLACES[place]
    # 부분 일치 허용 ('대청' → '대청댐')
    for name, coord in PLACES.items():
        if place and place in name:
            return coord
    return None


@mcp.tool()
def rain_forecast(place: str = "대전", days: int = 7) -> str:
    """지역/댐 유역의 향후 강수량 예보를 조회합니다.

    place: 대전, 소양강댐, 충주댐, 대청댐, 안동댐, 합천댐, 섬진강댐, 주암댐, 서울
    days : 예보 일수 (1~16)
    """
    coord = _resolve_place(place)
    if coord is None:
        return f"지원 지역: {', '.join(PLACES)}"
    lat, lon = coord
    days = max(1, min(int(days), 16))
    url = (f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
           f"&daily=precipitation_sum,precipitation_probability_max"
           f"&timezone=Asia%2FSeoul&forecast_days={days}")
    try:
        d = _get_json(url)["daily"]
    except Exception as e:  # noqa: BLE001
        return f"예보 조회 실패: {e}"

    lines = [f"[{place}] 향후 {len(d['time'])}일 강수 예보",
             "─" * 46,
             "날짜       | 강수량   | 확률 | 강도"]
    total = 0.0
    for t, mm, p in zip(d["time"], d["precipitation_sum"],
                        d["precipitation_probability_max"]):
        mm = mm or 0
        p = p or 0
        total += mm
        lines.append(f"{t} | {mm:5.1f}mm | {p:3d}% | {_bar(mm, 2)}")
    lines.append("─" * 46)
    lines.append(f"→ 기간 합계 {total:.1f}mm")
    if total >= 100:
        lines.append("⚠ 누적 강수 100mm 이상 — 댐·하천 수위 주시 필요")
    return "\n".join(lines)


@mcp.tool()
def weather_now(place: str = "대전") -> str:
    """지역/댐 유역의 현재 기상 실황(기온·강수·습도·바람)을 조회합니다."""
    coord = _resolve_place(place)
    if coord is None:
        return f"지원 지역: {', '.join(PLACES)}"
    lat, lon = coord
    url = (f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
           f"&current=temperature_2m,precipitation,relative_humidity_2m,"
           f"wind_speed_10m&timezone=Asia%2FSeoul")
    try:
        c = _get_json(url)["current"]
    except Exception as e:  # noqa: BLE001
        return f"실황 조회 실패: {e}"
    return (f"[{place}] {c['time']} 현재 기상\n"
            f"  기온 {c['temperature_2m']}°C | 습도 {c['relative_humidity_2m']}% | "
            f"강수 {c['precipitation']}mm | 풍속 {c['wind_speed_10m']}km/h")


# ══════════════════════════════════════════════════════════
# [B] HRFCO — 댐
# ══════════════════════════════════════════════════════════

def _find_dam_rows(keyword: str = ""):
    """댐 관측소 목록을 조회하고 keyword로 필터링한 행 리스트 반환."""
    url = f"{HRFCO_BASE}/{HRFCO_API_KEY}/dam/info.json"
    rows = _content(_get_json(url))
    if not keyword:
        return rows
    return [r for r in rows if keyword in str(r.get("obsnm", ""))]


@mcp.tool()
def dam_observatory(keyword: str = "") -> str:
    """전국 댐 관측소 목록·코드를 조회합니다.

    keyword 로 댐 이름 필터링 (예: '대청', '충주'). 비우면 전체 목록.
    출력된 dam 코드(dmobscd)를 dam_status 도구에 넣어 사용하세요.
    """
    try:
        rows = _find_dam_rows(keyword)
    except Exception as e:  # noqa: BLE001
        return f"댐 목록 조회 실패: {e}"
    if not rows:
        return f"'{keyword}' 검색 결과 없음. keyword 없이 호출하면 전체를 봅니다."

    lines = [f"댐 관측소 검색: '{keyword or '전체'}'  (총 {len(rows)}건)",
             "─" * 52,
             "코드      | 댐 이름        | 관리기관"]
    for r in rows[:50]:
        lines.append(f"{r.get('dmobscd',''):<9} | {r.get('obsnm',''):<13} | "
                     f"{r.get('agcnm','')}")
    if len(rows) > 50:
        lines.append(f"... 외 {len(rows) - 50}건 (keyword로 좁혀 보세요)")
    return "\n".join(lines)


def _dam_risk(swl, fldlmtwl, pfh):
    """댐 위험도 판정. (등급문자, 설명) 반환.

    swl(현재 저수위)을 fldlmtwl(홍수기제한수위), pfh(계획홍수위)와 비교.
    """
    s = _num(swl)
    lim = _num(fldlmtwl)
    plan = _num(pfh)
    if s is None:
        return "—", "현재 저수위 데이터 없음"
    if plan is not None and s >= plan:
        return "🔴 위험", f"저수위 {s} ≥ 계획홍수위 {plan} EL.m — 월류 위험"
    if lim is not None and s >= lim:
        margin = (plan - s) if plan is not None else None
        msg = f"저수위 {s} ≥ 홍수기제한수위 {lim} EL.m — 제한수위 초과"
        if margin is not None:
            msg += f" (계획홍수위까지 {margin:.2f}m 여유)"
        return "🟠 주의", msg
    # 정상
    ref = lim if lim is not None else plan
    if ref is not None:
        return "🟢 정상", f"저수위 {s} < 기준 {ref} EL.m ({ref - s:.2f}m 여유)"
    return "🟢 정상", f"저수위 {s} EL.m (임계값 미제공)"


@mcp.tool()
def dam_status(obs_code: str, hours_back: int = 24) -> str:
    """댐 코드로 최근 수위·저수량·유입량·방류량 시계열과 위험도를 조회합니다.

    obs_code  : dam_observatory 로 확인한 댐 코드(dmobscd). 예) 충주댐 '1003110'
    hours_back: 조회 시간 범위(시간). 기본 24.

    저수위(swl)를 홍수기제한수위(fldlmtwl)·계획홍수위(pfh)와 비교해
    정상/주의/위험 등급을 함께 판정합니다.
    """
    # 1) 댐 메타(임계값) 조회
    meta = {}
    try:
        for r in _content(_get_json(f"{HRFCO_BASE}/{HRFCO_API_KEY}/dam/info.json")):
            if str(r.get("dmobscd")) == str(obs_code):
                meta = r
                break
    except Exception:  # noqa: BLE001 (메타 실패해도 시계열은 진행)
        meta = {}

    # 2) 시계열 조회
    sdt, edt = _time_window(hours_back)
    url = f"{HRFCO_BASE}/{HRFCO_API_KEY}/dam/list/1H/{obs_code}/{sdt}/{edt}.json"
    try:
        rows = _content(_get_json(url))
    except Exception as e:  # noqa: BLE001
        return f"댐 시계열 조회 실패: {e}\n시도 URL: {_safe_url(url)}"
    if not rows:
        return (f"댐 {obs_code} 데이터 없음 (최근 {hours_back}시간).\n"
                f"코드가 맞는지 dam_observatory 로 확인해 보세요.")

    rows = _sorted_by_time(rows)
    name = meta.get("obsnm", obs_code)
    fld = meta.get("fldlmtwl")
    pfh = meta.get("pfh")

    # 헤더 + 위험도 (현재 시각 행은 빈 값일 수 있어 값 있는 최신 행 사용)
    cur = _latest_valued(rows, "swl")
    grade, detail = _dam_risk(cur.get("swl"), fld, pfh)
    header = [f"━━━ 댐 수문 현황 : {name} ({obs_code}) ━━━",
              f"관리기관 {meta.get('agcnm','-')} | 위치 {meta.get('addr','-')} "
              f"{meta.get('etcaddr','')}".rstrip(),
              f"홍수기제한수위 {fld if not _blank(fld) else '미제공'} EL.m | "
              f"계획홍수위 {pfh if not _blank(pfh) else '미제공'} EL.m",
              f"위험도 판정: {grade} — {detail}",
              "─" * 64,
              "시각        | 저수위EL.m | 유입㎥/s | 총방류㎥/s | 저수량백만㎥"]

    body = []
    for r in rows[-24:]:
        swl = _num(r.get("swl"))
        inf = _num(r.get("inf"))
        otf = _num(r.get("tototf"))
        sfw = _num(r.get("sfw"))
        body.append(
            f"{_fmt_dt(r.get('ymdhm','')):<11} | "
            f"{('%.3f' % swl) if swl is not None else '   -   ':>9} | "
            f"{('%.1f' % inf) if inf is not None else '  -  ':>7} | "
            f"{('%.1f' % otf) if otf is not None else '  -  ':>8} | "
            f"{('%.1f' % sfw) if sfw is not None else '  -  '}"
        )

    # 추세 요약
    first_swl = _num(rows[0].get("swl"))
    last_swl = _num(cur.get("swl"))
    trend = ""
    if first_swl is not None and last_swl is not None:
        diff = last_swl - first_swl
        arrow = "▲상승" if diff > 0.01 else ("▼하강" if diff < -0.01 else "─보합")
        trend = f"\n→ {hours_back}시간 변화: {arrow} {diff:+.3f}m (현재 {last_swl} EL.m)"

    return "\n".join(header + body) + trend


# ══════════════════════════════════════════════════════════
# [C] HRFCO — 하천 수위
# ══════════════════════════════════════════════════════════

@mcp.tool()
def waterlevel_observatory(keyword: str = "") -> str:
    """하천 수위관측소 목록·코드를 조회합니다.

    keyword 로 관측소 이름 필터링 (예: '한강대교', '여주'). 권장: keyword 지정.
    전국 목록은 매우 크므로 keyword 없이 호출하면 일부만 보여줍니다.
    출력된 코드(wlobscd)를 waterlevel_status 에 넣어 사용하세요.
    """
    url = f"{HRFCO_BASE}/{HRFCO_API_KEY}/waterlevel/info.json"
    try:
        rows = _content(_get_json(url))
    except Exception as e:  # noqa: BLE001
        return (f"수위관측소 목록 조회 실패: {e}\n"
                f"(전국 목록이 커서 일시적으로 실패할 수 있습니다. 잠시 후 재시도)")
    if keyword:
        rows = [r for r in rows if keyword in str(r.get("obsnm", ""))]
    if not rows:
        return f"'{keyword}' 검색 결과 없음."

    lines = [f"수위관측소 검색: '{keyword or '전체'}'  (총 {len(rows)}건)",
             "─" * 58,
             "코드      | 관측소        | 예보 | 주의/경계/경보/심각(m)"]
    for r in rows[:50]:
        thr = "/".join(str(r.get(k, "")).strip() or "-"
                       for k in ("attwl", "wrnwl", "almwl", "srswl"))
        fcst = "예보" if str(r.get("fstnyn", "")).strip() == "Y" else " - "
        lines.append(f"{r.get('wlobscd',''):<9} | {r.get('obsnm',''):<13} | "
                     f"{fcst} | {thr}")
    if len(rows) > 50:
        lines.append(f"... 외 {len(rows) - 50}건 (keyword로 좁혀 보세요)")
    return "\n".join(lines)


def _wl_stage(wl, attwl, wrnwl, almwl, srswl):
    """하천 수위 홍수 단계 판정. (등급, 설명) 반환.

    정상 < 주의(attwl) < 경계(wrnwl) < 경보(almwl) < 심각(srswl).
    공백 임계값은 판정에서 제외.
    """
    w = _num(wl)
    if w is None:
        return "—", "현재 수위 데이터 없음"
    # 높은 단계부터 검사
    for label, key, val in (("🔴 심각", "srswl", srswl),
                            ("🟠 경보", "almwl", almwl),
                            ("🟡 경계", "wrnwl", wrnwl),
                            ("🟢 주의", "attwl", attwl)):
        t = _num(val)
        if t is not None and w >= t:
            return label, f"수위 {w}m ≥ {key} {t}m"
    # 정상 — 가장 낮은 유효 임계값과의 여유 표시
    att = _num(attwl)
    if att is not None:
        return "🟦 정상", f"수위 {w}m < 주의수위 {att}m ({att - w:.2f}m 여유)"
    return "🟦 정상", f"수위 {w}m (임계값 미제공)"


@mcp.tool()
def waterlevel_status(obs_code: str, hours_back: int = 24) -> str:
    """하천 수위관측소 코드로 최근 수위·유량 시계열과 홍수 단계를 조회합니다.

    obs_code  : waterlevel_observatory 로 확인한 코드(wlobscd).
    hours_back: 조회 시간 범위(시간). 기본 24.

    현재 수위(wl)를 주의/경계/경보/심각 4단계 임계값과 비교해 판정합니다.
    """
    # 1) 메타(임계값)
    meta = {}
    try:
        for r in _content(_get_json(
                f"{HRFCO_BASE}/{HRFCO_API_KEY}/waterlevel/info.json")):
            if str(r.get("wlobscd")) == str(obs_code):
                meta = r
                break
    except Exception:  # noqa: BLE001
        meta = {}

    # 2) 시계열
    sdt, edt = _time_window(hours_back)
    url = f"{HRFCO_BASE}/{HRFCO_API_KEY}/waterlevel/list/1H/{obs_code}/{sdt}/{edt}.json"
    try:
        rows = _content(_get_json(url))
    except Exception as e:  # noqa: BLE001
        return f"수위 시계열 조회 실패: {e}\n시도 URL: {_safe_url(url)}"
    if not rows:
        return (f"수위관측소 {obs_code} 데이터 없음 (최근 {hours_back}시간).\n"
                f"waterlevel_observatory 로 코드를 확인해 보세요.")

    rows = _sorted_by_time(rows)
    name = meta.get("obsnm", obs_code)
    cur = _latest_valued(rows, "wl")
    grade, detail = _wl_stage(cur.get("wl"),
                              meta.get("attwl"), meta.get("wrnwl"),
                              meta.get("almwl"), meta.get("srswl"))

    def _thr(k):
        v = meta.get(k)
        return str(v).strip() if not _blank(v) else "—"

    header = [f"━━━ 하천 수위 현황 : {name} ({obs_code}) ━━━",
              f"관리기관 {meta.get('agcnm','-')} | 위치 {meta.get('addr','-')}",
              f"임계수위(m)  주의 {_thr('attwl')} / 경계 {_thr('wrnwl')} / "
              f"경보 {_thr('almwl')} / 심각 {_thr('srswl')}",
              f"홍수 단계: {grade} — {detail}",
              "─" * 50,
              "시각        | 수위(m) | 유량(㎥/s)"]
    body = []
    for r in rows[-24:]:
        wl = _num(r.get("wl"))
        fw = _num(r.get("fw"))
        body.append(
            f"{_fmt_dt(r.get('ymdhm','')):<11} | "
            f"{('%.2f' % wl) if wl is not None else '  -  ':>6} | "
            f"{('%.1f' % fw) if fw is not None else '   -   '}"
        )

    first_wl = _num(rows[0].get("wl"))
    last_wl = _num(cur.get("wl"))
    trend = ""
    if first_wl is not None and last_wl is not None:
        diff = last_wl - first_wl
        arrow = "▲상승" if diff > 0.01 else ("▼하강" if diff < -0.01 else "─보합")
        trend = f"\n→ {hours_back}시간 변화: {arrow} {diff:+.2f}m (현재 {last_wl}m)"
    return "\n".join(header + body) + trend


# ══════════════════════════════════════════════════════════
# [D] HRFCO — 강수량
# ══════════════════════════════════════════════════════════

@mcp.tool()
def rainfall_observatory(keyword: str = "") -> str:
    """강수량관측소 목록·코드를 조회합니다.

    keyword 로 관측소 이름 필터링 (예: '청주', '대전'). 권장: keyword 지정.
    출력된 코드(rfobscd)를 rainfall_status 에 넣어 사용하세요.
    """
    url = f"{HRFCO_BASE}/{HRFCO_API_KEY}/rainfall/info.json"
    try:
        rows = _content(_get_json(url))
    except Exception as e:  # noqa: BLE001
        return (f"강수량관측소 목록 조회 실패: {e}\n"
                f"(전국 목록이 커서 일시적으로 실패할 수 있습니다. 잠시 후 재시도)")
    if keyword:
        rows = [r for r in rows if keyword in str(r.get("obsnm", ""))]
    if not rows:
        return f"'{keyword}' 검색 결과 없음."

    lines = [f"강수량관측소 검색: '{keyword or '전체'}'  (총 {len(rows)}건)",
             "─" * 52,
             "코드        | 관측소        | 관리기관"]
    for r in rows[:50]:
        lines.append(f"{r.get('rfobscd',''):<11} | {r.get('obsnm',''):<13} | "
                     f"{r.get('agcnm','')}")
    if len(rows) > 50:
        lines.append(f"... 외 {len(rows) - 50}건 (keyword로 좁혀 보세요)")
    return "\n".join(lines)


@mcp.tool()
def rainfall_status(obs_code: str, hours_back: int = 24) -> str:
    """강수량관측소 코드로 최근 강수량 시계열과 누적을 조회합니다.

    obs_code  : rainfall_observatory 로 확인한 코드(rfobscd).
    hours_back: 조회 시간 범위(시간). 기본 24.
    """
    meta = {}
    try:
        for r in _content(_get_json(
                f"{HRFCO_BASE}/{HRFCO_API_KEY}/rainfall/info.json")):
            if str(r.get("rfobscd")) == str(obs_code):
                meta = r
                break
    except Exception:  # noqa: BLE001
        meta = {}

    sdt, edt = _time_window(hours_back)
    url = f"{HRFCO_BASE}/{HRFCO_API_KEY}/rainfall/list/1H/{obs_code}/{sdt}/{edt}.json"
    try:
        rows = _content(_get_json(url))
    except Exception as e:  # noqa: BLE001
        return f"강수량 시계열 조회 실패: {e}\n시도 URL: {_safe_url(url)}"
    if not rows:
        return (f"강수량관측소 {obs_code} 데이터 없음 (최근 {hours_back}시간).\n"
                f"rainfall_observatory 로 코드를 확인해 보세요.")

    rows = _sorted_by_time(rows)
    name = meta.get("obsnm", obs_code)
    total = sum(_num(r.get("rf")) or 0 for r in rows)

    header = [f"━━━ 강수량 현황 : {name} ({obs_code}) ━━━",
              f"관리기관 {meta.get('agcnm','-')} | 위치 {meta.get('addr','-')}",
              f"최근 {hours_back}시간 누적 강수량: {total:.1f}mm",
              "─" * 44,
              "시각        | 강수(mm) | 강도"]
    body = []
    for r in rows[-24:]:
        rf = _num(r.get("rf")) or 0
        body.append(f"{_fmt_dt(r.get('ymdhm','')):<11} | {rf:6.1f} | {_bar(rf, 1)}")

    note = ""
    if total >= 80:
        note = "\n⚠ 단시간 누적 80mm 이상 — 하천·댐 수위 급변 주의"
    return "\n".join(header + body) + f"\n{'─'*44}\n→ 누적 {total:.1f}mm" + note


# ══════════════════════════════════════════════════════════
# [E] 종합 — 킬러 도구
# ══════════════════════════════════════════════════════════

@mcp.tool()
def flood_briefing(dam_name: str = "충주댐") -> str:
    """★ 댐 이름 하나로 종합 '주간 수문 브리핑'을 한 번에 생성합니다.

    내부에서 다음을 모두 자동 수행합니다(에이전트 연쇄 호출을 1개로 캡슐화):
      1) 댐 관측소 검색 → 코드 확정
      2) 댐 수문 실측(저수위·유입·방류) + 위험도 판정
      3) 유역 강수 예보(Open-Meteo) 종합

    dam_name: 댐 이름 또는 일부 (예: '충주', '대청', '소양강').
    """
    out = [f"╔══════════════════════════════════════════════╗",
           f"║  수문 종합 브리핑 — {dam_name:<24}║",
           f"║  생성: {datetime.now().strftime('%Y-%m-%d %H:%M'):<35}║",
           f"╚══════════════════════════════════════════════╝", ""]

    # ── 1) 댐 관측소 검색 ──────────────────────────────
    keyword = dam_name.replace("댐", "")
    dam_row = None
    try:
        candidates = _find_dam_rows(keyword)
        if candidates:
            # 정확 일치 우선
            exact = [r for r in candidates
                     if str(r.get("obsnm", "")).replace("댐", "") == keyword]
            dam_row = (exact or candidates)[0]
    except Exception as e:  # noqa: BLE001
        out.append(f"[1] 댐 검색 실패: {e}")

    if not dam_row:
        out.append(f"[1] '{dam_name}' 댐 관측소를 찾지 못했습니다.")
        out.append("    dam_observatory 도구로 정확한 이름을 확인해 보세요.")
        # 유역 예보라도 제공
        coord = _resolve_place(dam_name) or _resolve_place(keyword)
        if coord:
            out.append("")
            out.append("[유역 강수 예보]")
            out.append(rain_forecast(dam_name if dam_name in PLACES else keyword, 7))
        return "\n".join(out)

    code = dam_row.get("dmobscd", "")
    obsnm = dam_row.get("obsnm", dam_name)
    out.append(f"[1] 대상 댐 : {obsnm} (코드 {code})")
    out.append(f"    관리기관 {dam_row.get('agcnm','-')} | "
               f"위치 {dam_row.get('addr','-')} {dam_row.get('etcaddr','')}".rstrip())
    lat = dms_to_dec(dam_row.get("lat"))
    lon = dms_to_dec(dam_row.get("lon"))
    if lat and lon:
        out.append(f"    좌표(십진) {lat}, {lon}")
    out.append("")

    # ── 2) 댐 수문 실측 + 위험도 ──────────────────────
    out.append("[2] 댐 수문 실측 (최근 24시간)")
    try:
        sdt, edt = _time_window(24)
        url = f"{HRFCO_BASE}/{HRFCO_API_KEY}/dam/list/1H/{code}/{sdt}/{edt}.json"
        rows = _sorted_by_time(_content(_get_json(url)))
    except Exception as e:  # noqa: BLE001
        rows = []
        out.append(f"    수문 데이터 조회 실패: {e}")

    if rows:
        latest = _latest_valued(rows, "swl")
        grade, detail = _dam_risk(latest.get("swl"),
                                  dam_row.get("fldlmtwl"), dam_row.get("pfh"))
        swl = _num(latest.get("swl"))
        inf = _num(latest.get("inf"))
        otf = _num(latest.get("tototf"))
        sfw = _num(latest.get("sfw"))
        out.append(f"    최신 관측 {_fmt_dt(latest.get('ymdhm',''))}")
        out.append(f"    저수위 {swl if swl is not None else '-'} EL.m  "
                   f"| 유입 {inf if inf is not None else '-'} ㎥/s  "
                   f"| 총방류 {otf if otf is not None else '-'} ㎥/s  "
                   f"| 저수량 {sfw if sfw is not None else '-'} 백만㎥")
        out.append(f"    홍수기제한수위 {dam_row.get('fldlmtwl') or '미제공'} / "
                   f"계획홍수위 {dam_row.get('pfh') or '미제공'} EL.m")
        out.append(f"    ▶ 위험도: {grade} — {detail}")
        # 24h 추세
        f0 = _num(rows[0].get("swl"))
        if f0 is not None and swl is not None:
            d = swl - f0
            arrow = "▲상승" if d > 0.01 else ("▼하강" if d < -0.01 else "─보합")
            out.append(f"    ▶ 24h 저수위 변화: {arrow} {d:+.3f}m")
        # 유입 vs 방류 수지
        if inf is not None and otf is not None:
            bal = inf - otf
            sign = "유입 우세(수위↑ 경향)" if bal > 0 else \
                   ("방류 우세(수위↓ 경향)" if bal < 0 else "균형")
            out.append(f"    ▶ 유입-방류 수지: {bal:+.1f} ㎥/s — {sign}")
    out.append("")

    # ── 3) 유역 강수 예보 ─────────────────────────────
    out.append("[3] 유역 강수 예보 (향후 7일)")
    coord = _resolve_place(obsnm) or _resolve_place(keyword)
    if coord:
        lat_f, lon_f = coord
        place_key = obsnm if obsnm in PLACES else (keyword if _resolve_place(keyword) else "대전")
    elif lat and lon:
        lat_f, lon_f = lat, lon          # 댐 실제 좌표로 예보
        place_key = None
    else:
        lat_f = lon_f = None
        place_key = None

    fc_total = None
    if lat_f and lon_f:
        try:
            url = (f"https://api.open-meteo.com/v1/forecast?latitude={lat_f}"
                   f"&longitude={lon_f}&daily=precipitation_sum,"
                   f"precipitation_probability_max&timezone=Asia%2FSeoul&forecast_days=7")
            d = _get_json(url)["daily"]
            fc_total = 0.0
            for t, mm, p in zip(d["time"], d["precipitation_sum"],
                                d["precipitation_probability_max"]):
                mm = mm or 0
                p = p or 0
                fc_total += mm
                out.append(f"    {t} | {mm:5.1f}mm | {p:3d}% | {_bar(mm, 2)}")
            out.append(f"    → 7일 누적 예보 {fc_total:.1f}mm")
        except Exception as e:  # noqa: BLE001
            out.append(f"    예보 조회 실패: {e}")
    else:
        out.append("    유역 좌표를 확인할 수 없어 예보를 생략합니다.")

    # ── 4) 종합 판단 ─────────────────────────────────
    out.append("")
    out.append("[4] 종합 판단")
    msgs = []
    if rows:
        grade, _ = _dam_risk(_latest_valued(rows, "swl").get("swl"),
                             dam_row.get("fldlmtwl"), dam_row.get("pfh"))
        if "위험" in grade:
            msgs.append("현재 저수위가 계획홍수위에 근접/초과 — 즉시 방류·경보 검토.")
        elif "주의" in grade:
            msgs.append("홍수기제한수위를 초과한 상태 — 선제 방류로 여유고 확보 권장.")
        else:
            msgs.append("댐 수위는 정상 범위.")
    if fc_total is not None:
        if fc_total >= 100:
            msgs.append(f"향후 7일 누적 강수 {fc_total:.0f}mm 예상 — 유입 급증 대비 필요.")
        elif fc_total >= 30:
            msgs.append(f"향후 7일 강수 {fc_total:.0f}mm 예상 — 수위 변동 모니터링.")
        else:
            msgs.append("향후 강수량 적음 — 급격한 수위 상승 가능성 낮음.")
    if not msgs:
        msgs.append("데이터 부족으로 종합 판단을 생략합니다.")
    for m in msgs:
        out.append(f"    • {m}")

    return "\n".join(out)


if __name__ == "__main__":
    mcp.run()
