import os
import asyncio
import logging
from dotenv import load_dotenv

from config import (
    get_kst_now,
    get_today_shift_info,
    get_monitor_start_time,
    get_early_threshold_limit
)
from scraper import scrape_completed_early_reservations, scrape_all_completed_reservations
from notifier import send_emergency_alarm, send_light_alarm
from db import (
    get_today_reservations,
    save_today_reservations,
    get_morning_alarm_state,
    save_morning_alarm_state,
    check_pushover_ack
)

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s (%(name)s): %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("main")

async def main():
    load_dotenv()
    
    target_url = os.getenv("SHERLOCK_URL") or "https://sherlock-holmes.co.kr/reservation/index.php?sido=12&bno=86#reservation"
    pushover_token = os.getenv("PUSHOVER_API_TOKEN")
    
    now_kst = get_kst_now()
    today_str = now_kst.strftime("%Y-%m-%d")
    current_time_str = now_kst.strftime("%H:%M")
    
    is_shift_day, start_time_str, end_time_str, weekday = get_today_shift_info(now_kst)
    
    logger.info(f"Starting Sherlock-Alarm execution. Date: {today_str} ({current_time_str} KST), Weekday: {weekday}")
    logger.info(f"Shift Schedule -> Work Day: {is_shift_day}, Start: {start_time_str}, End: {end_time_str}")
    
    if not is_shift_day:
        logger.info("Today is not a scheduled shift day. Skipping automatic monitoring.")
        return

    start_time_obj = now_kst.replace(
        hour=int(start_time_str.split(":")[0]),
        minute=int(start_time_str.split(":")[1]),
        second=0, microsecond=0
    ).time()

    end_time_obj = now_kst.replace(
        hour=int(end_time_str.split(":")[0]),
        minute=int(end_time_str.split(":")[1]),
        second=0, microsecond=0
    ).time()
    
    morning_start_time_str = get_monitor_start_time()
    morning_start_time_obj = now_kst.replace(
        hour=int(morning_start_time_str.split(":")[0]),
        minute=int(morning_start_time_str.split(":")[1]),
        second=0, microsecond=0
    ).time()

    current_time_obj = now_kst.time()

    # =========================================================================
    # CASE 0: 오전 감시 시작 시각 이전 (현재 시각 < 09:40) -> 실행 중단
    # =========================================================================
    if current_time_obj < morning_start_time_obj:
        logger.info(f"Current time ({current_time_str}) is before morning monitoring start time ({morning_start_time_str}). Skipping execution.")
        return

    # =========================================================================
    # CASE 1: 퇴근 시각 이후 (현재 시각 > end_time) -> 실행 중단
    # =========================================================================
    if current_time_obj > end_time_obj:
        logger.info(f"Current time ({current_time_str}) is past shift end time ({end_time_str}). Off-work hours -> Skipping execution.")
        return

    # =========================================================================
    # MODE 1: 오전 긴급 모드 (현재 시각 < 출근 시각 11:20)
    # =========================================================================
    if current_time_obj < start_time_obj:
        logger.info(f"Running [MORNING EMERGENCY MODE] (Current: {current_time_str} < Shift Start: {start_time_str})")
        
        # 1. DB에서 오늘 아침 알람 발송 및 확인(Ack) 여부 검증 (Smart Silence)
        alarm_state = get_morning_alarm_state(today_str)
        if alarm_state and alarm_state.get("receipt"):
            receipt_id = alarm_state["receipt"]
            logger.info(f"Found existing morning alarm receipt: {receipt_id}")
            
            is_acked = check_pushover_ack(receipt_id, pushover_token)
            if is_acked:
                logger.info("✨ User has ACKNOWLEDGED today's morning alarm. Smart Silence active -> Skipping 2nd alarm.")
                return
            else:
                logger.info("Morning alarm was sent earlier, but user has not acknowledged it yet.")

        # 2. 크롤링 진행 및 조기 예약 완료 건 감지
        try:
            early_limit_str = get_early_threshold_limit()
            early_reservations = await scrape_completed_early_reservations(target_url, limit_time_str=early_limit_str)
            
            if early_reservations:
                logger.warning(f"Detected {len(early_reservations)} early reservations before {early_limit_str}.")

                
                msg_lines = [
                    "🚨 조기 출근 예약 알람 🚨",
                    f"냔냐님! 아산점에 조기 예약 완료 건이 감지되었습니다.",
                    "평소보다 일찍 출근 준비를 시작해야 할 수 있습니다.",
                    "",
                    "[예약 완료 내역]"
                ]
                for res in early_reservations:
                    msg_lines.append(f"- {res['theme']} ({res['time']})")
                    
                alarm_message = "\n".join(msg_lines)
                
                success, receipt_id = send_emergency_alarm(alarm_message, alarm_type="emergency")
                if success:
                    logger.info("Emergency alarm sent successfully.")
                    if receipt_id:
                        save_morning_alarm_state(today_str, {
                            "receipt": receipt_id,
                            "sent_at": current_time_str,
                            "count": (alarm_state.get("count", 0) + 1) if alarm_state else 1
                        })
                else:
                    logger.error("Failed to send emergency alarm.")
            else:
                logger.info("No early reservations detected before 12:00. Sleep well!")
                
        except Exception as e:
            logger.critical(f"Error during Morning Emergency Mode execution: {e}")

    # =========================================================================
    # MODE 2: 근무 중 실시간 예약 변동 모드 (출근 시각 11:20 <= 현재 시각 <= 퇴근 시각)
    # =========================================================================
    else:
        logger.info(f"Running [DAYTIME WORK MODE] (Shift Start: {start_time_str} <= Current: {current_time_str} <= End: {end_time_str})")
        
        try:
            current_reservations = await scrape_all_completed_reservations(target_url)
            prev_reservations = get_today_reservations(today_str)
            
            if prev_reservations:
                prev_set = {(r["theme"], r["time"]) for r in prev_reservations}
                curr_set = {(r["theme"], r["time"]) for r in current_reservations}

                # 현재 시각 이후의 미래 예약 항목만 필터링 (시간 경과에 따른 과거 슬롯의 자동 마감/소멸을 신규/취소로 오탐 방지)
                new_items = {item for item in (curr_set - prev_set) if item[1] > current_time_str}
                canceled_items = {item for item in (prev_set - curr_set) if item[1] > current_time_str}
                
                # 퇴근 정각 시각 (월 16:00 / 화·수 18:00) 전용 마감 알람
                is_off_work_time = (current_time_obj == end_time_obj)
                
                if is_off_work_time:
                    logger.info("Shift end time reached. Sending off-work briefing alert.")
                    end_msg_lines = [
                        "🏁 [오늘의 퇴근 마감]",
                        "냔냐님! 오늘 하루도 정말 수고 많으셨습니다. 즐거운 퇴근길 되세요! ✨"
                    ]
                    if new_items or canceled_items:
                        end_msg_lines.append("")
                        end_msg_lines.append("[퇴근 시점 예약 변동 내역]")
                        if new_items:
                            for theme, res_time in sorted(new_items):
                                end_msg_lines.append(f"🆕 {theme} ({res_time})")
                        if canceled_items:
                            for theme, res_time in sorted(canceled_items):
                                end_msg_lines.append(f"❌ {theme} ({res_time})")
                    
                    send_light_alarm("\n".join(end_msg_lines), sound="vibrate", title="🏁 [퇴근 마감] 수고하셨습니다!", alarm_type="end")
                else:
                    if new_items:
                        logger.warning(f"Detected {len(new_items)} NEW reservations!")
                        msg_lines = ["🔔 [신규 예약 접수 알림]"]
                        for theme, res_time in sorted(new_items):
                            msg_lines.append(f"🆕 {theme} ({res_time})")
                        send_light_alarm("\n".join(msg_lines), sound="vibrate", title="🆕 신규 예약 접수!", alarm_type="diff_plus")
                        
                    if canceled_items:
                        logger.warning(f"Detected {len(canceled_items)} CANCELED reservations!")
                        msg_lines = ["🔔 [예약 취소 알림]"]
                        for theme, res_time in sorted(canceled_items):
                            msg_lines.append(f"❌ {theme} ({res_time})")
                        send_light_alarm("\n".join(msg_lines), sound="vibrate", title="❌ 예약 취소 발생", alarm_type="diff_minus")
                        
                    if not new_items and not canceled_items:
                        logger.info("No reservation changes detected during work mode.")
            else:
                logger.info("First reservation scan of the day in Work Mode. Sending Daily Shift Briefing alert.")
                upcoming_reservations = [r for r in current_reservations if r["time"] > current_time_str]
                if upcoming_reservations:
                    msg_lines = [
                        "📋 [오늘의 출근 브리핑]",
                        f"냔냐님! {current_time_str} 이후 오늘의 현재 예약 상황입니다 (총 {len(upcoming_reservations)}건):",
                        ""
                    ]
                    for res in sorted(upcoming_reservations, key=lambda x: x["time"]):
                        msg_lines.append(f"- {res['time']} | {res['theme']}")
                else:
                    msg_lines = [
                        "📋 [오늘의 출근 브리핑]",
                        f"냔냐님! {current_time_str} 이후 오늘의 현재 예약 건이 없습니다. 편안한 근무 되세요! ✨"
                    ]
                
                send_light_alarm("\n".join(msg_lines), sound="vibrate", title="📋 [출근 브리핑] 현재 예약 상황", alarm_type="briefing")

            save_today_reservations(today_str, current_reservations)



        except Exception as e:
            logger.critical(f"Error during Daytime Work Mode execution: {e}")

if __name__ == "__main__":
    asyncio.run(main())
