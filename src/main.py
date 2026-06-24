import os
import asyncio
import logging
from dotenv import load_dotenv

from scraper import scrape_completed_early_reservations
from notifier import send_emergency_alarm

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s (%(name)s): %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("main")

async def main():
    # 로컬 개발 시 .env 로드 (GitHub Actions 실행 시 런타임 환경변수 자동 적용)
    load_dotenv()
    
    target_url = os.getenv("SHERLOCK_URL") or "https://sherlock-holmes.co.kr/reservation/index.php?sido=12&bno=86#reservation"
    limit_time = os.getenv("EARLY_THRESHOLD_LIMIT") or "12:00"
    
    logger.info(f"Starting Sherlock-Alarm check. URL: {target_url}, Threshold: {limit_time}")
    
    try:
        # 1. 크롤링 진행 및 12:00 이전 예약 완료 건 탐색
        early_reservations = await scrape_completed_early_reservations(target_url, limit_time)
        
        # 2. 결과 분석 및 알림 발송
        if early_reservations:
            logger.warning(f"Detected {len(early_reservations)} early reservations.")
            
            # 메시지 포맷 작성
            msg_lines = [
                "🚨 조기 출근 예약 알람 🚨",
                f"냔냐님! 아산점에 {limit_time} 이전 예약 완료 건이 감지되었습니다.",
                "평소보다 일찍 출근 준비를 시작해야 할 수 있습니다.",
                "",
                "[예약 완료 내역]"
            ]
            for res in early_reservations:
                msg_lines.append(f"- {res['theme']} ({res['time']})")
                
            alarm_message = "\n".join(msg_lines)
            
            # Pushover 비상 사이렌 알람 전송
            success = send_emergency_alarm(alarm_message)
            if success:
                logger.info("Emergency alarm sent successfully.")
            else:
                logger.error("Failed to send emergency alarm.")
        else:
            logger.info(f"No early reservations (before {limit_time}) detected. Sleep well!")
            
    except Exception as e:
        logger.critical(f"Execution failed due to unexpected error: {e}")
        
if __name__ == "__main__":
    # Windows 환경에서 Default ProactorEventLoop를 사용하도록 둠 (Playwright의 subprocess 제어 필수)
    asyncio.run(main())
