# 🌊 수문 워치 — 작업 핸드오프 / 이어하기 가이드

> 이 파일 하나만 읽으면 다음 세션에서 바로 이어서 작업할 수 있도록 정리한 문서입니다.
> 최종 업데이트: 2026-06-15 (Claude Opus 4.8 + 김덕진 소장 공동 작업)

---

## 0. 30초 요약

- **무엇**: 한강홍수통제소(HRFCO) Open API로 전국 댐·하천·강수를 실시간 보는 **웹서비스** + Claude용 **MCP 서버**.
- **라이브 URL**: https://socialkim.github.io/kwater-hydro-watch/
- **GitHub**: https://github.com/socialkim/kwater-hydro-watch (public, 계정 `socialkim`)
- **로컬 폴더**: `C:\Users\kimdu\claude\kwater\` (자체 git repo)
- **현재 상태**: ✅ 웹앱 라이브 동작 · MCP 서버 검증 완료 · 문서 완비. 강의 시연 가능 상태.

---

## 1. 어떻게 이어서 작업하나 (새 세션 시작 절차)

다음에 클로드와 이 작업을 이어갈 때:

1. **이 파일(`HANDOFF.md`)을 먼저 읽으라고 시킨다.** 예: "kwater 폴더의 HANDOFF.md 읽고 이어서 작업하자."
2. 클로드가 폴더 구조 + 아래 "핵심 기술 사실"을 파악하면 바로 작업 가능.
3. 작업 후에는 **반드시 git commit + push** 해야 라이브 사이트(GitHub Pages)에 반영됨.

### 로컬에서 미리보기
- 웹앱: `index.html` 더블클릭 (브라우저에서 바로 열림 — 백엔드 불필요, API CORS 개방됨).
- MCP: `cd mcp && pip install -r requirements.txt` 후 Claude Desktop에 등록(`claude_desktop_config.example.json` 참고).

### 수정 → 배포 흐름 (중요)
```bash
cd C:\Users\kimdu\claude\kwater
# index.html 등 수정 후
git add -A
git commit -m "수정 내용"
git push origin main
# → GitHub Pages가 약 1분 뒤 자동 재빌드. 브라우저는 Ctrl+Shift+R(강력 새로고침)으로 캐시 무시.
```
- gh CLI는 `socialkim` 계정으로 이미 로그인되어 있음(`repo` 권한).
- Pages 빌드 상태 확인: `gh api repos/socialkim/kwater-hydro-watch/pages/builds/latest --jq .status`

---

## 2. 파일 구조

```
kwater/
├── index.html            # ★ 웹앱 본체 (단일 자기완결 HTML, 8탭 SPA, ~1100줄)
│                         #   인라인 CSS+JS, CDN: Chart.js·Leaflet. 여기를 고치면 됨.
├── README.md             # GitHub 메인 소개
├── HANDOFF.md            # ← 지금 이 파일
├── LICENSE               # MIT
├── .gitignore
├── mcp/
│   ├── kwater_hydro_mcp.py            # MCP 서버 (fastmcp, 도구 9종, ~790줄)
│   ├── requirements.txt
│   └── claude_desktop_config.example.json
└── docs/
    ├── DEPLOY.md          # GitHub Pages 배포 상세 가이드
    └── DATA_DICTIONARY.md # HRFCO API 데이터 사전 (필드·단위·위험도 로직) ★기술 SSOT
```

---

## 3. 핵심 기술 사실 (반드시 알아야 디버깅 가능)

이건 추측이 아니라 **2026-06-15 한국 PC에서 실제 호출로 검증**한 사실들입니다.

1. **HRFCO API는 한국 네트워크에서만 호출됨.** 해외/해외VPN이면 `.go.kr`이 차단되어 데이터가 안 옴.
2. **CORS 개방**: 응답에 `Access-Control-Allow-Origin: *` → 브라우저가 직접 호출 가능 → 백엔드·프록시 불필요(정적 웹앱으로 충분).
3. **HTTPS 필수**: 웹앱은 반드시 `https://api.hrfco.go.kr` 사용. GitHub Pages가 https라서 http로 부르면 "혼합 콘텐츠"로 전부 차단됨. (코드 `index.html`의 `const BASE`에 https로 박혀 있음.)
4. **`content` 배열에 `null` 빈 슬롯이 섞여 옴** (댐 71건 중 16건). → `apiGet()`에서 `.filter(x=>x&&typeof x==="object")`로 거름. **새 데이터 소스 추가 시 이 필터 잊지 말 것.**
5. **현재 시각(부분 집계 중인 시간대) 행은 값이 비어서 옴.** → 그냥 마지막 행 쓰면 "데이터 없음"으로 보임. **반드시 "값이 채워진 최신 행" 사용**: 웹앱 `latestValued(arr,key)`, MCP `_latest_valued(rows,key)`.
6. **시계열은 내림차순(최신이 앞)으로 옴** → `sortAsc()`(웹) / `_sorted_by_time()`(MCP)로 오름차순 정렬 후 차트.
7. **Chart.js 스파크라인 높이**: 반응형 캔버스는 반드시 고정 높이 부모(`.spark-wrap` 40px, `.canvas-holder` 300px) 안에 둘 것. 안 그러면 무한 확대됨.
8. **인증키(데모)**: `9A3A6678-2E77-43F0-841B-F2368978107B`. 웹앱은 설정 탭에서 localStorage에 저장(기본값으로 미리 박혀 있음). HRFCO 무료·공공데이터·localhost용 키라 공개 노출 위험은 낮음(소장님 동의 하에 기본값 유지).

### HRFCO API 패턴 요약
- 목록: `https://api.hrfco.go.kr/{KEY}/{type}/info.json`
- 시계열: `https://api.hrfco.go.kr/{KEY}/{type}/list/{TIME}/{코드}/{sdt}/{edt}.json`
  - `{type}` = `dam`|`waterlevel`|`rainfall`|`bo` / `{TIME}` = `10M`|`1H`|`1D` / 시각 = `YYYYMMDDHHmm`
- 자세한 필드 정의는 `docs/DATA_DICTIONARY.md`.

---

## 4. 작업 히스토리 (이번 세션에 한 것)

시작점: 소장님이 받은 "프롬프트 쳤을 때 나오는" 형태의 MCP 파일 3개(`kwater_hydro_mcp.py`, README, config)만 있던 폴더.
목표: 이걸 **브라우저로 보는 실제 웹서비스 + 강화 MCP**로 재구성 → GitHub 배포.

1. **탐색·검증** — 폴더의 기존 3파일을 읽고, 한국 PC라는 점을 이용해 HRFCO API를 실제 호출. CORS 개방·필드 구조·null 슬롯·내림차순 정렬 등을 직접 확인(기존 README는 "해외라 검증 못 함"이라 적혀 있었음).
2. **에이전트 팀 병렬 가동 (하네스 엔지니어링)** — 검증된 API 스펙을 SSOT 문서로 만들어 4개 에이전트에 배포:
   - MCP 빌더 → 도구 4종 → **9종**으로 확장(`flood_briefing` 킬러 도구 포함)
   - 웹앱 빌더 → 단일 HTML 8탭 SPA
   - 문서 빌더 → README·DEPLOY·DATA_DICTIONARY·LICENSE·.gitignore
   - QA 검증 에이전트 → 교차 검증 + 문서/구현 정합성(도구 9종, 탭 8개로 정정)
3. **직접 버그 수정** — "현재 시각 빈 값" 문제를 MCP·웹앱 양쪽에 `latestValued`/`_latest_valued` 폴백으로 수정.
4. **정리·배포** — 구버전 루트 파일 제거, 폴더 구조 정리, `git init` → public repo 생성 → push → GitHub Pages 활성화 → 라이브 200 확인.
5. **라이브 디버깅 (소장님 피드백 반영)**:
   - 🐛 "안되는디" → `content`의 null 슬롯으로 `null.obsnm` 에러 → `apiGet`에서 필터링하여 해결, 재배포.
   - 🐛 "대시보드 그래픽 깨짐"(스파크라인 무한 확대) → 클립보드 캡처를 직접 확인 → `.spark-wrap` 고정 높이 래퍼로 해결, 재배포.
6. **핸드오프 문서 작성** (이 파일).

---

## 5. 알려진 한계 & 다음에 할 일 (TODO 후보)

이어서 작업할 때 고를 수 있는 작업들:

### 검증/마무리
- [ ] 나머지 탭 실제 동작 확인: **지도, 댐 상세, 하천 수위, 강수 현황, 기상 예보, 수문 브리핑** — 깨지는 곳 없는지 브라우저에서 점검(특히 차트·지도 마커).
- [ ] 모바일/태블릿 반응형 실제 확인.
- [ ] `docs/screenshot.png` 추가 (README가 참조하는 placeholder. 대시보드 캡처 넣으면 GitHub에서 미리보기 예쁨).

### 기능 확장 아이디어
- [ ] **보(洑) 탭 추가** — 현재 미구현. HRFCO `bo` 타입 데이터 존재(DATA_DICTIONARY에 문서화됨). 4대강 보 수위/방류 추가 가능.
- [ ] **저수율(%) 표시** — 현재는 저수위(EL.m)만. 총저수용량 데이터를 별도 확보하면 저수율 게이지 가능(HRFCO info엔 총용량 없음 → 외부 데이터 필요).
- [ ] **홍수특보 연동** — HRFCO 또는 기상청 특보 API로 실시간 경보 배너.
- [ ] **관심 관측소 즐겨찾기**(localStorage) / **자동 새로고침 주기 UI** 강화.
- [ ] **데이터 다운로드**(CSV) 버튼.
- [ ] **강의 모드** — 시연용으로 특정 댐·기간을 미리 세팅한 프리셋.

### 운영
- [ ] 데모키 → 소장님 전용키로 교체 시: 웹앱 설정 탭 + `mcp/kwater_hydro_mcp.py` 상단 + README/DATA_DICTIONARY의 키 문자열 교체.
- [ ] (선택) vault 정리: `kwater/`가 부모 vault git repo 안에 중첩됨. vault 자동백업이 서브모듈로 잡으면 지저분 → 필요시 vault `.gitignore`에 `kwater/` 추가.

---

## 6. 자주 쓰는 명령어 모음

```bash
# 작업 폴더로 이동
cd C:\Users\kimdu\claude\kwater

# 변경 후 배포
git add -A && git commit -m "메시지" && git push origin main

# Pages 빌드 상태
gh api repos/socialkim/kwater-hydro-watch/pages/builds/latest --jq .status

# MCP 서버 문법 검사
python -m py_compile mcp/kwater_hydro_mcp.py

# MCP 킬러 도구 직접 테스트 (UTF-8 출력)
$env:PYTHONIOENCODING="utf-8"; python -c "import importlib.util; s=importlib.util.spec_from_file_location('m','mcp/kwater_hydro_mcp.py'); m=importlib.util.module_from_spec(s); s.loader.exec_module(m); f=m.flood_briefing; print((getattr(f,'fn',f))('대청댐'))"

# HRFCO API 직접 확인 (한국 PC에서)
curl "https://api.hrfco.go.kr/9A3A6678-2E77-43F0-841B-F2368978107B/dam/info.json"
```

---

## 7. MCP 도구 9종 (강의 시연 참고)

| 도구 | 키 필요 | 설명 |
|---|---|---|
| `rain_forecast` | ❌ | 지역/댐 유역 강수 예보 (Open-Meteo) |
| `weather_now` | ❌ | 현재 기상 실황 |
| `dam_observatory` | ✅ | 댐 관측소 검색 |
| `dam_status` | ✅ | 댐 수위·유입·방류 + 위험도 판정 |
| `waterlevel_observatory` | ✅ | 하천 수위관측소 검색 |
| `waterlevel_status` | ✅ | 하천 수위·유량 + 주의/경계/경보/심각 단계 |
| `rainfall_observatory` | ✅ | 강수량관측소 검색 |
| `rainfall_status` | ✅ | 강수량 시계열·누적 |
| **`flood_briefing`** | ✅ | ★킬러: 댐 이름 하나로 검색→실측→예보를 종합 브리핑(도구 연쇄 호출 시연용) |

**강의 킬러 프롬프트**: "대청댐 최근 수위와 이번 주 강수 예보를 종합해서 주간 수문 브리핑 만들어줘" → `flood_briefing` 한 방에 종합.
