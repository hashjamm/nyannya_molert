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
    user_key_raw = os.getenv("PUSHOVER_USER_KEY")
    
    if not token or not user_key_raw:
        logger.error("Pushover credentials (PUSHOVER_API_TOKEN, PUSHOVER_USER_KEY) are missing in environment variables.")
        return False
        
    # 쉼표로 구분된 다중 유저 키 분리
    user_keys = [k.strip() for k in user_key_raw.split(",") if k.strip()]
    if not user_keys:
        logger.error("No valid Pushover User Keys found after parsing PUSHOVER_USER_KEY.")
        return False
        
    # 개인 선호도에 따른 알람 세부 설정을 .env에서 읽고 오버라이드 (기본값 제공)
    sound = os.getenv("PUSHOVER_SOUND", "siren")
    retry = int(os.getenv("PUSHOVER_RETRY", "60"))
    # [중요] 사용자가 알림을 확인하지 않아 알람이 지속되는 시간이 감시 주기(10분)보다 길 경우, 
    # 다음 주기(10분 후) 감시 실행 시 새로운 긴급 알람이 발생하여 알람이 중복으로 겹쳐 울릴 수 있습니다.
    # 이를 원천 방지하기 위해 PUSHOVER_EXPIRE 설정값은 반드시 감시 주기(10분 = 600초)보다 
    # 짧은 값(예: 300초 = 5분)으로 유지해야 합니다.
    expire = int(os.getenv("PUSHOVER_EXPIRE", "3600"))
    
    url = "https://api.pushover.net/1/messages.json"
    
    all_success = True
    for u_key in user_keys:
        payload = {
            "token": token,
            "user": u_key,
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
            logger.info(f"Emergency alarm successfully sent to Pushover user: {u_key[:6]}...")
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to send Pushover alarm to user {u_key[:6]}...: {e}")
            if e.response is not None:
                logger.error(f"Response details: {e.response.text}")
            all_success = False
            
    return all_success
