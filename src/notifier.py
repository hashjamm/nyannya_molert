import os
import requests
import logging

from config import get_pushover_retry_expire, get_pushover_token_for_type

logger = logging.getLogger(__name__)

def send_emergency_alarm(message: str, alarm_type: str = "emergency") -> tuple[bool, list[str]]:
    """
    Pushover API를 통해 priority=2 (Emergency Bypass) 알림을 스마트폰으로 전송합니다.
    성공 시 (True, receipts_list) 튜플을 반환하고, 실패 시 (False, [])을 반환합니다.
    """
    token = get_pushover_token_for_type(alarm_type)
    user_key_raw = os.getenv("PUSHOVER_USER_KEY")
    
    if not token or not user_key_raw:
        logger.error("Pushover credentials (API Token or User Key) are missing in environment variables.")
        return False, []
        
    user_keys = [k.strip() for k in user_key_raw.split(",") if k.strip()]
    if not user_keys:
        logger.error("No valid Pushover User Keys found after parsing PUSHOVER_USER_KEY.")
        return False, []
        
    sound_raw = os.getenv("PUSHOVER_SOUND", "siren")
    sounds = [s.strip() for s in sound_raw.split(",") if s.strip()]
    
    retry, expire = get_pushover_retry_expire()
    
    url = "https://api.pushover.net/1/messages.json"

    all_success = True
    receipts = []
    
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
            if receipt:
                receipts.append(receipt)
            logger.info(f"Emergency alarm ({user_sound}) successfully sent to Pushover user: {u_key[:6]}... (receipt: {receipt})")
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to send Pushover alarm ({user_sound}) to user {u_key[:6]}...: {e}")
            if e.response is not None:
                logger.error(f"Response details: {e.response.text}")
            all_success = False
            
    return all_success, receipts


def send_light_alarm(message: str, sound: str = "vibrate", title: str = "🔔 셜록홈즈 예약 변동 알림", alarm_type: str = "default") -> bool:
    """
    Pushover API를 통해 priority=0 (Normal Priority) 가벼운 진동/음성 알림을 전송합니다.
    근무 시간대 예약 변동(신규/취소) 발생 시 사용됩니다.
    """
    token = get_pushover_token_for_type(alarm_type)
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
            logger.info(f"Light alarm ({alarm_type}/{sound}) sent to user: {u_key[:6]}...")
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to send light alarm to user {u_key[:6]}...: {e}")
            all_success = False
            
    return all_success

