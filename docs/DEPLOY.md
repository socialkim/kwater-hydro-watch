# 🚀 배포 가이드 — GitHub Pages

> **수문 워치(Hydro Watch)** 웹앱은 백엔드가 없는 **순수 정적 웹앱**입니다.
> `index.html` 하나만 호스팅하면 누구나 브라우저로 접속할 수 있습니다.
> (HRFCO API가 CORS를 개방해 브라우저가 직접 호출 — 서버·프록시 불필요)

소요 시간: 약 5분.

---

## 1. 로컬에서 먼저 실행해 보기

배포 전 동작을 확인하려면, 저장소를 내려받은 뒤 `index.html`을 **더블클릭**하면 됩니다.

- 별도 서버·빌드·설치 과정이 전혀 없습니다.
- 댐/하천/강수 데이터를 보려면 화면 상단에 **HRFCO 인증키**를 입력하세요. (발급법: [README](../README.md#-hrfco-인증키-발급-방법))
- 기상 예보·실황은 키 없이도 작동합니다.

> 💡 일부 브라우저에서 `file://`로 열 때 제한이 있으면, 간단한 로컬 서버를 띄워도 됩니다.
> ```bash
> # 저장소 폴더에서
> python -m http.server 8000
> # → 브라우저에서 http://localhost:8000 접속
> ```

---

## 2. GitHub 저장소 생성 & 푸시

### (1) 새 저장소(repository) 생성
1. GitHub에 로그인 → 우측 상단 **＋ → New repository**
2. 저장소 이름 입력 (예: `hydro-watch`)
3. **Public**으로 설정 (GitHub Pages 무료 호스팅은 Public에서 가장 간단)
4. **Create repository** 클릭

### (2) 로컬 프로젝트를 푸시
이미 git 저장소라면 원격만 연결해 푸시합니다.

```bash
git init                 # (이미 했다면 생략)
git add .
git commit -m "init: 수문 워치 웹앱 + MCP 서버"
git branch -M main
git remote add origin https://github.com/<사용자명>/<저장소명>.git
git push -u origin main
```

> ⚠️ **중요:** `index.html`은 반드시 **저장소 루트(root)** 에 있어야 합니다.
> (이 프로젝트는 이미 루트에 위치합니다. 하위 폴더로 옮기면 아래 Pages 설정에서 폴더를 맞춰줘야 합니다.)

---

## 3. GitHub Pages 활성화

1. 저장소 페이지 상단 **Settings** 탭 클릭
2. 좌측 사이드바에서 **Pages** 클릭
3. **Build and deployment → Source**에서 **Deploy from a branch** 선택
4. **Branch**를 다음과 같이 지정:
   - 브랜치: **`main`**
   - 폴더: **`/ (root)`**
5. **Save** 클릭

저장하면 상단에 배포가 시작되고, 1~2분 뒤 공개 URL이 나타납니다.

```
https://<사용자명>.github.io/<저장소명>/
```

---

## 4. URL 확인 & 점검

- 위 URL을 브라우저에서 열어 웹앱이 뜨는지 확인합니다.
- 화면이 비어 보이면:
  - **1~2분 대기** 후 새로고침 (첫 배포는 시간이 걸릴 수 있음)
  - **Settings → Pages**에서 폴더 설정이 `/ (root)`인지 확인
  - 브라우저 캐시 강력 새로고침 (`Ctrl/Cmd + Shift + R`)
- 댐/하천 데이터가 안 나오면 상단에 **HRFCO 인증키**를 입력했는지 확인하세요.

---

## 5. (선택) 커스텀 도메인 연결

자체 도메인(예: `hydro.example.com`)을 쓰려면:

1. **Settings → Pages → Custom domain**에 도메인 입력 후 **Save**
2. 도메인 등록기관(DNS)에서 레코드 추가:
   - **서브도메인** (`hydro.example.com`): `CNAME` → `<사용자명>.github.io`
   - **루트 도메인** (`example.com`): GitHub의 `A` 레코드 IP 4개 등록
     (`185.199.108.153`, `185.199.109.153`, `185.199.110.153`, `185.199.111.153`)
3. DNS 전파(최대 24시간) 후 **Enforce HTTPS** 체크

> 커스텀 도메인을 쓰면 저장소 루트에 `CNAME` 파일이 자동 생성됩니다. 삭제하지 마세요.

---

## 6. 업데이트 배포

코드를 고친 뒤 다시 푸시하면 GitHub Pages가 자동으로 재배포합니다.

```bash
git add .
git commit -m "update: ..."
git push
```

> 🔒 **보안:** 공개 저장소에는 데모 인증키가 그대로 노출됩니다.
> 외부에 정식 공개할 때는 README의 [보안 주의](../README.md#-보안-주의-security-note) 항목을 참고해 **본인 키로 교체**하세요.
