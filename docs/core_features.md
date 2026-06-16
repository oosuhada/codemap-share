# CodeMap AI 프로젝트 파일 단위 상세 작업 분할 명세서 (v2)

기존의 추상적인 4대 핵심 기능(Phase 1)을 넘어서, **현재 구현되어 있는 `/Users/gabriel/Development/fastapi-reference/codemap/codemap-ai` 프로젝트의 모든 실제 파일(Frontend/Backend)을 기준**으로 작업 명세서를 분할했습니다. 팀 프로젝트 역할 분담(WBS)을 위해 최대한 잘게 쪼개어 구성했습니다.

> [!NOTE]
> 🏗️ **명세서 읽는 법**
> - **계층/디렉토리**: `Frontend (frontend/src/...)` 와 `Backend (backend/app/...)` 로 물리적 경로를 엄격히 분리했습니다.
> - **대상 파일**: 실제 개발자가 코드를 작성하거나 수정해야 할 정확한 파일명입니다.
> - **기능 ID**: `{대분류}-{모듈}-{F/B}-{일련번호}` 규칙 준수.

---

## 🎨 [Frontend] 1. GLOBAL-UI (전역 설정 및 공통 레이아웃)
**경로**: `frontend/src/`
앱 전역의 레이아웃, 다국어(i18n), 테마(Theme) 및 타입 정의를 관리합니다.

| ID | 대분류 | 모듈 | 계층 | 기능명 | 대상 파일 | 상세 설명 | 우선순위 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **GLOBAL-UI-F-01** | GLOBAL | APP | F | 최상위 레이아웃 구성 | `app/layout.tsx` | HTML/Body 뼈대, 글로벌 폰트 적용, Next.js 메타데이터, `AppContext` Provider 주입 | P0 |
| **GLOBAL-UI-F-02** | GLOBAL | CSS | F | 전역 CSS 및 테마 변수 | `app/globals.css` | Tailwind CSS 초기화 및 Light/Dark 모드 대응을 위한 `var(--bg-primary)` 등 CSS 변수 선언 | P0 |
| **GLOBAL-CTX-F-01**| GLOBAL | CTX | F | 전역 상태 관리 컨텍스트 | `contexts/AppContext.tsx`| `localStorage`를 연동하여 다국어(ko/en) 및 테마(light/dark) 상태를 전역 컴포넌트에 공급 | P0 |
| **GLOBAL-I18N-F-01**| GLOBAL | I18N | F | 다국어 사전 (Dictionary) | `lib/translations.ts` | 하드코딩 텍스트를 제거하기 위한 영/한 다국어 번역 객체(`t`) 정의 | P0 |
| **GLOBAL-TYPE-F-01**| GLOBAL | TYPE | F | 클라이언트 타입 정의 | `types/contracts.ts` | 백엔드 API 응답과 통일성을 맞추기 위한 TypeScript 인터페이스(DTO) 정의 | P0 |

---

## 🚀 [Frontend] 2. LANDING-PAGE (메인 랜딩 페이지)
**경로**: `frontend/src/`
사용자가 처음 접속하는 홈페이지(`.com/`)의 UI 및 애니메이션 컴포넌트입니다.

| ID | 대분류 | 모듈 | 계층 | 기능명 | 대상 파일 | 상세 설명 | 우선순위 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **LAND-PAGE-F-01** | LANDING | PAGE | F | 메인 랜딩 페이지 조립 | `app/page.tsx` | 네비게이션, 히어로, 벤토 그리드, 푸터 등 랜딩 페이지 컴포넌트 배치 | P0 |
| **LAND-NAV-F-01** | LANDING | NAV | F | 헤더 네비게이션 | `components/Navbar.tsx` | 서비스 로고, 언어 전환(EN/KR) 버튼, 테마 전환(해/달) 토글 버튼 UI | P0 |
| **LAND-HERO-F-01** | LANDING | HERO | F | 3D 히어로 섹션 UI | `components/hero/AsciiScene.tsx`| 랜딩 최상단의 Three.js 캔버스 렌더링 및 테마(Dark/Light)에 따른 배경색 동기화 | P2 |
| **LAND-HERO-F-02** | LANDING | HERO | F | 3D ASCII 이펙트 코어 | `components/hero/ascii-effect.ts` | 3D 모델을 ASCII 문자로 변환하는 커스텀 Three.js 렌더러 로직 | P2 |
| **LAND-FEAT-F-01** | LANDING | FEAT | F | 터미널 모의 데모 UI | `components/InteractiveDemo.tsx`| 사용자가 서비스 작동 방식을 미리 볼 수 있는 가상 터미널 애니메이션 | P1 |
| **LAND-FEAT-F-02** | LANDING | FEAT | F | 벤토 그리드 기능 소개 | `components/BentoFeatures.tsx` | 주요 기능(아키텍처 맵핑 등)을 카드 형태로 나열하는 Bento Grid 컴포넌트 | P1 |
| **LAND-FOOT-F-01** | LANDING | FOOT | F | 공통 푸터 영역 | `components/CodeMapFooter.tsx` | (또는 `Footer.tsx`) 하단 링크, 소셜 아이콘 및 정보 제공 | P2 |
| **LAND-SEC-F-01** | LANDING | SEC | F | 보안 고지 배너 | `components/SecurityBanner.tsx` | "코드를 저장하지 않습니다" 등 신뢰도를 높이기 위한 보안 정책 배너 | P2 |

---

## 🔍 [Frontend] 3. ANALYZE-DASHBOARD (저장소 연동 및 분석 대시보드)
**경로**: `frontend/src/`
저장소를 연동하고 실시간 분석 과정을 확인하며, 최종 리포트를 열람하는 핵심 화면입니다.

| ID | 대분류 | 모듈 | 계층 | 기능명 | 대상 파일 | 상세 설명 | 우선순위 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **DASH-PAGE-F-01** | DASH | PAGE | F | 분석 페이지 레이아웃 | `app/analyze/page.tsx` | `/analyze` 라우트 진입점. URL 파라미터(`path`)를 파싱하여 분석 시작 및 Skeleton UI 제어 | P0 |
| **DASH-INPUT-F-01** | DASH | INPUT | F | 저장소 입력 폼 | `components/RepoInput.tsx` | GitHub URL / 로컬 경로 입력 UI, 유효성 검증 및 API 호출, 버튼 로딩 상태 | P0 |
| **DASH-HIST-F-01** | DASH | HIST | F | 과거 분석 이력 목록 | `components/HistoryList.tsx` | `lib/api.ts`를 통해 이력을 불러와 최근 분석 레포지토리 목록 제공 | P0 |
| **DASH-PROG-F-01** | DASH | PROG | F | 에이전트 실시간 진행 패널| `components/ProgressPanel.tsx` | 여러 에이전트의 진행률, 현재 상태(Pending/Running 등), 로그를 스트리밍하여 시각화 | P0 |
| **DASH-VIEW-F-01** | DASH | VIEW | F | 마스터 리포트 뷰어 | `components/ReportViewer.tsx` | 분석 완료된 JSON을 받아 요약, 취약점, 커뮤니티 지표 등 최종 마크다운 리포트 렌더링 | P0 |
| **DASH-CHART-F-01** | DASH | CHART | F | 파일 리스크 히트맵 | `components/HeatmapChart.tsx` | 파일 경로와 위험도 데이터를 기반으로 트리맵 형태의 색상 히트맵 구현 | P1 |
| **DASH-TIME-F-01** | DASH | TIME | F | 에이전트 소요 시간 패널 | `components/AgentDurationsPanel.tsx`| `static_analyzer`, `behavior_inferer` 등 각 에이전트가 소요한 시간 통계 차트 | P1 |
| **DASH-HOOK-F-01** | DASH | HOOK | F | 웹소켓 커스텀 훅 | `hooks/useWebSocket.ts` | WebSocket 객체 생성, 재연결, 이벤트 리스닝 로직을 추상화한 Hook | P0 |
| **DASH-API-F-01** | DASH | API | F | 백엔드 API 통신 모듈 | `lib/api.ts` | Axios/Fetch를 이용해 백엔드 REST 엔드포인트(`POST /analysis`, `GET /history`) 호출 래핑 | P0 |
| **DASH-UTIL-F-01** | DASH | UTIL | F | HTML XSS 렌더링 방어 | `lib/sanitize.ts` | 마크다운을 HTML로 변환하여 렌더링할 때 발생할 수 있는 XSS 취약점 방어(DOMPurify 등) | P1 |

---

## ⚙️ [Backend] 4. CORE-API (FastAPI 라우팅 및 서버 설정)
**경로**: `backend/app/`
FastAPI 서버의 진입점, 데이터 스키마 정의 및 REST API 라우터를 관리합니다.

| ID | 대분류 | 모듈 | 계층 | 기능명 | 대상 파일 | 상세 설명 | 우선순위 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **CORE-MAIN-B-01** | CORE | MAIN | B | 서버 진입점 및 미들웨어 | `main.py` | FastAPI 인스턴스 생성, CORS 정책 설정, 에러 핸들러 및 라우터 등록 | P0 |
| **CORE-ROUTE-B-01**| CORE | ROUTE | B | 메인 REST API 라우트 | `api/routes.py` | 분석 시작(`POST /api/analysis`), 이력 조회(`GET`), 리포트 조회 엔드포인트 로직 | P0 |
| **CORE-WS-B-01** | CORE | WS | B | 웹소켓 라우트 및 매니저 | `api/routes.py` | `ws://.../progress/{job_id}` 소켓 연결 수립, 클라이언트 세션 관리 | P0 |
| **CORE-HEALTH-B-01**| CORE | HEALTH | B | 서버 상태 검사 라우트 | `api/health.py` | 무중단 배포 및 로드밸런서를 위한 Health Check (`GET /health`) | P0 |
| **CORE-SCHEMA-B-01**| CORE | SCHEMA| B | 데이터 유효성 검사 스키마| `models/schemas.py` | Pydantic을 이용한 Request/Response DTO 정의 (타입 힌팅 및 직렬화) | P0 |
| **CORE-CONF-B-01** | CORE | CONF | B | 환경 변수 및 설정 관리 | `models/config.py` | `.env` 로드, 서버 포트, 허용 도메인, 외부 API 키 등 전역 설정 객체 관리 | P0 |

---

## 🗄️ [Backend] 5. REPO & STORE (저장소 관리 및 데이터 캐싱)
**경로**: `backend/app/services/`
사용자 요청에 따라 Git을 복제하고 분석 결과를 데이터베이스(또는 메모리)에 저장하는 계층입니다.

| ID | 대분류 | 모듈 | 계층 | 기능명 | 대상 파일 | 상세 설명 | 우선순위 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **SVC-CLONE-B-01** | SVC | CLONE | B | Git 저장소 클론 관리자 | `services/repo_cloner.py` | `subprocess`를 이용한 얕은 복제(Shallow Clone) 및 로컬 임시 마운트 로직 | P0 |
| **SVC-FILTER-B-01**| SVC | FILTER| B | 노이즈 파일 필터링 | `services/repo_cloner.py` | 분석에 불필요한 `node_modules`, `dist`, `__pycache__` 등을 자동 스캔 후 제외 | P0 |
| **SVC-STORE-B-01** | SVC | STORE | B | 분석 잡(Job) 상태 저장소 | `services/analysis_store.py`| 분석 진행 중인 Job의 메타데이터(상태, 시작시간 등)를 메모리/DB에 캐싱 | P0 |
| **SVC-STORE-B-02** | SVC | STORE | B | 마스터 리포트 이력 조회 | `services/analysis_store.py`| 분석이 완료된 JSON 결과를 저장하고 클라이언트 요청 시 반환하는 CRUD 로직 | P1 |

---

## 🤖 [Backend] 6. AGENT & ORCHESTRATOR (다중 에이전트 제어망)
**경로**: `backend/app/agents/` 및 `orchestrator/`
실제 AI 모델과 상호작용하며 코드를 분석하는 도메인 특화 에이전트와 이들을 조율하는 오케스트레이터입니다.

| ID | 대분류 | 모듈 | 계층 | 기능명 | 대상 파일 | 상세 설명 | 우선순위 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **ORCH-PLAN-B-01** | ORCH | PLAN | B | 에이전트 실행 오케스트레이터| `orchestrator/planner.py` | 사용자의 분석 요청을 하위 에이전트 태스크로 분할하고 비동기(Async) 병렬 실행 스케줄링 | P0 |
| **ORCH-BUS-B-01** | ORCH | BUS | B | 이벤트 메세지 버스 | `api/progress_bus.py` | 각 에이전트가 실행 중 남기는 로그와 퍼센티지를 모아 WebSocket 라우터로 브로드캐스트 | P0 |
| **AGENT-MAP-B-01** | AGENT | MAP | B | 정적 구조 분석 에이전트 | `agents/code_mapper.py` | (`static_analyzer`) AST 구문 분석을 통해 디렉토리 구조, 의존성 관계, Entry Point 식별 | P0 |
| **AGENT-DOC-B-01** | AGENT | DOC | B | 문서/주석 생성 에이전트 | `agents/doc_generator.py` | (`behavior_inferer`) 복잡한 비즈니스 로직과 Data Flow를 파악하여 컴포넌트별 요약 수행 | P0 |
| **AGENT-GUIDE-B-01**| AGENT | GUIDE | B | 마스터 리포트 취합 에이전트| `agents/onboarding_guide.py`| (`reporter` & `community_assessor`) 이전 에이전트들의 결과를 취합, LLM Judge로 충돌 해결 후 최종 JSON 반환 | P0 |
