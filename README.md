# 🔨 Product Forge With AI

업무 요청·장애 처리 SaaS **OpsDesk**를 기획부터 운영·개선까지 AI와 함께 만드는 터미널 학습 게임입니다. 단계마다 "어떤 도구의 어떤 기능을 왜 쓰는지" 알고, AI에게 지시하고 결과를 검증할 수 있게 되는 것이 목표입니다.

- 설계서: [docs/design.md](docs/design.md) (v0.3.5, 2026-11-09)
- 요구사항(PRD)·데이터 구조(ERD)·명세(Spec): [docs/PRD.md](docs/PRD.md), [docs/ERD.md](docs/ERD.md), [docs/SPEC.md](docs/SPEC.md)
- 용어집·결정 기록·정보 구조·사용자 여정: [docs/GLOSSARY.md](docs/GLOSSARY.md), [docs/adr/](docs/adr/), [docs/IA.md](docs/IA.md), [docs/USER-JOURNEY.md](docs/USER-JOURNEY.md)
- 구성: 18장(기반 도구 → 기획 → 설계 → 백엔드 → 비동기 → 프론트엔드 → 테스트 → 컨테이너 → 배포 → CI/CD → 쿠버네티스 비교 → 클라우드·IaC → 운영 → 제품 안의 AI → 분석·개선 → 최종)
- 상태: 엔진 M0 게이트 승인(2026-11-13), M1 중 Windows에서 할 수 있는 작업 완료(2026-11-14). 다음은 맥에서 OrbStack 랩과 사용자 QA, 그다음 콘텐츠. 작업 순서는 [docs/PLAN.md](docs/PLAN.md), 현재 작업은 [Intent.md](Intent.md)
- 맥 준비 점검: `bash scripts/check-mac.sh` — 이미 설치된 것과 빠진 것, 설치 명령을 보여 준다(읽기만 한다)

## 맥에서 시작하기

1. 준비 점검: `curl -fsSL https://raw.githubusercontent.com/sikomar00/product-forge-with-ai/main/scripts/check-mac.sh -o check-mac.sh && bash check-mac.sh` — 마지막 '필요한 것'만 차례로 한다.
2. 엔진 받기: `git clone https://github.com/sikomar00/product-forge-with-ai.git ~/code/product-forge-with-ai && cd ~/code/product-forge-with-ai && uv sync`
3. 점검: `uv run quest doctor` (콘텐츠를 받기 전에는 엔진 쪽만 본다)
4. 어디서나 `quest`로 부르기(선택): `echo "alias quest='uv run --project ~/code/product-forge-with-ai quest'" >> ~/.zshrc && source ~/.zshrc`
5. 처음 `quest`를 실행하면 설정 파일(`~/.config/quest/config.toml`)을 만든다. `<GitHub 사용자 이름>` 두 곳을 내 값으로 바꾼다.
6. 콘텐츠 리포(비공개)가 생긴 뒤: `gh auth login` → `quest update` → `quest`
- 선택 연결 트랙: [tech-radar-agent](https://github.com/sikomar00/tech-radar-agent)

> 등장하는 회사(포지랩)·인물·데이터는 모두 가상이며, 이 게임은 AI와 함께 만든 학습 도구입니다.
