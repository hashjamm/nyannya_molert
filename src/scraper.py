import asyncio
import re
import logging
from datetime import datetime, timezone, timedelta
from playwright.async_api import async_playwright

logger = logging.getLogger(__name__)

# CSS Selectors
RESERVATION_CONTAINER = "#reservation"
THEME_ITEM = ".theme-list > .theme-item"
THEME_TITLE = ".theme-title"
TIME_ROW = ".row"
TIME_SLOT = ".col"
COMPLETED_SLOT = ".col.false"  # 예약 완료 / 불가 상태

MAX_RETRIES = 3
INITIAL_BACKOFF = 2.0  # 초 (Exponential Backoff 적용용)

def parse_time(time_str: str):
    """
    텍스트에서 HH:MM 형식의 시간을 추출하고 datetime.time 객체로 반환합니다.
    """
    match = re.search(r'(\d{2}):(\d{2})', time_str)
    if match:
        hour, minute = map(int, match.groups())
        return datetime.strptime(f"{hour:02d}:{minute:02d}", "%H:%M").time()
    return None

async def scrape_completed_early_reservations(target_url: str, limit_time_str: str = "12:00") -> list:
    """
    Playwright를 사용하여 셜록홈즈 예약 페이지를 크롤링하고,
    지정된 한계 시간 이전의 '예약 완료(불가)' 건을 감지하여 반환합니다.
    """
    limit_time = datetime.strptime(limit_time_str, "%H:%M").time()
    detected_reservations = []

    KST = timezone(timedelta(hours=9))
    now_kst = datetime.now(KST)
    current_time = now_kst.time()
    logger.info(f"Checking early reservations after current KST time ({current_time.strftime('%H:%M')}) before limit ({limit_time_str})")

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
                
                logger.info(f"Connecting to {target_url} (Attempt {attempt}/{MAX_RETRIES})...")
                await page.goto(target_url, wait_until="networkidle", timeout=30000)
                await page.wait_for_selector(RESERVATION_CONTAINER, timeout=15000)
                await page.wait_for_timeout(2000)
                
                themes = await page.query_selector_all(THEME_ITEM)
                logger.info(f"Found {len(themes)} themes on the page.")

                # [최적화] 페이지 내 limit_time 이전의 모든 예약 타임들을 모아 가장 이른 첫 타임 탐색
                all_early_times = []
                for theme in themes:
                    slots = await theme.query_selector_all(TIME_SLOT)
                    for slot in slots:
                        slot_text = (await slot.inner_text()).strip()
                        slot_time = parse_time(slot_text)
                        if slot_time and slot_time < limit_time:
                            all_early_times.append(slot_time)

                if all_early_times:
                    earliest_time = min(all_early_times)
                    logger.info(f"Earliest possible reservation time on page: {earliest_time.strftime('%H:%M')}")
                    
                    # 가장 이른 첫 예약 시간보다 현재 시각이 이미 지난 경우 조기 종료
                    # (단, 수동 테스트를 위해 limit_time이 18:00 이상으로 늦춰진 경우 우회)
                    if limit_time <= datetime.strptime("12:00", "%H:%M").time() and current_time >= earliest_time:
                        logger.info("Current time has passed the earliest reservation time. Aborting search.")
                        await browser.close()
                        return []
                else:
                    logger.info(f"No slots found before threshold limit time {limit_time_str}. Aborting search.")
                    await browser.close()
                    return []

                # 예약 불가(완료) 상태의 슬롯 검색
                for theme in themes:
                    title_elem = await theme.query_selector(THEME_TITLE)
                    if not title_elem:
                        continue
                    theme_title = (await title_elem.inner_text()).strip()
                    
                    completed_slots = await theme.query_selector_all(COMPLETED_SLOT)
                    for slot in completed_slots:
                        slot_text = (await slot.inner_text()).strip()
                        slot_time = parse_time(slot_text)
                        
                        if slot_time and current_time < slot_time < limit_time:
                            detected_time_str = slot_time.strftime("%H:%M")
                            logger.warning(f"Early reservation detected: theme='{theme_title}', time='{detected_time_str}'")
                            detected_reservations.append({
                                "theme": theme_title,
                                "time": detected_time_str
                            })
                            
                await browser.close()
                return detected_reservations
                
        except Exception as e:
            logger.error(f"Error occurred during scraping on attempt {attempt}: {e}")
            if attempt < MAX_RETRIES:
                backoff_time = INITIAL_BACKOFF * (2 ** (attempt - 1))
                logger.info(f"Retrying in {backoff_time} seconds...")
                await asyncio.sleep(backoff_time)
            else:
                logger.critical("Max retries reached. Scraping failed.")
                raise e
                
    return detected_reservations

async def scrape_all_completed_reservations(target_url: str) -> list:
    """
    Playwright를 사용하여 셜록홈즈 예약 페이지에서 당일 전체 테마의
    모든 '예약 완료' 건 목록([{"theme": "...", "time": "..."}, ...])을 수집하여 반환합니다.
    """
    all_completed = []

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
                
                logger.info(f"Connecting to {target_url} for full reservation scan (Attempt {attempt}/{MAX_RETRIES})...")
                await page.goto(target_url, wait_until="networkidle", timeout=30000)
                await page.wait_for_selector(RESERVATION_CONTAINER, timeout=15000)
                await page.wait_for_timeout(2000)
                
                themes = await page.query_selector_all(THEME_ITEM)
                
                for theme in themes:
                    title_elem = await theme.query_selector(THEME_TITLE)
                    if not title_elem:
                        continue
                    theme_title = (await title_elem.inner_text()).strip()
                    
                    completed_slots = await theme.query_selector_all(COMPLETED_SLOT)
                    for slot in completed_slots:
                        slot_text = (await slot.inner_text()).strip()
                        slot_time = parse_time(slot_text)
                        if slot_time:
                            all_completed.append({
                                "theme": theme_title,
                                "time": slot_time.strftime("%H:%M")
                            })
                            
                await browser.close()
                logger.info(f"Scraped total {len(all_completed)} completed reservations across all themes.")
                return all_completed
                
        except Exception as e:
            logger.error(f"Error during full reservation scraping (attempt {attempt}): {e}")
            if attempt < MAX_RETRIES:
                backoff_time = INITIAL_BACKOFF * (2 ** (attempt - 1))
                await asyncio.sleep(backoff_time)
            else:
                logger.critical("Max retries reached for full reservation scraping.")
                raise e

    return all_completed
