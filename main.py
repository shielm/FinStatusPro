from aiogram import Bot, Dispatcher, types, executor
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters import Command
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.contrib.fsm_storage.memory import MemoryStorage
import sqlite3
import requests
import json
from xml.etree import ElementTree
from aiogram.types import ParseMode, ReplyKeyboardMarkup, KeyboardButton

bot = Bot(token="6000838512:AAG7feFAY0z913wd-qmiIE1F5sE2G0AsNgo")

storage = MemoryStorage()

dp = Dispatcher(bot, storage=storage)

class CheckStockStates(StatesGroup):
    StockID = State()

class User:

    def __init__(self, telegram_id) -> None:
        self.telegram_id = telegram_id

    def checkUserRecord(self):
        conn = sqlite3.connect('/Users/shiel/Documents/Telegram_4/database.db')
        cursor = conn.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS users (telegram_id INTEGER PRIMARY KEY)''')
        cursor.execute('SELECT * FROM users WHERE telegram_id = ?', (self.telegram_id,))
        db_data = cursor.fetchone()
        if db_data is None:
            result = None
            conn.close()
        else:
            result = db_data[0]
            conn.close()    
        return result
    
    def createUserRecord(self):
        insterted_id = None
        conn = sqlite3.connect('/Users/shiel/Documents/Telegram_4/database.db')
        cursor = conn.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS users (telegram_id INTEGER PRIMARY KEY)''')
        cursor.execute('INSERT INTO users (telegram_id) VALUES (?)', (self.telegram_id,))
        conn.commit()
        insterted_id = cursor.lastrowid
        conn.close()
        return insterted_id 

def checkStockExistance(stock_id):
    url = f"https://iss.moex.com/iss/securities/{stock_id}.json"
    
    response = requests.get(url)

    if response.status_code == 200:
        data = response.json()
        exist = data.get("boards", {}).get("data", [])
        return bool(exist)
    else:
        return False
    
def getStockPrice(stock_id):
    url = f"https://iss.moex.com/iss/engines/stock/markets/shares/boards/TQBR/securities/{stock_id}.json?iss.only=securities&securities.columns=PREVPRICE,CURRENCYID"
    response = requests.get(url)

    if response.status_code == 200:
        data = response.json()
        stock_price = data.get("securities", {}).get("data", [[]])[0][0]
        stock_currency = data.get("securities", {}).get("data", [[]])[0][1]

        if stock_currency == "SUR":
            stock_currency = "RUB"
        stock_info = str(stock_price) + " " + str(stock_currency)
        return stock_info
    else: 
        return False

@dp.message_handler(commands=['start'])
async def start_command(message: types.Message):
    user = User(message.from_user.id)
    user_record = user.checkUserRecord()
    if user_record is None:
        user.createUserRecord() 
        await message.reply("Привет! Регистрация пользователя успешно \n Чтобы посмотреть все команды введите /help")
    else:
        await message.reply("Привет! Рады видеть вас  \n Напоминаем - чтобы посмотреть все команды введите /help")

@dp.message_handler(commands=['help'])
async def send_help(message: types.Message):
    await message.reply("Доступные команды: \n /getStock - Показывает текущую стоимость ценный бумаг на Мосбирже \n /currency - Показывает текущих курс валют от ЦБ РФ \n /crypto - Показывает текущую стоимость популярных криптовалют")

@dp.message_handler(commands=['getStock'])
async def getStock_start(message: types.Message):
    await message.reply("Введите идентификатор ценной бумаги")
    await CheckStockStates.StockID.set()

@dp.message_handler(state=CheckStockStates.StockID)
async def getStock_exec(message: types.Message, state: FSMContext):
    stock_id = message.text.upper()
    if checkStockExistance(stock_id) == True:
        stock_price = getStockPrice(stock_id)
        if stock_price != False:
            await message.reply("Ценная бумага " + str(stock_id) + " найдена на Московской бирже. Стоимость: " + str(stock_price))
        else:
            await message.reply("He удалось получить данные от Московской биржи")    
    else:
        await message.reply("He удалось найти ценную бумагу")
    await state.finish()

def get_currency_rate(from_currency: str, to_currency: str) -> float:
    response = requests.get("http://www.cbr.ru/scripts/XML_daily.asp")
    tree = ElementTree.fromstring(response.content)

    from_currency_rate = None
    to_currency_rate = None

    for item in tree.iter("Valute"):
        if item.find("CharCode").text == from_currency:
            from_currency_rate = float(item.find("Value").text.replace(",", "."))
        if item.find("CharCode").text == to_currency:
            to_currency_rate = float(item.find("Value").text.replace(",", "."))

    if from_currency_rate is None or to_currency_rate is None:
        return None

    return to_currency_rate / from_currency_rate

@dp.message_handler(commands=['currency'])
async def currency_command(message: types.Message):
    command_parts = message.text.split(" ")
    if len(command_parts) != 3:
        await message.reply("Использование: /currency [вaлютa1] [вaлютa2]")
        return

    from_currency = command_parts[1]
    to_currency = command_parts[2]

    rate = get_currency_rate(from_currency.upper(), to_currency.upper())
    if rate is None:
        await message.reply("He удалось получить курс валют")
    else:
        await message.reply(f"Kypc {from_currency.upper()} к {to_currency.upper()} составляет {rate:.4f}")

URL = 'https://api.coingecko.com/api/v3/simple/price?ids={}&vs_currencies={}'

CRYPTO_LIST = ['bitcoin', 'ethereum', 'ripple', 'litecoin', 'dogecoin']

CURRENCY_LIST = ['usd', 'eur', 'rub']

keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
for currency in CURRENCY_LIST:
    button = KeyboardButton(currency.upper())
    keyboard.add(button)

@dp.message_handler(commands=['crypto'])
async def start_command(message: types.Message):
    await message.reply('Выбери валюту:', reply_markup=keyboard)

@dp.message_handler(lambda message: message.text.lower() in CURRENCY_LIST)
async def crypto_command(message: types.Message):
    currency = message.text.lower()
    crypto_prices = {}
    for crypto in CRYPTO_LIST:
        url = URL.format(crypto, currency)
        response = requests.get(url)
        data = json.loads(response.text)
        price = data[crypto][currency]
        crypto_prices[crypto] = price
    text = ''
    for crypto, price in crypto_prices.items():
        text += f'{crypto.capitalize()}: {price} {currency.upper()}\n'
    await message.reply(text, reply_markup=keyboard)

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)