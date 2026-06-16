# CodeMap AI

AI 코드베이스 온보딩 도우미 MVP입니다.

GitHub 저장소 URL을 입력하면 CodeMap AI가 저장소 구조를 분석하고, 여러 분석 agent의 진행 상태를 보여준 뒤, 신규 팀원이 읽기 쉬운 코드베이스 온보딩 리포트를 생성하는 흐름을 목표로 합니다.

현재 이 저장소는 팀 프로젝트 공유와 역할 분담을 위한 MVP scaffold입니다. 프론트엔드 화면, FastAPI mock backend, WebSocket 기반 진행 상태, 리포트 화면, 작업 분할 문서가 포함되어 있습니다.

## 공유 데모

팀원들과 바로 확인할 수 있는 배포 주소입니다.

[https://oosu.dev/codemap/example/](https://oosu.dev/codemap/example/)

## 핵심 기능

1. **프로젝트 등록**
   - GitHub repository URL 또는 로컬 경로를 입력합니다.
   - MVP backend는 mock 분석 job을 생성합니다.

2. **코드 맥락 및 관계망 이해**
   - 코드 구조, 주요 파일, 위험 지점, heatmap 형태의 분석 결과를 보여주는 화면을 제공합니다.
   - 현재는 mock 데이터 기반이며, 실제 clone 및 파일 분석 로직은 후속 구현 대상입니다.

3. **자율 탐색형 AI 코드 분석**
   - `static_analyzer`, `behavior_inferer`, `community_assessor`, `reporter` agent의 진행 상태를 WebSocket으로 표시합니다.
   - agent별 실행 시간과 완료 상태를 dashboard에서 확인할 수 있습니다.

4. **계층형 프로젝트 가이드북 자동 생성**
   - 분석 완료 후 JSON report와 HTML report를 표시합니다.
   - 신규 팀원이 읽을 수 있는 요약, 추천 작업, 위험 파일 정보를 담는 방향으로 확장합니다.

## 기술 스택

| 영역 | 기술 |
|---|---|
| Frontend | Next.js 16, React 19, TypeScript, Tailwind CSS v4 |
| UI/Interaction | Framer Motion, Three.js, Lucide React |
| Backend | FastAPI, Pydantic, Uvicorn |
| Realtime | WebSocket |
| Package Manager | pnpm |

## 프로젝트 구조

```text
codemap-share/
├── frontend/
│   ├── src/
│   │   ├── app/             # landing page, analyze dashboard
│   │   ├── components/      # UI components
│   │   ├── contexts/        # locale/theme app context
│   │   ├── hooks/           # WebSocket hook
│   │   ├── lib/             # API client, sanitizer, translations
│   │   └── types/           # frontend/backend shared contracts
│   ├── package.json
│   └── next.config.ts
│
├── backend/
│   ├── app/
│   │   ├── main.py          # FastAPI app, CORS, WebSocket route
│   │   ├── api/             # REST routes and progress bus
│   │   ├── agents/          # mock agent modules
│   │   ├── models/          # Pydantic schemas and config
│   │   ├── orchestrator/    # analysis planner scaffold
│   │   └── services/        # repo clone/store scaffold
│   └── pyproject.toml
│
├── docs/
│   └── core_features.md     # 파일 단위 작업 분할 명세서
├── docker-compose.yml
└── README.md
```

## 로컬 실행 방법

### 1. Backend 실행

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -e .
uvicorn app.main:app --reload --host 127.0.0.1 --port 8001
```

Backend 확인:

```bash
curl http://127.0.0.1:8001/health
curl http://127.0.0.1:8001/api/models
```

### 2. Frontend 실행

```bash
cd frontend
pnpm install
pnpm dev
```

브라우저에서 아래 주소를 엽니다.

[http://localhost:3000](http://localhost:3000)

Frontend는 기본적으로 `/api/*` 요청을 `http://127.0.0.1:8001/api/*`로 proxy합니다.

## 데모 확인 흐름

1. 랜딩 페이지에서 GitHub repository URL을 입력합니다.
2. `/analyze` 페이지로 이동합니다.
3. 왼쪽 panel에서 agent 진행 상태를 확인합니다.
4. 분석이 끝나면 오른쪽 report viewer에 결과가 표시됩니다.
5. 아래 history 영역에서 이전 분석 job을 다시 열 수 있습니다.

예시 입력:

```text
https://github.com/tiangolo/fastapi
https://github.com/numpy/numpy
https://github.com/vercel/next.js
```

## 팀 작업 문서

파일 단위 작업 분할 명세서는 아래 문서에 있습니다.

[docs/core_features.md](docs/core_features.md)

이 문서는 다음 6개 기능 축을 기준으로 frontend/backend 작업을 나누고 있습니다.

1. 프로젝트 기반 구축
2. 프로젝트 등록
3. 코드 맥락 및 관계망 이해
4. 자율 탐색형 AI 코드 분석
5. 계층형 프로젝트 가이드북 자동 생성
6. 검증/문서화/배포

## 현재 상태와 주의점

- 현재 backend 분석 결과는 대부분 mock 데이터입니다.
- `repo_cloner`, `analysis_store`, `planner`, agent modules는 실제 구현을 위한 scaffold 상태입니다.
- 배포 데모는 팀 공유와 UI/흐름 확인 목적입니다.
- `pnpm build`는 통과합니다.
- `pnpm lint`는 기존 코드의 `any` 타입과 React effect lint 규칙 때문에 아직 실패합니다. 후속 QA/Ops 작업에서 정리해야 합니다.
- 실제 API key, token, secret은 repository에 포함하지 않습니다.

## English Summary

CodeMap AI is an MVP scaffold for an AI-powered codebase onboarding assistant.

It lets a user enter a GitHub repository URL, starts a mock multi-agent analysis pipeline, streams progress through WebSocket, and renders a structured onboarding report for new developers.

Shared preview:

[https://oosu.dev/codemap/example/](https://oosu.dev/codemap/example/)

Local development:

```bash
# Backend
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -e .
uvicorn app.main:app --reload --host 127.0.0.1 --port 8001

# Frontend
cd frontend
pnpm install
pnpm dev
```

Open [http://localhost:3000](http://localhost:3000).
