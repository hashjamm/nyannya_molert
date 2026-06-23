import os
import requests
import logging

logger = logging.getLogger(__name__)

def send_emergency_alarm(message: str) -> bool:
    """
    Pushover API를 통해 priority=2 (Emergency Bypass) 알림을 스마트폰으로 전송합니다.
    사용자가 직접 확인할 때까지 60초 간격으로 최대 1시간 동안 siren 소리로 알람이 재울립니다.
    """
    token = os.getenv("PUSHOVER_API_TOKEN")
    user_key = os.getenv("PUSHOVER_USER_KEY")
    
    if not token or not user_key:
        logger.error("Pushover credentials (PUSHOVER_API_TOKEN, PUSHOVER_USER_KEY) are missing in environment variables.")
        return False
        
    # 개인 선호도에 따른 알람 세부 설정을 .env에서 읽고 오버라이드 (기본값 제공)
    sound = os.getenv("PUSHOVER_SOUND", "siren")
    retry = int(os.getenv("PUSHOVER_RETRY", "60"))
    expire = int(os.getenv("PUSHOVER_EXPIRE", "3600"))
    
    url = "https://api.pushover.net/1/messages.json"
    payload = {
        "token": token,
        "user": user_key,
        "message": message,
        "title": "🚨 셜록홈즈 예약 비상 알람 🚨",
        "priority": 2,
        "retry": retry,
        "expire": expire,
        "sound": sound
    }
    
    try:
        response = requests.post(url, data=payload, timeout=10)
        response.raise_for_status()
        logger.info("Emergency alarm successfully sent to Pushover.")
        return True
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to send Pushover alarm: {e}")
        if e.response is not None:
            logger.error(f"Response details: {e.response.text}")
        return False
