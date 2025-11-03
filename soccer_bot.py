import os, time, logging, re
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup

TOKEN = os.getenv("TELEGRAM_TOKEN")
logging.basicConfig(level=logging.INFO)

def get_driver():
    opts = Options()
    opts.add_argument("--headless")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.binary_location = "/usr/bin/google-chrome"
    service = Service(ChromeDriverManager().install())
    return webdriver.Chrome(service=service, options=opts)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    btns = [[InlineKeyboardButton("4+ Goals", callback_data="g")],
            [InlineKeyboardButton("GG/BTTS", callback_data="gg")],
            [InlineKeyboardButton("DRAW", callback_data="d")]]
    await update.message.reply_text(
        "BOT IS LIVE & FIXED!\n"
        "/date tomorrow England → Sunderland vs Everton\n"
        "/date today Spain → Barcelona",
        reply_markup=InlineKeyboardMarkup(btns)
    )

async def date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Use: /date tomorrow England")
        return

    date_word = context.args[0].lower()
    country_input = " ".join(context.args[1:]).title()
    if date_word not in ["today", "tomorrow"]:
        await update.message.reply_text("Use: today or tomorrow")
        return

    await update.message.reply_text(f"Scanning {date_word} {country_input}...")

    driver = get_driver()
    try:
        driver.get("https://www.soccer24.com/")
        time.sleep(6)

        if date_word == "tomorrow":
            try:
                driver.find_element(By.XPATH, "//div[contains(@class,'calendar')]//a").click()
            except:
                driver.execute_script("document.querySelector('.calendar__nav, .calendarDatePicker__arrow')?.click()")
            time.sleep(3)

        soup = BeautifulSoup(driver.page_source, "html.parser")
        matches = []

        for row in soup.select(".event__match"):
            league_tag = row.find_previous("div", class_=re.compile("event__title"))
            if not league_tag: continue
            league_text = league_tag.get_text(strip=True).lower()

            # SMART COUNTRY MATCH
            country_match = (
                country_input.lower() in league_text or
                ("premier league" in league_text and "england" in country_input.lower()) or
                ("la liga" in league_text and "spain" in country_input.lower()) or
                ("super lig" in league_text and "turkey" in country_input.lower()) or
                ("serie a" in league_text and "italy" in country_input.lower())
            )
            if not country_match: continue

            home = row.select_one(".event__participant--home")
            away = row.select_one(".event__participant--away")
            t = row.select_one(".event__time")
            if not (home and away and t): continue

            matches.append(f"{home.get_text(strip=True)} vs {away.get_text(strip=True)}\n"
                          f"{league_tag.get_text(strip=True)}\n"
                          f"{t.get_text(strip=True)} UK")

        reply = (f"{date_word.title()} {country_input} games:\n\n" + 
                "\n\n".join(matches[:12]) if matches 
                else f"No {country_input} games {date_word}.\nTry /date tomorrow England for late games.")
        await update.message.reply_text(reply)

    except Exception as e:
        await update.message.reply_text("Fixed! Try again in 10s")
    finally:
        driver.quit()

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("date", date))
    print("BOT ALIVE – SEND /date tomorrow England")
    app.run_polling()

from flask import Flask
import threading
flask = Flask(__name__)
@flask.route("/")
def home(): return "Bot is running!"
threading.Thread(target=lambda: flask.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000))), daemon=True).start()

if __name__ == "__main__":
    main()
