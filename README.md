# 💧 수문(水門) 워치 — Hydro Watch

> 한강홍수통제소(HRFCO) Open API 기반 **실시간 댐·하천·강수 모니터링 웹서비스 + MCP 서버**
> 수문(水門, floodgate) 데이터를 누구나 브라우저로 보고, Claude로 분석한다.

<!-- 배지 자리 (Badges) — 배포 후 실제 URL/뱃지로 교체하세요 -->
![License](https://img.shields.io/badge/license-MIT-green)
![Web](https://img.shields.io/badge/web-Vanilla%20JS-yellow)
![MCP](https://img.shields.io/badge/MCP-fastmcp-blue)
![Data](https://img.shields.io/badge/data-HRFCO%20Open%20API-1f77b4)

<!-- 스크린샷 자리 (Screenshot) — docs/screenshot.png 를 추가하면 아래가 표시됩니다 -->
![수문 워치 스크린샷](docs/screenshot.png)

---

## 📖 프로젝트 소개

**수문 워치(Hydro Watch)** 는 전국 댐·수위관측소·강수량관측소의 실시간 수문 데이터를 보여주는 두 가지 도구의 묶음입니다.

1. **웹서비스 (Web)** — 설치 없이 **브라우저에서 바로** 댐 저수위, 하천 수위, 강수량, 홍수 위험도를 지도와 차트로 봅니다. 백엔드/서버가 필요 없는 **순수 정적 웹앱**입니다 (HRFCO API가 CORS를 개방해 브라우저에서 직접 호출됨).
2. **MCP 서버 (MCP)** — **Claude Desktop**에 붙여 "대청댐 최근 24시간 수위·방류량 정리해줘" 같은 자연어 질문으로 수문 데이터를 분석하게 합니다.

> 데이터 출처: **한강홍수통제소(HRFCO)** 수문 Open API + **Open-Meteo** 기상 예보. 모두 공개 데이터이며 **참고용**입니다.

---

## ✨ 기능 요약

### 🌐 웹앱 8개 탭

| # | 탭 | 내용 |
|---|------|------|
| 1 | **대시보드 (Dashboard)** | 전국 주요 다목적댐 실시간 저수위·유입·방류 카드 + 위험 단계 KPI |
| 2 | **지도 (Map)** | 댐·수위·강수 관측소를 Leaflet 지도에 표시 (마커 색상=위험도, DMS→십진수 변환) |
| 3 | **댐 상세 (Dam)** | 댐별 저수위(EL.m)·저수량·유입량·총방류량 시계열, 제한수위/계획홍수위 대비 위험도 |
| 4 | **하천 수위 (Water Level)** | 수위관측소별 수위·유량, 주의→경계→경보→심각 4단계 홍수 단계 (위험 상단 정렬) |
| 5 | **강수 현황 (Rainfall)** | 강수량관측소별 시간 강수량·누적 막대/라인 차트 |
| 6 | **기상 예보 (Forecast)** | Open-Meteo 기반 유역별 7일 강수 예보 + 현재 실황 |
| 7 | **수문 브리핑 (Briefing)** | 선택 댐의 실측 데이터 + 강수 예보를 종합한 자동 텍스트 브리핑 (복사 가능) |
| 8 | **설정 (Settings)** | HRFCO 인증키·자동 새로고침 주기·타임아웃 (localStorage 저장) |

### 🤖 MCP 도구 9종 (Claude Desktop용)

| 도구 | 설명 | 인증키 |
|------|------|--------|
| `rain_forecast` | 지역/댐 유역의 향후 강수량 예보 (Open-Meteo) | ❌ 불필요 (즉시 작동) |
| `weather_now` | 지역/댐 유역의 현재 기상 실황(기온·강수·습도·바람) | ❌ 불필요 (즉시 작동) |
| `dam_observatory` | 전국 댐 관측소 목록·코드(dmobscd) 조회 (이름 필터) | ✅ HRFCO 키 필요 |
| `dam_status` | 댐 코드로 최근 저수위·저수량·유입·방류 시계열 + 위험도 판정 | ✅ HRFCO 키 필요 |
| `waterlevel_observatory` | 하천 수위관측소 목록·코드(wlobscd) 조회 (이름 필터) | ✅ HRFCO 키 필요 |
| `waterlevel_status` | 수위 코드로 수위·유량 시계열 + 주의/경계/경보/심각 단계 판정 | ✅ HRFCO 키 필요 |
| `rainfall_observatory` | 강수량관측소 목록·코드(rfobscd) 조회 (이름 필터) | ✅ HRFCO 키 필요 |
| `rainfall_status` | 강수 코드로 강수량 시계열 + 기간 누적 | ✅ HRFCO 키 필요 |
| `flood_briefing` | ★ 댐 이름 하나로 관측소검색→수문실측→유역예보를 한 번에 종합 브리핑 | ✅ HRFCO 키 필요 |

> 💡 키 없이도 날씨 도구 2종(`rain_forecast`, `weather_now`)은 바로 작동합니다.
> 나머지 7종은 HRFCO 인증키가 필요합니다(미설정 시 검증된 데모 공개키로 동작).

---

## 🚀 빠른 시작

### (A) 웹앱 — 설치 없이 바로

- **온라인:** GitHub Pages URL을 브라우저에서 엽니다.
  `https://<사용자명>.github.io/<저장소명>/`
  *(배포 방법은 [docs/DEPLOY.md](docs/DEPLOY.md) 참고)*
- **로컬:** 저장소를 내려받아 `index.html`을 **더블클릭**하면 끝입니다. (별도 서버·빌드 불필요)

### (B) MCP 서버 — Claude Desktop에 등록

```bash
# 1. 의존성 설치
pip install -r mcp/requirements.txt

# 2. Claude Desktop 설정 파일에 등록
#    맥:    ~/Library/Application Support/Claude/claude_desktop_config.json
#    윈도우: %APPDATA%\Claude\claude_desktop_config.json
```

`mcp/claude_desktop_config.example.json` 내용을 붙여넣고 **두 군데**만 수정합니다.

1. `"args"`의 파일 경로 → `mcp/kwater_hydro_mcp.py`의 실제 저장 위치
2. `"HRFCO_API_KEY"` → 발급받은 인증키 (없으면 빈칸 — 날씨 도구 2종은 작동)

저장 후 **Claude Desktop 완전 종료 → 재시작** → 입력창 하단 🔨 아이콘에 도구가 보이면 성공입니다.

**시연 프롬프트 예시:**
```
대청댐 관측소 코드를 찾고, 최근 24시간 수위·유입량·방류량 추이를 표로 정리한 뒤
이번 주 강수 예보와 종합해서 '주간 수문 브리핑' 형식으로 작성해줘.
```
→ Claude가 도구를 **3번 연쇄 호출**(관측소 검색 → 수문 데이터 → 강수 예보)하고 종합합니다.

---

## 🔑 HRFCO 인증키 발급 방법

댐·하천·강수 실측 데이터(웹앱의 댐 상세·하천 수위·강수 현황 탭, MCP의 `dam_*`·`waterlevel_*`·`rainfall_*`·`flood_briefing` 도구)는 한강홍수통제소 인증키가 필요합니다. **무료**입니다.

1. **발급 페이지 접속:** <https://www.hrfco.go.kr/web/openapiPage/certifyKey.do>
2. **인증키 발급 신청** — 사용 URL/IP란에 `localhost` 입력
3. 신청 이메일로 승인 메일이 오면 메일 안의 **[인증키 사용] 버튼 클릭** → 키 활성화

> ⚠️ **실사용 노하우 (다수 증언):**
> - **네이버/다음/지메일** 계정은 승인 메일이 누락되는 경우가 있습니다. → **회사 메일** 사용 권장 (예: `itcl.kr`)
> - 메일이 끝내 안 오면 한강홍수통제소 대표번호 **02-590-9999**로 전화해 이메일로 키를 직접 받을 수 있습니다.

발급 후, 웹앱에서는 **설정 탭**의 인증키 입력란에 키를 붙여넣고(브라우저 localStorage에 저장), MCP에서는 `HRFCO_API_KEY` 환경변수/설정에 넣습니다. (둘 다 미입력 시 검증된 데모 공개키로 동작)

---

## 🗂 데이터 출처 / 면책 (Data & Disclaimer)

| 데이터 | 출처 | 인증키 |
|--------|------|--------|
| 댐·수위·강수·보 수문 실측 | **한강홍수통제소(HRFCO) Open API** — `api.hrfco.go.kr` | 필요 |
| 강수 예보·기상 실황 | **Open-Meteo** — `api.open-meteo.com` | 불필요 |

- 본 서비스의 모든 데이터는 **공공·공개 데이터**이며 **참고용(informational)** 입니다.
- 실제 홍수 대응·방재 의사결정은 반드시 **한강홍수통제소 및 관계기관의 공식 발표**를 따르십시오.
- 데이터 정확성·실시간성·가용성은 원천 API 제공 상황에 따라 달라질 수 있으며, 본 프로젝트는 이에 대해 보증하지 않습니다.

---

## 📁 폴더 구조

```
kwater/
├── index.html                          # 정적 웹앱 (GitHub Pages 루트 배포 대상)
├── README.md                           # 이 문서
├── LICENSE                             # MIT License
├── .gitignore
├── mcp/
│   ├── kwater_hydro_mcp.py             # MCP 서버 본체 (도구 9종)
│   ├── requirements.txt                # 파이썬 의존성
│   └── claude_desktop_config.example.json
└── docs/
    ├── DEPLOY.md                       # GitHub Pages 배포 가이드
    ├── DATA_DICTIONARY.md              # 데이터 사전 (필드·단위·위험도 로직, SSOT)
    └── screenshot.png                  # 스크린샷 (placeholder — 직접 추가)
```

---

## 🛠 기술 스택

- **웹앱:** Vanilla JS (프레임워크·빌드 없음), [Chart.js](https://www.chartjs.org/) (차트), [Leaflet](https://leafletjs.com/) (지도)
- **MCP 서버:** Python 3.10+, [fastmcp](https://github.com/jlowin/fastmcp)
- **데이터 API:** HRFCO Open API, Open-Meteo
- **배포:** GitHub Pages (정적 호스팅)

---

## 🔒 보안 주의 (Security Note)

이 저장소에는 **데모용 HRFCO 인증키**가 코드에 포함되어 있을 수 있습니다(`index.html`, 스펙 문서).

- 데모 키는 학습·시연 편의를 위한 것으로, **언제든 차단·소진될 수 있습니다.**
- 정식 서비스나 외부 공개 배포 시에는 반드시 **본인 명의로 발급한 키로 교체**하세요.
- 클라이언트 측 정적 웹앱 특성상 키가 브라우저에 노출되므로, 민감한 운영 환경에서는 별도 프록시/서버로 키를 감추는 구성을 권장합니다.

---

## 📄 라이선스

[MIT License](LICENSE) © 2026 Kim Dukjin / IT커뮤니케이션연구소(ITCL)
