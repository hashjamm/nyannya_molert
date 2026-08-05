# 🚨 Sherlock-Alarm Agent Control Tower

본 문서는 Sherlock-Alarm 프로젝트의 최상위 컨트롤 타워 문서입니다. 모든 AI 에이전트는 작업 시작 전 본 문서를 가장 먼저 확인하고 가이드를 따라야 합니다.

---

## 1. 프로젝트 개요 (Overview)
* **목표**: 셜록홈즈 충청 대전 세종 - 아산점의 예약을 크롤링하여, 오전 조기 출근 시간(12:00 이전)에 완료된 예약 감지 시 Pushover 비상 사이렌 알람을 전송하고, 근무 시간대 예약 변동(신규/취소)을 실시간 추적합니다.
* **핵심 스택**: Python 3.10+, Playwright (Async Chromium), Pushover API, Upstash Redis (REST), GitHub Actions (Cron/Dispatch).

---

## 2. 📖 작업 유형별 필독 문서 가이드 (Reading Guide)

| 작업 유형 | 참고 필수 문서 | 설명 |
|---|---|---|
| 백엔드 / DB / 파이프라인 개편 | [ARCHITECTURE.md](file:///c:/Users/lmh16/playground/nyannya_molert/ARCHITECTURE.md) | 파이프라인 그래프, 시퀀스, Upstash Redis 스키마 & Pushover API |
| 신규 기능 / 백로그 / 확장 기획 | [ROADMAP.md](file:///c:/Users/lmh16/playground/nyannya_molert/ROADMAP.md) | 미완료 TODO, 차후 개발 액션 플랜 & B2B SaaS 로드맵 |
| UI/UX 및 프론트엔드 작업 | [Design.md](file:///c:/Users/lmh16/playground/nyannya_molert/Design.md) | 디자인 시스템, UI 가이드라인 & 컬러 토큰 |
| 알람 오류 / 트러블슈팅 대응 | [alarm-overlap-and-fallback.md](file:///c:/Users/lmh16/playground/nyannya_molert/agent/troubleshooting/alarm-overlap-and-fallback.md) | Pushover EXPIRE 만료, Secrets 폴백 & 과거 슬롯 오탐 이슈 |
| 히스토리 & 맥락 파악 | [agent/history.md](file:///c:/Users/lmh16/playground/nyannya_molert/agent/history.md) | 완료된 마일스톤 히스토리 전량 (100% 무손실 보존) |
| 환경변수 설정 및 Secrets 갱신 | [.env.example](file:///c:/Users/lmh16/playground/nyannya_molert/.env.example) | 백엔드/프론트엔드 통합 환경변수 명세 |

---

## 3. 디렉터리 구조 (Directory Map)
* `src/`: 메인 소스코드 ([main.py](file:///c:/Users/lmh16/playground/nyannya_molert/src/main.py), [config.py](file:///c:/Users/lmh16/playground/nyannya_molert/src/config.py), [scraper.py](file:///c:/Users/lmh16/playground/nyannya_molert/src/scraper.py), [db.py](file:///c:/Users/lmh16/playground/nyannya_molert/src/db.py), [notifier.py](file:///c:/Users/lmh16/playground/nyannya_molert/src/notifier.py))
* `agent/`: 차가운 메모리 아카이브 ([history.md](file:///c:/Users/lmh16/playground/nyannya_molert/agent/history.md), [troubleshooting/](file:///c:/Users/lmh16/playground/nyannya_molert/agent/troubleshooting/alarm-overlap-and-fallback.md))
* `data/`, `logs/`, `tools/`, `docs/archive/`: 데이터, 로그 및 유틸리티 보관소

---

## 4. 🚨 AI 에이전트 필수 행동 지침 (Crucial Guardrails)

> [!IMPORTANT]
> 1. **Git 버전 관리 제약**: `git commit`, `git push` 등 Git 커맨드는 에이전트 자의로 절대 실행하지 않으며, 오직 사용자가 명시적으로 요청한 경우에만 수행합니다.
> 2. **컨텍스트 보존 규정**: `project-context.md` 파일 구조를 함부로 변형하지 않으며, 히스토리는 절대로 삭제하지 않고 [agent/history.md](file:///c:/Users/lmh16/playground/nyannya_molert/agent/history.md)에 무손실 누적 기록합니다.
> 3. **알람 만료 시간(EXPIRE) 규정**: Pushover 중복 알람 겹침을 방지하기 위해 `PUSHOVER_EXPIRE`는 반드시 감시 주기(10분)보다 짧은 값(추천: 300초 = 5분)을 유지해야 합니다.
