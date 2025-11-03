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
  async def date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /date today England")
        return
    date_word = context.args[0].lower()
    country = " ".join(context.args[1:]).title()
    if date_word not in ["today", "tomorrow"]:
        await update.message.reply_text("Use today or tomorrow")
        return
    await update.message.reply_text(f"Scanning {date_word} {country}...")
    driver = get_driver()
    try:
        driver.get("https://www.soccer24.com/")
        time.sleep(5)
        if date_word == "tomorrow":
            driver.find_element(By.CSS_SELECTOR, ".calendar__nav").click()
            time.sleep(2)
        soup = BeautifulSoup(driver.page_source, "html.parser")
        matches = []
        for row in soup.select(".event__match"):
            league_div = row.find_previous("div", class_=re.compile("event__title"))
            league = league_div.get_text(strip=True) if league_div else ""
            if country.lower() in league.lower():
                home = row.select_one(".event__participant--home").get_text(strip=True)
                away = row.select_one(".event__participant--away").get_text(strip=True)
                time_str = row.select_one(".event__time").get_text(strip=True)
                matches.append(f"{home} vs {away}\n{league}\n{time_str} UK")
        if matches:
            reply = f"{date_word.title()} {country} games:\n\n" + "\n\n".join(matches[:10])
        else:
            reply = f"No {country} games {date_word}. Try /date tomorrow England for late games."
        await update.message.reply_text(reply)
    except Exception as e:
        await update.message.reply_text(f"Error: {str(e)[:100]}")
    finally:
        driver.quit()

    await update.message.reply_text(f"Scanning {date_word} {country}...")

    driver = get_driver()
    try:
        driver.get("https://www.soccer24.com/")
        time.sleep(5)  # Wait for load

        # NEW: Click calendar ONLY for tomorrow
        if date_word == "tomorrow":
            driver.find_element(By.CSS_SELECTOR, ".calendar__nav").click()
            time.sleep(2)

        soup = BeautifulSoup(driver.page_source, "html.parser")
        matches = []

        for row in soup.select(".event__match"):
            league_div = row.find_previous("div", class_=re.compile("event__title"))
            league = league_div.get_text(strip=True) if league_div else ""
            if country.lower() in league.lower():
                home = row.select_one(".event__participant--home").get_text(strip=True)
                away = row.select_one(".event__participant--away").get_text(strip=True)
                time_str = row.select_one(".event__time").get_text(strip=True)
                matches.append(f"{home} vs {away}\n{league}\n{time_str} UK")

        if matches:
            reply = f"{date_word.title()} {country} games:\n\n" + "\n\n".join(matches[:10])
        else:
            reply = f"No {country} games {date_word}. Try /date tomorrow England for late games."

        await update.message.reply_text(reply)

    except Exception as e:
        await update.message.reply_text(f"Error: {str(e)[:100]}")
    finally:
        driver.quit()
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


