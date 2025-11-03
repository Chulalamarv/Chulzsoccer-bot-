import os, time, logging, re
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, ContextTypes
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup

TOKEN = os.getenv("TELEGRAM_TOKEN")
logging.basicConfig(level=logging.INFO)

# —————— DRIVER ——————
def get_driver():
    opts = Options()
    opts.add_argument("--headless")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.binary_location = "/usr/bin/google-chrome"
    service = Service(ChromeDriverManager().install())
    return webdriver.Chrome(service=service, options=opts)

# —————— START ——————
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    btns = [[InlineKeyboardButton("4+ Goals", callback_data="g")],
            [InlineKeyboardButton("GG/BTTS", callback_data="gg")],
            [InlineKeyboardButton("DRAW", callback_data="d")]]
    await update.message.reply_text(
        "YOUR 3-IN-1 BOT IS LIVE!\n"
        "Try:\n/date today England\n/date tomorrow Greece",
        reply_markup=InlineKeyboardMarkup(btns)
    )

# —————— DATE COMMAND ——————
async def date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /date today England")
        return

    # 1. Parse date
    date_word = context.args[0].lower()
    if date_word == "today": target = datetime.today()
    elif date_word == "tomorrow": target = datetime.today() + timedelta(days=1)
    else:
        await update.message.reply_text("Use: today or tomorrow")
        return

    # 2. Parse country
    country = " ".join(context.args[1:]).title()
    await update.message.reply_text(f"Scanning {date_word} {country}...")

    # 3. Open Soccer24
    driver = get_driver()
    driver.get("https://www.soccer24.com/")
    time.sleep(4)

    # 4. Click correct date
    if "tomorrow" in date_word:
        driver.find_element("css selector", ".calendar__nav").click()
        time.sleep(2)

    # 5. Scrape matches
    soup = BeautifulSoup(driver.page_source, "html.parser")
    rows = soup.select(".event__match")
    results = []

    for row in rows:
        teams = row.select(".event__participant")
        if len(teams) < 2: continue
        home = teams[0].get_text(strip=True)
        away = teams[1].get_text(strip=True)
        league = row.find_previous("div", class_=re.compile("event__title")).get_text(strip=True)
        if country.lower() in league.lower():
            results.append(f"{home} vs {away}\n{league}")

    driver.quit()

    # 6. Reply
    if results:
        msg = f"Matches on {target.strftime('%Y-%m-%d')} in {country}\n\n" + "\n\n".join(results[:10])
    else:
        msg = f"No {country} games found {date_word}."
    await update.message.reply_text(msg)

# —————— MAIN ——————
def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("date", date))
    print("BOT IS ALIVE – SEND /start")
    app.run_polling()

# —————— FLASK FOR RENDER ——————
from flask import Flask
import threading
flask_app = Flask(__name__)
@flask_app.route("/") 
def home(): return "Bot running"
threading.Thread(target=lambda: flask_app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000))), daemon=True).start()

if __name__ == "__main__":
    main()
