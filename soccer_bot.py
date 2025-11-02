import logging
import re
import time
import os  # ← KEEP THIS
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup

TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')  # ← KEEP THIS

logging.basicConfig(level=logging.INFO)

# === LOGIC #1: 4+ GOALS ===
GOALS_PATTERN = {
    '0.5': r'^1\.1\d-1\.1\d$',
    '0.75': r'^1\.2\d-1\.2\d$',
    '1.0': r'^(1\.3\d-1\.3\d|1\.4\d-1\.3\d)$',
    '1.25': r'^1\.7\d-1\.6\d$',
    '1.5': r'^2\.0\d-1\.8\d$',
    '1.75': r'^2\.4\d-2\.2\d$'
}

# === LOGIC #2: GG/BTTS ===
GG_RULES = {
    '1.25': [r'^1\.5\d-1\.6\d$', r'^1\.6\d-1\.5\d$'],
    '1.5': [r'^1\.8\d-1\.9\d$', r'^1\.7\d-1\.8\d$']
}

# === LOGIC #3: DRAW ===
DRAW_DIFFS = {0, 4, 5, 8, 10, 11, 15}

STATS = {'goals': 0, 'gg': 0, 'draw': 0, 'total': 0, 'leagues': 0}

# === SELENIUM DRIVER ===
def get_driver():
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    driver.set_page_load_timeout(20)
    return driver

# === COMMANDS ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("4+ Goals", callback_data='g')],
        [InlineKeyboardButton("GG / BTTS", callback_data='gg')],
        [InlineKeyboardButton("DRAW", callback_data='d')],
        [InlineKeyboardButton("ALL 3", callback_data='all')],
        [InlineKeyboardButton("Stats", callback_data='stats')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        'YOUR 3-IN-1 EDGE BOT (1xBet Only)\n\n'
        'Single game: /predict <Soccer24 URL>\n'
        'Today: /leagues Spain LaLiga\n'
        'Any date: /date 2025-11-05 Spain LaLiga\n'
        'Use: today, tomorrow, or YYYY-MM-DD',
        reply_markup=reply_markup
    )

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    msgs = {
        'g': 'Checks 4+ Goals digit ladder',
        'gg': 'Checks GG 1.25 & 1.5 blocks',
        'd': 'Checks Draw difference',
        'all': 'Runs all 3',
        'stats': f'Scans: {STATS["total"]}\n4+: {STATS["goals"]}\nGG: {STATS["gg"]}\nDraw: {STATS["draw"]}\nLeague scans: {STATS["leagues"]}'
    }
    await q.edit_message_text(msgs[q.data] + '\n\nSend /predict, /leagues, or /date')

async def predict(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global STATS
    STATS['total'] += 1
    if not context.args:
        await update.message.reply_text('Send Soccer24 match URL after /predict')
        return
    url = context.args[0]
    data = scrape_soccer24_selenium(url)
    if not data:
        await update.message.reply_text('Failed to load. Try again.')
        return
    results = []
    g = check_goals(data['second'])
    gg = check_gg(data['second'])
    d = check_draw(data)
    if g: results.append(g); STATS['goals'] += 1
    if gg: results.append(gg); STATS['gg'] += 1
    if d: results.append(d); STATS['draw'] += 1
    if not results:
        results.append("No signals.")
    await update.message.reply_text('\n\n'.join(results))

async def leagues(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global STATS
    STATS['leagues'] += 1
    if not context.args:
        await update.message.reply_text('Send leagues: /leagues Spain LaLiga, England Premier League')
        return
    
    target_leagues = [arg.strip() for arg in ' '.join(context.args).split(',')]
    matches = scrape_matches_from_homepage_selenium()
    if not matches:
        await update.message.reply_text('No matches found today.')
        return
    
    filtered_matches = []
    for match in matches:
        league_text = f"{match['country']} {match['league']}".lower()
        if any(target.lower() in league_text for target in target_leagues):
            filtered_matches.append(match)
    
    if not filtered_matches:
        await update.message.reply_text(f'No matches in: {", ".join(target_leagues)}')
        return
    
    goals_results = []
    gg_results = []
    draw_results = []
    
    driver = get_driver()
    try:
        for match in filtered_matches:
            data = scrape_soccer24_selenium(match['url'], driver=driver)
            if not data:
                continue
            
            game_title = f"{match['home']} vs {match['away']} ({match['country']} - {match['league']})"
            
            g = check_goals(data['second'])
            if g:
                goals_results.append(f"{game_title}\n{g}")
                STATS['goals'] += 1
            
            gg = check_gg(data['second'])
            if gg:
                gg_results.append(f"{game_title}\n{gg}")
                STATS['gg'] += 1
            
            d = check_draw(data)
            if d:
                draw_results.append(f"{game_title}\n{d}")
                STATS['draw'] += 1
    finally:
        driver.quit()
    
    results = []
    if goals_results:
        results.append("4+ GOALS SIGNALS:\n" + '\n\n'.join(goals_results))
    else:
        results.append("No 4+ Goals signals.")
    
    if gg_results:
        results.append("GG/BTTS SIGNALS:\n" + '\n\n'.join(gg_results))
    else:
        results.append("No GG/BTTS signals.")
    
    if draw_results:
        results.append("DRAW SIGNALS:\n" + '\n\n'.join(draw_results))
    else:
        results.append("No Draw signals.")
    
    await update.message.reply_text('\n\n---\n\n'.join(results))

# === NEW: /date COMMAND ===
async def date_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global STATS
    STATS['leagues'] += 1
    if not context.args:
        await update.message.reply_text('Usage: /date <date> <league1, league2>\n'
                                        'Date: today, tomorrow, or YYYY-MM-DD\n'
                                        'Example: /date 2025-11-05 Spain LaLiga')
        return

    # Parse date
    date_input = context.args[0].lower()
    try:
        if date_input == 'today':
            target_date = datetime.now().date()
        elif date_input == 'tomorrow':
            target_date = (datetime.now() + timedelta(days=1)).date()
        else:
            target_date = datetime.strptime(date_input, '%Y-%m-%d').date()
    except:
        await update.message.reply_text('Invalid date. Use: today, tomorrow, or YYYY-MM-DD')
        return

    # Get leagues
    if len(context.args) < 2:
        await update.message.reply_text('Add leagues after date: /date 2025-11-05 Spain LaLiga')
        return
    target_leagues = [arg.strip() for arg in ' '.join(context.args[1:]).split(',')]

    # Scrape matches for the target date
    matches = scrape_matches_by_date_selenium(target_date)
    if not matches:
        await update.message.reply_text(f'No matches found on {target_date}')
        return

    filtered_matches = []
    for match in matches:
        league_text = f"{match['country']} {match['league']}".lower()
        if any(target.lower() in league_text for target in target_leagues):
            filtered_matches.append(match)

    if not filtered_matches:
        await update.message.reply_text(f'No matches in leagues on {target_date}')
        return

    # Run logic
    goals_results = []
    gg_results = []
    draw_results = []

    driver = get_driver()
    try:
        for match in filtered_matches:
            data = scrape_soccer24_selenium(match['url'], driver=driver)
            if not data: continue

            game_title = f"{match['home']} vs {match['away']} ({match['country']} - {match['league']})"

            g = check_goals(data['second'])
            if g:
                goals_results.append(f"{game_title}\n{g}")
                STATS['goals'] += 1

            gg = check_gg(data['second'])
            if gg:
                gg_results.append(f"{game_title}\n{gg}")
                STATS['gg'] += 1

            d = check_draw(data)
            if d:
                draw_results.append(f"{game_title}\n{d}")
                STATS['draw'] += 1
    finally:
        driver.quit()

    # Send results
    results = []
    if goals_results:
        results.append("4+ GOALS SIGNALS:\n" + '\n\n'.join(goals_results))
    else:
        results.append("No 4+ Goals signals.")

    if gg_results:
        results.append("GG/BTTS SIGNALS:\n" + '\n\n'.join(gg_results))
    else:
        results.append("No GG/BTTS signals.")

    if draw_results:
        results.append("DRAW SIGNALS:\n" + '\n\n'.join(draw_results))
    else:
        results.append("No Draw signals.")

    await update.message.reply_text(f"Results for {target_date}\n\n" + '\n\n---\n\n'.join(results))

# === SCRAPERS ===
def scrape_matches_from_homepage_selenium() -> List[Dict]:
    driver = get_driver()
    try:
        driver.get('https://www.soccer24.com/')
        WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.CSS_SELECTOR, ".event__match")))
        time.sleep(3)
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        matches = []
        event_links = soup.find_all('a', href=re.compile(r'/[^/]+/[^/]+/match/\d+'))
        for link in event_links:
            href = link.get('href')
            if not href.startswith('/'): continue
            full_url = 'https://www.soccer24.com' + href
            parent_row = link.find_parent('div', class_=re.compile(r'event__match'))
            if not parent_row: continue
            home_elem = parent_row.find('div', class_=re.compile(r'event__participant--home'))
            away_elem = parent_row.find('div', class_=re.compile(r'event__participant--away'))
            home = home_elem.get_text(strip=True) if home_elem else 'Unknown'
            away = away_elem.get_text(strip=True) if away_elem else 'Unknown'
            league_elem = parent_row.find_previous_sibling('div', class_=re.compile(r'league|country'))
            league_text = league_elem.get_text(strip=True) if league_elem else ''
            parts = re.split(r' - | / ', league_text)
            country = parts[0].strip() if parts else 'Unknown'
            league = parts[1].strip() if len(parts) > 1 else 'Unknown'
            matches.append({'home': home, 'away': away, 'country': country, 'league': league, 'url': full_url})
        unique = {m['url']: m for m in matches}.values()
        return list(unique)[:30]
    except Exception as e:
        logging.error(f"Error: {e}")
        return []
    finally:
        driver.quit()

def scrape_matches_by_date_selenium(target_date) -> List[Dict]:
    driver = get_driver()
    try:
        driver.get('https://www.soccer24.com/')
        WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.CSS_SELECTOR, ".calendar__nav")))
        
        date_picker = driver.find_element(By.CSS_SELECTOR, ".calendar__nav")
        date_picker.click()
        time.sleep(1)

        day = target_date.day
        month_name = target_date.strftime('%b')
        date_str = f"{day} {month_name}"

        date_cell = None
        try:
            date_cell = driver.find_element(By.XPATH, f"//td[contains(@class,'calendar__day') and .//span[text()='{day}'] and .//span[text()='{month_name}']]")
        except:
            pass
        if not date_cell:
            date_cell = driver.find_element(By.XPATH, f"//td[contains(@class,'calendar__day') and .//span[text()='{day}']]")
        
        if date_cell:
            date_cell.click()
            time.sleep(3)
        else:
            return []

        soup = BeautifulSoup(driver.page_source, 'html.parser')
        matches = []
        event_links = soup.find_all('a', href=re.compile(r'/match/\d+'))
        for link in event_links:
            href = link.get('href')
            if not href: continue
            full_url = 'https://www.soccer24.com' + href if href.startswith('/') else href
            parent_row = link.find_parent('div', class_=re.compile(r'event__match'))
            if not parent_row: continue
            home_elem = parent_row.find('div', class_=re.compile(r'event__participant--home'))
            away_elem = parent_row.find('div', class_=re.compile(r'event__participant--away'))
            home = home_elem.get_text(strip=True) if home_elem else 'Unknown'
            away = away_elem.get_text(strip=True) if away_elem else 'Unknown'
            league_elem = parent_row.find_previous_sibling('div', class_=re.compile(r'league'))
            league_text = league_elem.get_text(strip=True) if league_elem else ''
            parts = re.split(r' - | / ', league_text)
            country = parts[0].strip() if parts else 'Unknown'
            league = parts[1].strip() if len(parts) > 1 else 'Unknown'
            matches.append({'home': home, 'away': away, 'country': country, 'league': league, 'url': full_url})
        unique = {m['url']: m for m in matches}.values()
        return list(unique)[:30]
    except Exception as e:
        logging.error(f"Date scrape error: {e}")
        return []
    finally:
        driver.quit()

def scrape_soccer24_selenium(url: str, driver: Optional[webdriver.Chrome] = None) -> Dict:
    own_driver = False
    if driver is None:
        driver = get_driver()
        own_driver = True
    try:
        driver.get(url)
        WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.CSS_SELECTOR, ".odds__table")))
        time.sleep(2)
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        data = {'full': {}, 'first': {}, 'second': {}}
        sections = soup.find_all('div', string=re.compile(r'Full Time|1st Half|2nd Half', re.I))
        for sec in sections:
            sec_text = sec.get_text().lower()
            if '1st half' in sec_text or 'first half' in sec_text:
                sec_name = 'first'
            elif '2nd half' in sec_text or 'second half' in sec_text:
                sec_name = 'second'
            else:
                sec_name = 'full'
            table = sec.find_next('table', class_=re.compile(r'odds|table'))
            if not table: continue
            bet_row = table.find('span', string='1xBet')
            if not bet_row: continue
            row = bet_row.find_parent('tr')
            if not row: continue
            cells = row.find_all('td')
            if len(cells) < 3: continue
            line_match = re.search(r'(\d+\.\d+)', cells[0].get_text())
            if not line_match: continue
            line = line_match.group(1)
            over_cell = cells[1]
            title = over_cell.get('title', '') or over_cell.get_text()
            rng_match = re.search(r'(\d+\.\d+)-(\d+\.\d+)', title)
            if rng_match:
                data[sec_name][line] = f"{rng_match.group(1)}-{rng_match.group(2)}"
        return data
    except Exception as e:
        logging.error(f"Error scraping {url}: {e}")
        return {}
    finally:
        if own_driver:
            driver.quit()

# === LOGIC CHECKS ===
def check_goals(odds: Dict) -> Optional[str]:
    lines = ['0.5','0.75','1.0','1.25','1.5','1.75']
    hits = sum(1 for l in lines if l in odds and re.match(GOALS_PATTERN[l], odds[l]))
    if hits == 6:
        return "4+ GOALS LOCKED (6/6)\nBET: Over 4.5"
    return None

def check_gg(odds: Dict) -> Optional[str]:
    hits = 0
    for l in ['1.25', '1.5']:
        if l in odds:
            for p in GG_RULES[l]:
                if re.match(p, odds[l]):
                    hits += 1
                    break
    if hits == 2:
        return "GG CONFIRMED (1.25 & 1.5)\nBET: Both Teams to Score"
    return None

def check_draw(data: Dict) -> Optional[str]:
    ft = data['full'].get('2.75')
    fh = data['first'].get('1.25')
    if not ft or not fh: return None
    diff = round(float(fh.split('-')[0]) - float(ft.split('-')[0]))
    if diff in DRAW_DIFFS:
        return f"DRAW LOCKED (Diff: {diff})\nBET: Draw"
    return None

# === MAIN ===
def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button))
    app.add_handler(CommandHandler("predict", predict))
    app.add_handler(CommandHandler("leagues", leagues))
    app.add_handler(CommandHandler("date", date_command))  # ← NEW
    print("YOUR 3-IN-1 BOT IS LIVE (1xBet Only + /date Command!)")
    app.run_polling()

if __name__ == '__main__':
    main()

