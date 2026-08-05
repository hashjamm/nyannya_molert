# 🏗️ Sherlock-Alarm Backend Architecture

본 문서는 **Sherlock-Alarm (nyannya_molert)** 프로젝트의 백엔드 시스템 아키텍처, 데이터 흐름, 핵심 컴포넌트 구조 및 머메이드(Mermaid) 시각화 다이어그램을 설명합니다.

---

## 1. 시스템 전체 아키텍처 (Overall Architecture Diagram)

```mermaid
flowchart TD
    subgraph TRIGGERS["⏰ Trigger & Execution Layer"]
        A1["External Scheduler\n(cron-job.org)"] -->|POST repository_dispatch| A2["GitHub Actions Workflows\n(check-reservation.yml)"]
        A3["Manual Trigger\n(workflow_dispatch)"] --> A2
    end

    subgraph ENGINE["⚙️ Core Controller (src/main.py)"]
        A2 -->|Run python src/main.py| B1["main() Entrypoint"]
        B1 --> B2["Schedule Evaluator\n(src/config.py)"]
        
        B2 -->|Shift Off / Off-work| B3["Stop Execution"]
        B2 -->|Current < 11:30 KST| MODE1["Mode 1: Morning Emergency Mode"]
        B2 -->|11:30 <= Current <= End KST| MODE2["Mode 2: Daytime Work Mode"]
    end

    subgraph SCRAPING["🕸️ Web Scraping Engine (src/scraper.py)"]
        MODE1 -->|scrape_completed_early_reservations| C1["Playwright Async Chromium"]
        MODE2 -->|scrape_all_completed_reservations| C1
        C1 -->|HTTP/HTTPS| C2[("Sherlock Holmes Web\n(sherlock-holmes.co.kr)")]
    end

    subgraph DB["💾 Persistence Layer (src/db.py)"]
        MODE1 -->|Check Receipt Ack| D1["Pushover Receipt API"]
        MODE1 <-->|Get/Save Alarm State| D2[("Upstash Redis DB\n(REST API / TTL 24h)")]
        MODE2 <-->|Get/Save Today Reservations| D2
    end

    subgraph NOTIFICATION["📢 Notification Engine (src/notifier.py)"]
        MODE1 -->|Early Reservation Found & Not Acked| E1["send_emergency_alarm()\n(Priority 2 Siren / Retry 60s)"]
        MODE2 -->|Diff Detected: New/Canceled| E2["send_light_alarm()\n(Priority 0 Vibration / Light)"]
        
        E1 -->|HTTP POST| F1[("Pushover Notification API")]
        E2 -->|HTTP POST| F1
    end

    subgraph RECIPIENTS["📱 End Devices"]
        F1 -->|Emergency Alarm / Custom Sound| G1["User Device"]
        F1 -->|Emergency Alarm / Custom Sound| G2["NyanNya Device"]
    end

    classDef trigger fill:#e1f5fe,stroke:#0288d1,stroke-width:2px;
    classDef engine fill:#fff3e0,stroke:#f57c00,stroke-width:2px;
    classDef scraping fill:#e8f5e9,stroke:#388e3c,stroke-width:2px;
    classDef db fill:#f3e5f5,stroke:#7b1fa2,stroke-width:2px;
    classDef notification fill:#ffebee,stroke:#d32f2f,stroke-width:2px;

    class A1,A2,A3 trigger;
    class B1,B2,B3,MODE1,MODE2 engine;
    class C1,C2 scraping;
    class D1,D2 db;
    class E1,E2,F1 notification;
```

---

## 2. 모드별 시퀀스 다이어그램 (Sequence Diagrams)

### 2.1 Mode 1: 아침 긴급 알람 모드 (Morning Emergency Mode, `< 11:30 KST`)

아침 출근 전 지정된 시각(12:00) 이전의 조기 예약 완료 건을 감지하여 스마트폰 무음/방해금지 모드를 우회하는 비상 알람을 발송합니다. **Smart Silence** 메커니즘을 통해 사용자가 이미 알람을 확인(Ack)한 경우 2차 알람을 자동 차단합니다.

```mermaid
sequenceDiagram
    autonumber
    actor Scheduler as cron-job.org / GitHub Actions
    participant Main as src/main.py
    participant Config as src/config.py
    participant DB as src/db.py
    participant PushoverAPI as Pushover Receipt API
    participant Scraper as src/scraper.py
    participant Site as Sherlock Holmes Web
    participant Notifier as src/notifier.py
    participant Mobile as User & NyanNya Devices

    Scheduler->>Main: Execute main()
    Main->>Config: get_today_shift_info(now_kst)
    Config-->>Main: (is_shift_day=True, start_time="11:30", end_time="16:00/18:00")
    
    Note over Main: Current Time < 11:30 KST -> Mode 1 Triggered
    
    Main->>DB: get_morning_alarm_state(today_str)
    DB-->>Main: alarm_state (receipt_id)
    
    opt Exists receipt_id
        Main->>DB: check_pushover_ack(receipt_id, api_token)
        DB->>PushoverAPI: GET /1/receipts/{receipt_id}.json
        PushoverAPI-->>DB: {acknowledged: 1}
        DB-->>Main: is_acked = True
        Note over Main: ✨ Smart Silence Active! Skip execution.
    end

    Main->>Scraper: scrape_completed_early_reservations(url, limit_time="12:00")
    Scraper->>Site: Fetch Reservation Page via Playwright
    Site-->>Scraper: Rendered HTML Theme & Time Slots
    Scraper-->>Main: List of early reservations (e.g. Carder 11:30)

    alt Early Reservations Found
        Main->>Notifier: send_emergency_alarm(message)
        Notifier->>Mobile: POST /1/messages.json (Priority=2, sound=siren/maple, retry=60, expire=300)
        Notifier-->>Main: (success=True, receipt_id)
        Main->>DB: save_morning_alarm_state(today_str, receipt_id)
    else No Early Reservations
        Note over Main: No early slots detected. Finish safely.
    end
```

---

### 2.2 Mode 2: 근무 시간대 실시간 예약 변동 모드 (Daytime Work Mode, `11:30 ~ 18:00 KST`)

근무 시간 동안 10분 간격으로 전체 예약 상태를 스캔하여 직전 상태와 비교(Diffing)한 후, 신규 예약 또는 예약 취소 발생 시 가벼운 알림(Priority 0, 진동/음성)을 발송합니다.

```mermaid
sequenceDiagram
    autonumber
    actor Scheduler as cron-job.org / GitHub Actions
    participant Main as src/main.py
    participant Scraper as src/scraper.py
    participant Site as Sherlock Holmes Web
    participant DB as src/db.py
    participant Notifier as src/notifier.py
    participant Mobile as User & NyanNya Devices

    Scheduler->>Main: Execute main()
    Note over Main: 11:30 <= Current Time <= End Time KST -> Mode 2 Triggered

    Main->>Scraper: scrape_all_completed_reservations(url)
    Scraper->>Site: Fetch All Theme Reservations via Playwright
    Site-->>Scraper: Rendered HTML
    Scraper-->>Main: current_reservations (Future slots only)

    Main->>DB: get_today_reservations(today_str)
    DB-->>Main: prev_reservations

    alt First Scan of the Day
        Note over Main: Initial scan -> Save current state to DB without alert
    else Previous Data Exists (Diff Calculation)
        Note over Main: Calculate (curr_set - prev_set) & (prev_set - curr_set)<br/>Filter future slots > current_time
        opt New Reservations Detected
            Main->>Notifier: send_light_alarm(new_items, sound="vibrate", priority=0)
            Notifier->>Mobile: Send Push Notification (🆕 New Reservation)
        end
        opt Canceled Reservations Detected
            Main->>Notifier: send_light_alarm(canceled_items, sound="vibrate", priority=0)
            Notifier->>Mobile: Send Push Notification (❌ Canceled Reservation)
        end
    end

    Main->>DB: save_today_reservations(today_str, current_reservations)
    Note over DB: Save with 24h TTL (86400s)
```

---

## 3. 핵심 컴포넌트 명세 (Core Components)

| 컴포넌트 | 경로 | 주요 역할 및 기능 |
|---|---|---|
| **Workflow Pipeline** | [.github/workflows/check-reservation.yml](file:///c:/Users/lmh16/playground/nyannya_molert/.github/workflows/check-reservation.yml) | GitHub Actions 서버리스 파이프라인. `repository_dispatch` 및 `workflow_dispatch` 이벤트 수신, Python/Playwright 환경 빌드 및 Secrets 주입 후 스크립트 실행 |
| **Shift Config Evaluator** | [src/config.py](file:///c:/Users/lmh16/playground/nyannya_molert/src/config.py) | KST(UTC+9) 타임존 변환, 요일별 근무 스케줄 설정 파싱(`SHIFT_SCHEDULE_JSON` / 기본 월~수), 당일 근무 여부, 출퇴근 시간 및 시스템 시간/알람 상수(Single Source of Truth: `MONITOR_START_TIME`, `EARLY_THRESHOLD_LIMIT`, `PUSHOVER_RETRY`/`EXPIRE`) 중앙 반환 |

| **Main Orchestrator** | [src/main.py](file:///c:/Users/lmh16/playground/nyannya_molert/src/main.py) | 백엔드 진입점. 현재 시각 기반 실행 모드 분기(오프 / 오전 긴급 모드 / 근무 실시간 변동 모드) 및 모듈 간 비즈니스 오케스트레이션 |
| **Web Scraper Engine** | [src/scraper.py](file:///c:/Users/lmh16/playground/nyannya_molert/src/scraper.py) | Playwright Async Chromium 기반 셜록홈즈 아산점 웹 크롤러. 지수 백오프 재시도(Max 3회), 과거 슬롯 자동 오탐 방지 및 탐색 조기 종료 최적화 포함 |
| **State & Persistence Manager** | [src/db.py](file:///c:/Users/lmh16/playground/nyannya_molert/src/db.py) | Upstash Redis REST API 클라이언트. 24시간 TTL 연동, 당일 예약 목록 저장/조회, 아침 비상 알람 영수증(Receipt) 상태 및 Pushover Ack 확인 API 호출 |
| **Notification Dispatcher** | [src/notifier.py](file:///c:/Users/lmh16/playground/nyannya_molert/src/notifier.py) | Pushover HTTP REST API 클라이언트. 다중 사용자(`PUSHOVER_USER_KEY`) 개별 지원, 유저별 맞춤 사운드 매핑, Priority 2(긴급 무음 우회) / Priority 0(가벼운 진동) 전송 |

---

## 4. 데이터베이스 및 렌더링 상태 구조 (Data & State Schema)

Upstash Redis(REST API)에 저장되는 데이터 키 구조와 TTL 규격은 다음과 같습니다.

### 4.1 예약 변동 감지용 키 (`reservations:{YYYY-MM-DD}`)
* **Format**: JSON Array
* **TTL**: 86,400초 (24시간)
* **Example**:
```json
[
  {"theme": "Carder", "time": "11:30"},
  {"theme": "귀로여관", "time": "14:20"}
]
```

### 4.2 아침 긴급 알람 상태 키 (`morning_alarm:{YYYY-MM-DD}`)
* **Format**: JSON Object
* **TTL**: 86,400초 (24시간)
* **Example**:
```json
{
  "receipt": "r5x9q2m...",
  "sent_at": "09:40",
  "count": 1
}
```

---

## 5. 외부 서비스 연동 (External Dependencies)

```mermaid
graph LR
    System["Sherlock-Alarm System"] -->|1. REST API| Upstash["Upstash Redis\n(State Storage)"]
    System -->|2. HTTP POST| PushoverMsg["Pushover Message API\n(/1/messages.json)"]
    System -->|3. HTTP GET| PushoverAck["Pushover Receipt API\n(/1/receipts/{id}.json)"]
    System -->|4. Headless Browser| SherlockWeb["Sherlock Holmes Website\n(Reservation Target)"]
    CronJob["cron-job.org\n(External Scheduler)"] -->|5. Dispatch Webhook| GitHubActions["GitHub Actions API\n(Runner Host)"]
```
