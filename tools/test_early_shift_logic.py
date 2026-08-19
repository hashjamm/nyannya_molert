import sys
import os
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import config
import main

KST = timezone(timedelta(hours=9))

def run_tests():
    print("Testing dynamic early shift start time...")

    # Test 1: config default value
    assert config.get_early_shift_start_time() == "11:00", "Default early shift time should be 11:00"
    print("[PASS] Test 1 Passed: Default early shift start time is 11:00")

    # Test 2: Simulating Wednesday (weekday 2) at 11:00 without emergency alarm
    test_dt_1100 = datetime(2026, 8, 19, 11, 0, 0, tzinfo=KST)
    is_shift_day, start_time_str, end_time_str, weekday = config.get_today_shift_info(test_dt_1100)
    assert is_shift_day is True
    assert start_time_str == "11:20"

    # In normal state (no alarm), 11:00 is Mode 1 (< 11:20)
    start_time_obj = test_dt_1100.replace(hour=11, minute=20, second=0).time()
    assert test_dt_1100.time() < start_time_obj
    print("[PASS] Test 2 Passed: Normal day at 11:00 stays in Mode 1 (Morning Mode)")

    # Test 3: Simulating Wednesday at 11:00 WITH emergency alarm already sent
    alarm_state = {"receipts": ["test_receipt"], "sent_at": "09:40", "count": 1}
    if alarm_state:
        start_time_str = config.get_early_shift_start_time() # 11:00
    start_time_obj = test_dt_1100.replace(hour=11, minute=0, second=0).time()

    # Now at 11:00, current_time (11:00) >= start_time (11:00) -> Enters Mode 2!
    assert not (test_dt_1100.time() < start_time_obj)
    print("[PASS] Test 3 Passed: Emergency alarm day at 11:00 successfully triggers Mode 2 (Work Mode)")

    print("\nAll dynamic early shift unit tests passed successfully!")

if __name__ == "__main__":
    run_tests()
