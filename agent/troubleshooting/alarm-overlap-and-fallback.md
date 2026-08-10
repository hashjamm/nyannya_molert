# 🛠️ Troubleshooting Guide: Alarm Expire & Fallback Controls

본 문서는 Sherlock-Alarm 운영 중 발견 및 해결된 특수 버그, 오탐 방지 로직 및 예외 처리 정책을 정리한 온디맨드 트러블슈팅 가이드입니다.

---

## 1. Pushover 긴급 알람 만료시간 (`PUSHOVER_EXPIRE`) 설정 및 중복 방지

### 문제 상황
GitHub Actions 감시 스케줄러가 10분 간격으로 작동하는 환경에서, 조기 예약을 감지하여 Pushover `priority=2` (Emergency Siren) 알람을 발생시킨 후 수신자가 5분 이상 알람을 확인(Acknowledge)하지 않을 경우, 다음 10분 차 감시에서 동일(또는 신규) 예약에 대해 두 번째 긴급 알람이 수신되어 스마트폰상에 알람 2개가 동시에 겹쳐서 울리는 현상이 발생함.

### 원인 및 분석
Pushover의 `expire` 속성이 기본값(1시간=3600초)으로 길게 유지되어 있을 경우, 이전 감시에서 발생한 영수증(Receipt)이 아직 활성 상태인 동안 다음 스케줄러가 새 영수증을 생성하여 스마트폰 알림 센터에 이중 비상 사이렌이 팝업됨.

### 조치 메커니즘 & 해결책
- `PUSHOVER_EXPIRE`(만료 시간)는 반드시 **감시 주기(10분 = 600초)보다 짧은 값(예: 300초 = 5분)**으로 설정.
- 다음 10분 주기 감시가 시작되기 전에 이전 알람이 자동으로 만료되어 사라지도록 하여 중복 겹침 현상을 원천 방지. (기본 추천값: `300`초)

---

## 2. GitHub Secrets 미등록 시 환경변수 빈 문자열(`""`) 폴백

### 문제 상황
GitHub Secrets에 `SHERLOCK_URL` 또는 `EARLY_THRESHOLD_LIMIT`가 정의되어 있지 않은 경우, GitHub Actions 워크플로우 런타임에서 해당 변수가 빈 문자열(`""`)로 주입되어 Python `datetime.strptime()`에서 `time data '' does not match format` 파싱 에러 발생.

### 해결책
1. **Python 코드 내 이중 방어**:
   ```python
   target_url = os.getenv("SHERLOCK_URL") or "https://sherlock-holmes.co.kr/reservation/index.php?sido=12&bno=86#reservation"
   ```
   `or` 연산자를 활용해 빈 문자열이 반환되더라도 하드코딩된 안전한 기본값으로 자동 전환.
2. **Workflow YAML 방어**:
   ```yaml
   SHERLOCK_URL: ${{ secrets.SHERLOCK_URL || 'https://sherlock-holmes.co.kr/reservation/index.php?sido=12&bno=86#reservation' }}
   ```

---

## 3. 시간 경과에 따른 과거 예약 슬롯 자동 마감 오탐 방지

### 문제 상황
셜록홈즈 예약 웹사이트 특성상 시간이 흐르면 이미 지나간 과거 예약 슬롯(예: 현재가 15:00일 때 13:00 슬롯)이 웹사이트 상에서 자동으로 '예약불가'(`.col.false`) 클래스로 전환됨. 이를 단순 스크래핑할 경우 '신규 예약이 발생했다'고 잘못 판단하여 오탐 알림이 울리는 이슈.

### 해결책
- `src/scraper.py` 및 `src/main.py` 크롤링 및 Diff 계산 시 **현재 시각보다 미래의 슬롯(`slot_time > current_time`)만 필터링**하여 수집.
- 과거 시간 슬롯의 상태 변경은 오탐 대상에서 원천 제외.

---

## 4. 아침 조기 출근 긴급 알람 10분 간격 중복 재발송 및 Smart Silence 개선

### 문제 상황
오전 조기 출근 비상 사이렌 알람 수신 후 수신자(냔냐님)가 스마트폰 알림 배너를 터치하거나 확인하였음에도 불구하고, Pushover API 상의 Ack 미처리 및 `PUSHOVER_EXPIRE`(5분) 만료 현상으로 인해 오전 내내 10분 간격 감시 때마다 비상 사이렌 알람이 11:20 출근 전까지 계속 반복 재발송되는 현상.

### 원인 및 분석
Pushover 스마트폰 알림 배너를 단순히 터치하거나 지우는 일반적인 사용 패턴으로는 Pushover API 상에 `acknowledged: 1` 상태가 전달되지 않음. 이에 따라 10분 주기 스케줄러가 실행될 때마다 "아직 확인되지 않았다"고 판단하여 10분마다 5분짜리 비상 사이렌 알람을 반복 재발송함.

### 해결책
- **당일 1회 발송 시 무조건 2차 재발송 차단 (Smart Silence)**:
  - 아침 조기 출근 알람은 1회 발송 시 5분 동안 1분 간격으로 총 5번의 비상 사이렌이 울리므로, 1회 발송만으로 조기 출근 알림 목적이 100% 달성됨.
  - `src/main.py`에서 당일 아침 비상 알람 발송 이력(`alarm_state`)이 DB에 존재한다면, Pushover API Ack 버튼 전달 여부와 상관없이 **당일 아침의 2차/3차 비상 사이렌 재발송을 무조건 스킵**하도록 개편하여 중복 울림을 완벽 차단.


