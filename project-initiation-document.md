# **Sherlock-Alarm Project Initiation Document**

## **1\. 프로젝트 개요 (Background & Goal)**

* **배경**: 사용자의 여자친구(셜록홈즈 방탈출 카페 지점 아르바이트생, 별칭 '냔냐')는 기본 출근 시간인 11:30에 맞춰 늦잠을 자고 싶어 하나, 아침 첫 타임 예약(예: 11:20, 11:30 등)이 들어오면 평소보다 일찍 출근해야 하는 상황이 발생함. 이 때문에 자는 도중에도 수시로 깨서 예약을 확인해야 하는 심한 예약 스트레스를 겪고 있음.  
* **목표**: 매일 아침 특정 시간대에 해당 지점의 웹사이트를 자동으로 크롤링하여, 11:40 이전에 조기 출근해야 하는 예약 건이 발생하면 스마트폰으로 강력한 긴급 사이렌 알람(Pushover 활용)을 울려 수면을 보장하고 심리적 안정감을 제공함.

## **2\. 기술 스택 (Tech Stack)**

* **Language**: Python 3.10+  
* **Automation/Scraping**: Playwright (Async API) \- 동적 웹 페이지 로딩 및 요소 추출에 최적화  
* **Notification**: Pushover API (HTTP POST) \- 무음 모드를 돌파하는 priority=2(Emergency) 알림 사용  
* **Config Management**: python-dotenv (.env 파일로 중요 정보 분리 관리)  
* **CI/CD & Execution**: GitHub Actions (무료 무중단 예약 실행 엔진)

## **3\. 핵심 비즈니스 로직 & 워크플로우 (Core Logic & Workflow)**

1. **스케줄러 트리거**: 매일 아침 지정된 시간(예: 오전 8시, 9시, 10시)에 GitHub Actions 가상 서버가 작동하여 스크립트 실행.  
2. **웹 크롤링 (Playwright)**: 셜록홈즈 지점 예약 페이지에 접속하여 모든 테마의 시간대 정보를 동적으로 렌더링할 때까지 대기.  
3. **데이터 파싱 및 비교**:  
   * 화면에서 '예약 완료'에 해당하는 클래스 또는 스타일 속성을 가진 시간 정보를 모두 수집.  
   * 예시 이미지 분석 결과: 어두운 회색 배경의 시간 박스(예약 완료)와 황토색/금색 배경의 시간 박스(예약 가능)가 구분됨.  
4. **조기 출근 조건 검사**:  
   * 수집된 '예약 완료' 시간 중 조기 출근을 유발하는 임계 시간대인 오전 11:40 이전(예: 11:20, 11:30)이 포함되어 있는지 확인.  
5. **긴급 알람 발송**:  
   * 위 조건에 해당하는 예약이 발견되면 Pushover API를 통해 스마트폰으로 긴급 무음 무시(Emergency Bypass) 사이렌 알람을 발송함. (사용자가 스마트폰에서 직접 '확인'을 누를 때까지 일정 간격으로 무한 반복 재생)

## **4\. 권장 디렉토리 구조 (Directory Structure)**

sherlock-alarm/  
├── .github/  
│   └── workflows/  
│       └── check-reservation.yml  \# GitHub Actions 자동 실행 워크플로우 설정 파일  
├── .env                          \# 로컬 개발 및 테스트용 환경 변수 (Pushover 토큰, 예약 페이지 URL 등)  
├── .gitignore                    \# .env 및 \_\_pycache\_\_ 제외  
├── requirements.txt              \# 의존성 패키지 명세  
├── project-context.md            \# 프로젝트 개발 맥락 컨텍스트 (본 파일)  
└── src/  
    ├── \_\_init\_\_.py  
    ├── main.py                   \# 전체 프로세스 제어 및 예약 확인 주기 관리  
    ├── scraper.py                \# Playwright 기반 셜록홈즈 크롤러 모듈  
    └── notifier.py               \# Pushover API 연동 알람 발송 모듈

## **5\. 실행 및 배포 전략 (Deployment Strategy)**

### **\[Phase 1\] 로컬 검증 (Local Dev)**

* 개인 PC에서 수동으로 코드를 구동하여 크롤링 성공 여부와 스마트폰(Pushover) 알림 발송 동작을 완벽하게 검증함.

### **\[Phase 2\] GitHub Actions 이식 (MVP 릴리즈 \- 강력 추천)**

* **개념**: 별도의 개인 PC나 24시간 서버를 켜둘 필요 없이, GitHub의 서버리스 가상 컴퓨터 환경을 매일 아침 설정한 시간(Cron)에 무료 기동하여 알람을 전송함.  
* **장점**: 완전 무료 구동, 개인 기기 배터리 및 전력 소모 제로, 인프라 관리 불필요.  
* **단점**: 무료 공유 자원 특성상 크론 설정 대비 수 분에서 수십 분의 지연 실행(Delay)이 발생할 수 있음.

### **\[Phase 3\] 기능 확장 및 고도화 (Scale-up)**

* **Oracle Cloud Free Tier / AWS EC2 Free Tier**: 지연 실행 없는 정밀한 실행이 필요하거나, 예약 데이터 기록용 DB 및 냔냐님이 알람 감시 시간(예: 11:20 \-\> 11:50)을 직접 바꿀 수 있는 모바일/웹 대시보드로 확장 시 전환 도입을 검토함.

## **6\. 환경 변수 설정 명세 (.env)**

\# 셜록홈즈 대상 지점의 예약 페이지 URL  
SHERLOCK\_URL=\[https://sherlock-holmes.co.kr/reservation/index.php?sido=\](https://sherlock-holmes.co.kr/reservation/index.php?sido=)...

\# Pushover API 인증 정보  
PUSHOVER\_API\_TOKEN=your\_pushover\_application\_token\_here  
PUSHOVER\_USER\_KEY=your\_pushover\_user\_key\_here

\# 감시 대상 예약 타임 조건 (콤마 분리 형식)  
EARLY\_THRESHOLD\_TIMES=11:20,11:30,11:40

## **7\. 개발 규칙 및 예외 처리 가이드라인 (Development Guardrails)**

* **비동기 처리(Asynchronous)**: Playwright의 모든 크롤링 동작은 성능과 대기 시간 최적화를 위해 async/await 구조로 작성해야 함.  
* **예외 복구(Robustness)**: 네트워크 문제나 사이트의 일시적 장애에 대비하여 크롤링 실패 시 최대 3회 재시도(Exponential Backoff 적용) 로직을 필수로 구현할 것.  
* **클래스명 추상화**: 셜록홈즈 사이트의 HTML 구조(예약 완료 버튼 클래스 등)는 변경될 수 있으므로 Selector 정보는 scraper.py 상단에 상수로 깔끔하게 정의하여 추후 쉽게 관리할 수 있도록 함.  
* **보안**: API Key, 개인 User Key, Target URL은 코드 내부에 하드코딩하지 않고 철저히 .env 파일과 os.getenv를 거치거나 GitHub Secrets를 활용해 주입하여 사용해야 함.  
* **Pushover Priority 설정**: 알람 효과 극대화를 위해 Pushover 전송 시 priority=2, retry=60(60초 간격 재시도), expire=3600(최대 1시간 유지), sound=siren을 기본 세팅으로 작동하도록 작성할 것.