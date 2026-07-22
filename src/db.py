import os
import json
import logging
import requests

from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# 데이터 자동 만료 시간 (24시간 = 86400초)
TTL_SECONDS = 86400

def _get_credentials():
    load_dotenv()
    url = os.getenv("UPSTASH_REDIS_REST_URL")
    token = os.getenv("UPSTASH_REDIS_REST_TOKEN")
    return url, token

def _is_db_available() -> bool:
    """Upstash Redis 환경 변수가 설정되어 있는지 확인합니다."""
    url, token = _get_credentials()
    return bool(url and token)

def _redis_command(command_args: list):
    """Upstash Redis REST API에 명령어를 전송합니다."""
    url, token = _get_credentials()
    if not url or not token:
        logger.debug("Upstash Redis credentials missing. DB operations disabled.")
        return None

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.post(url, json=command_args, headers=headers, timeout=5)
        response.raise_for_status()
        data = response.json()
        return data.get("result")
    except Exception as e:
        logger.error(f"Upstash Redis API command failed ({command_args[:2]}...): {e}")
        return None

def get_today_reservations(date_str: str) -> list:
    """
    특정 날짜(YYYY-MM-DD)의 이전 저장된 예약 목록을 조회합니다.
    DB 미설정 또는 데이터 부재 시 빈 리스트 []를 반환합니다.
    """
    key = f"reservations:{date_str}"
    result = _redis_command(["GET", key])
    if result:
        try:
            return json.loads(result)
        except json.JSONDecodeError:
            logger.error(f"Failed to decode reservations JSON for key '{key}'.")
    return []

def save_today_reservations(date_str: str, reservations: list) -> bool:
    """
    특정 날짜(YYYY-MM-DD)의 예약 목록을 24시간 TTL과 함께 DB에 저장합니다.
    """
    key = f"reservations:{date_str}"
    value_str = json.dumps(reservations, ensure_ascii=False)
    result = _redis_command(["SET", key, value_str, "EX", str(TTL_SECONDS)])
    if result == "OK":
        logger.info(f"Saved {len(reservations)} reservations to DB (Key: {key}).")
        return True
    return False

def get_morning_alarm_state(date_str: str) -> dict | None:
    """
    특정 날짜(YYYY-MM-DD)의 아침 알람 상태(receipt_id 등)를 조회합니다.
    """
    key = f"morning_alarm:{date_str}"
    result = _redis_command(["GET", key])
    if result:
        try:
            return json.loads(result)
        except json.JSONDecodeError:
            logger.error(f"Failed to decode morning_alarm JSON for key '{key}'.")
    return None

def save_morning_alarm_state(date_str: str, alarm_data: dict) -> bool:
    """
    특정 날짜(YYYY-MM-DD)의 아침 알람 상태 정보를 DB에 24시간 TTL로 저장합니다.
    alarm_data 예시: {"receipt": "r5x...", "sent_at": "09:50", "acknowledged": False}
    """
    key = f"morning_alarm:{date_str}"
    value_str = json.dumps(alarm_data, ensure_ascii=False)
    result = _redis_command(["SET", key, value_str, "EX", str(TTL_SECONDS)])
    if result == "OK":
        logger.info(f"Saved morning alarm state to DB (Key: {key}).")
        return True
    return False

def check_pushover_ack(receipt_id: str, api_token: str) -> bool:
    """
    Pushover Receipt API를 호출하여 해당 알람을 사용자가 확인(Acknowledge)했는지 검증합니다.
    """
    if not receipt_id or not api_token:
        return False

    url = f"https://api.pushover.net/1/receipts/{receipt_id}.json"
    params = {"token": api_token}

    try:
        response = requests.get(url, params=params, timeout=5)
        response.raise_for_status()
        data = response.json()
        
        status = data.get("status", 0)
        acknowledged = data.get("acknowledged", 0)
        
        if status == 1 and acknowledged == 1:
            ack_at = data.get("acknowledged_at")
            logger.info(f"Pushover receipt '{receipt_id}' was acknowledged by user (timestamp: {ack_at}).")
            return True
        else:
            logger.info(f"Pushover receipt '{receipt_id}' has not been acknowledged yet.")
            return False
    except Exception as e:
        logger.error(f"Failed to check Pushover receipt status: {e}")
        return False
