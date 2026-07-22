import os
import requests
import logging

logger = logging.getLogger(__name__)

def send_emergency_alarm(message: str) -> tuple[bool, str | None]:
    """
    Pushover API를 통해 priority=2 (Emergency Bypass) 알림을 스마트폰으로 전송합니다.
    성공 시 (True, receipt_id) 튜플을 반환하고, 실패 시 (False, None)을 반환합니다.
    """
    token = os.getenv("PUSHOVER_API_TOKEN")
    user_key_raw = os.getenv("PUSHOVER_USER_KEY")
    
    if not token or not user_key_raw:
        logger.error("Pushover credentials (PUSHOVER_API_TOKEN, PUSHOVER_USER_KEY) are missing in environment variables.")
        return False, None
        
    user_keys = [k.strip() for k in user_key_raw.split(",") if k.strip()]
    if not user_keys:
        logger.error("No valid Pushover User Keys found after parsing PUSHOVER_USER_KEY.")
        return False, None
        
    sound_raw = os.getenv("PUSHOVER_SOUND", "siren")
    sounds = [s.strip() for s in sound_raw.split(",") if s.strip()]
    
    retry = int(os.getenv("PUSHOVER_RETRY", "60"))
    expire = int(os.getenv("PUSHOVER_EXPIRE", "300"))
    
    url = "https://api.pushover.net/1/messages.json"
    
    all_success = True
    first_receipt = None
    
    for i, u_key in enumerate(user_keys):
        if i < len(sounds):
            user_sound = sounds[i]
        elif sounds:
            user_sound = sounds[0]
        else:
            user_sound = "siren"
            
        payload = {
            "token": token,
            "user": u_key,
            "message": message,
            "title": "🚨 셜록홈즈 예약 비상 알람 🚨",
            "priority": 2,
            "retry": retry,
            "expire": expire,
            "sound": user_sound
        }
        
        try:
            response = requests.post(url, data=payload, timeout=10)
            response.raise_for_status()
            res_data = response.json()
            receipt = res_data.get("receipt")
            if not first_receipt:
                first_receipt = receipt
            logger.info(f"Emergency alarm ({user_sound}) successfully sent to Pushover user: {u_key[:6]}... (receipt: {receipt})")
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to send Pushover alarm ({user_sound}) to user {u_key[:6]}...: {e}")
            if e.response is not None:
                logger.error(f"Response details: {e.response.text}")
            all_success = False
            
    return all_success, first_receipt

def send_light_alarm(message: str, sound: str = "vibrate", title: str = "🔔 셜록홈즈 예약 변동 알림") -> bool:
    """
    Pushover API를 통해 priority=0 (Normal Priority) 가벼운 진동/음성 알림을 전송합니다.
    근무 시간대 예약 변동(신규/취소) 발생 시 사용됩니다.
    """
    token = os.getenv("PUSHOVER_API_TOKEN")
    user_key_raw = os.getenv("PUSHOVER_USER_KEY")
    
    if not token or not user_key_raw:
        logger.error("Pushover credentials missing.")
        return False
        
    user_keys = [k.strip() for k in user_key_raw.split(",") if k.strip()]
    if not user_keys:
        return False
        
    url = "https://api.pushover.net/1/messages.json"
    all_success = True
    
    for u_key in user_keys:
        payload = {
            "token": token,
            "user": u_key,
            "message": message,
            "title": title,
            "priority": 0,
            "sound": sound
        }
        
        try:
            response = requests.post(url, data=payload, timeout=10)
            response.raise_for_status()
            logger.info(f"Light alarm ({sound}) sent to user: {u_key[:6]}...")
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to send light alarm to user {u_key[:6]}...: {e}")
            all_success = False
            
    return all_success
