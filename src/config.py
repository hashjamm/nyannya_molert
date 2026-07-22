import os
import json
import logging
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)

# 한국 타임존 (KST)
KST = timezone(timedelta(hours=9))

# 요일별 근무 스케줄 (모두 11:30 출근, 퇴근시간은 요일별로 상이)
# 0: 월요일, 1: 화요일, 2: 수요일, 3: 목요일, 4: 금요일, 5: 토요일, 6: 일요일
DEFAULT_SHIFT_SCHEDULE = {
    0: {"start_time": "11:30", "end_time": "16:00", "enabled": True},  # 월요일: 11:30 출근 ~ 16:00 퇴근
    1: {"start_time": "11:30", "end_time": "18:00", "enabled": True},  # 화요일: 11:30 출근 ~ 18:00 퇴근
    2: {"start_time": "11:30", "end_time": "18:00", "enabled": True},  # 수요일: 11:30 출근 ~ 18:00 퇴근
    3: {"start_time": "11:30", "end_time": "18:00", "enabled": False}, # 목요일 휴무
    4: {"start_time": "11:30", "end_time": "18:00", "enabled": False}, # 금요일 휴무
    5: {"start_time": "11:30", "end_time": "18:00", "enabled": False}, # 토요일 휴무
    6: {"start_time": "11:30", "end_time": "18:00", "enabled": False}, # 일요일 휴무
}

def get_kst_now() -> datetime:
    """현재 한국 시간(KST) datetime 객체를 반환합니다."""
    return datetime.now(KST)

def load_shift_schedule() -> dict:
    """
    환경 변수 SHIFT_SCHEDULE_JSON이 정의되어 있다면 이를 우선 파싱하고,
    없다면 DEFAULT_SHIFT_SCHEDULE 기본값을 반환합니다.
    """
    env_json = os.getenv("SHIFT_SCHEDULE_JSON")
    if env_json:
        try:
            parsed = json.loads(env_json)
            schedule = {}
            for k, v in parsed.items():
                schedule[int(k)] = v
            logger.info("Loaded custom shift schedule from SHIFT_SCHEDULE_JSON environment variable.")
            return schedule
        except Exception as e:
            logger.warning(f"Failed to parse SHIFT_SCHEDULE_JSON: {e}. Falling back to default schedule.")

    return DEFAULT_SHIFT_SCHEDULE

def get_today_shift_info(target_dt: datetime = None) -> tuple[bool, str, str, int]:
    """
    주어진 datetime(없으면 현재 KST)의 출근 및 퇴근 정보를 반환합니다.
    반환값: (is_shift_day: bool, start_time_str: str, end_time_str: str, weekday: int)
    """
    if target_dt is None:
        target_dt = get_kst_now()

    weekday = target_dt.weekday()
    schedule = load_shift_schedule()

    shift_info = schedule.get(weekday, {"start_time": "11:30", "end_time": "18:00", "enabled": False})
    
    override_limit = os.getenv("EARLY_THRESHOLD_LIMIT")
    start_time_str = override_limit if override_limit else shift_info.get("start_time", "11:30")
    end_time_str = shift_info.get("end_time", "18:00")
    is_shift_day = shift_info.get("enabled", False)

    if override_limit:
        is_shift_day = True

    return is_shift_day, start_time_str, end_time_str, weekday
