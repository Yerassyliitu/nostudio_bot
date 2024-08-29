from aiogram import Bot, Dispatcher
from aiogram.filters import Command, CommandStart
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, Message, ReplyKeyboardRemove
import requests
import os
import asyncio
import logging
import sys
from dotenv import load_dotenv

load_dotenv()

API_TOKEN = os.getenv('API_TOKEN')
MAIN_DOMAIN = os.getenv('MAIN_DOMAIN')

bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# Загружаем данные с API
service_types = requests.get(f'{MAIN_DOMAIN}/api/service_types').json()
messenger_types = requests.get(f'{MAIN_DOMAIN}/api/messenger_types').json()

# Создаем клавиатуры
service_type_buttons = [KeyboardButton(text=service_type['name']) for service_type in service_types]
service_types_keyboard = ReplyKeyboardMarkup(
    keyboard=[[button] for button in service_type_buttons] + [[KeyboardButton(text="Готово")]],
    resize_keyboard=True
)

messenger_type_buttons = [KeyboardButton(text=messenger_type['name']) for messenger_type in messenger_types]
messenger_types_keyboard = ReplyKeyboardMarkup(
    keyboard=[[button] for button in messenger_type_buttons],
    resize_keyboard=True
)

skip_button = KeyboardButton(text="Пропустить")
skip_keyboard = ReplyKeyboardMarkup(
    keyboard=[[skip_button]],
    resize_keyboard=True
)

# Определяем состояния
class OrderForm(StatesGroup):
    service_type = State()
    name = State()
    project_name = State()
    messenger_type = State()
    contact = State()
    budget = State()
    message = State()

# Список для хранения выбранных service_types
selected_service_types = []

@dp.message(CommandStart())
async def command_start_handler(message: Message) -> None:
    await message.answer(f"Здравствуйте! Я бот для оформления заказов. Я могу помочь вам создать новый заказ, выбрав подходящий тариф и оставив свои контактные данные. Чтобы начать, введите команду /order.")

@dp.message(Command(commands=['order']))
async def cmd_order(message: Message, state: FSMContext):
    await state.set_state(OrderForm.service_type)
    global selected_service_types
    selected_service_types = []
    await message.answer("Выберите тип услуги (можно выбрать несколько):", reply_markup=service_types_keyboard)

# Обработка выбора service_types
@dp.message(OrderForm.service_type)
async def process_service_type(message: Message, state: FSMContext):
    global selected_service_types

    if message.text == "Готово":
        if not selected_service_types:
            await message.answer("Пожалуйста, выберите хотя бы один тип услуги.")
            return

        # Сохраняем выбранные service_types и переходим к следующему шагу
        await state.update_data(service_type=selected_service_types)
        await state.set_state(OrderForm.name)
        await message.answer("Введите ваше имя:", reply_markup=ReplyKeyboardRemove())
        selected_service_types = []  # Очищаем список для следующего пользователя
    else:
        selected_service = next((st for st in service_types if st['name'] == message.text), None)
        if not selected_service:
            await message.answer("Пожалуйста, выберите тип услуги, используя предложенные варианты.")
            return

        # Добавляем или удаляем тип из списка выбранных
        if selected_service['id'] in selected_service_types:
            selected_service_types.remove(selected_service['id'])
            await message.answer(f"{message.text} удален из выбранных типов услуг.")
        else:
            selected_service_types.append(selected_service['id'])
            await message.answer(f"{message.text} добавлен в выбранные типы услуг.\nЕсли хотите добавить еще, нажмите на услугу.\nЕсли хотите удалить, нажмите еще раз.\nЕсли закончили, нажмите 'Готово'.")

# Получаем имя
@dp.message(OrderForm.name)
async def process_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text)
    await state.set_state(OrderForm.project_name)
    await message.answer("Введите название проекта:")

# Получаем название проекта
@dp.message(OrderForm.project_name)
async def process_project_name(message: Message, state: FSMContext):
    await state.update_data(project_name=message.text)
    await state.set_state(OrderForm.messenger_type)
    await message.answer("Выберите тип мессенджера:", reply_markup=messenger_types_keyboard)

# Получаем messenger_type
@dp.message(OrderForm.messenger_type)
async def process_messenger_type(message: Message, state: FSMContext):
    selected_messenger = next((mt for mt in messenger_types if mt['name'] == message.text), None)
    if not selected_messenger:
        await message.answer("Пожалуйста, выберите тип мессенджера, используя предложенные варианты.")
        return
    await state.update_data(messenger_type=selected_messenger['id'])
    await state.set_state(OrderForm.contact)
    await message.answer("Введите ваш контакт (телефон, email и т.д.):")

# Получаем контакт
@dp.message(OrderForm.contact)
async def process_contact(message: Message, state: FSMContext):
    await state.update_data(contact=message.text)
    await state.set_state(OrderForm.budget)
    await message.answer("Введите бюджет (число) в долларах:")

# Получаем бюджет
@dp.message(OrderForm.budget)
async def process_budget(message: Message, state: FSMContext):
    try:
        budget = int(message.text)
        await state.update_data(budget=budget)
        await state.set_state(OrderForm.message)
        await message.answer("Введите сообщение (если не хотите оставлять сообщение, нажмите 'Пропустить'):", reply_markup=skip_keyboard)
    except ValueError:
        await message.answer("Пожалуйста, введите числовое значение для бюджета.")

# Получаем сообщение
@dp.message(OrderForm.message)
async def process_message(message: Message, state: FSMContext):
    user_data = await state.get_data()
    
    if message.text == "Пропустить":
        message_text = None
    else:
        message_text = message.text

    data = {
        "name": user_data['name'],
        "project_name": user_data['project_name'],
        "contact": user_data['contact'],
        "budget": user_data['budget'],
        "message": message_text,
        "service_types": user_data['service_type'],
        "messenger_type": user_data['messenger_type']
    }
    
    response = requests.post(f'{MAIN_DOMAIN}/api/orders/', json=data)
    
    if response.status_code == 201:
        await message.answer("Заявка успешно отправлена!")
    else:
        await message.answer("Произошла ошибка при отправке заявки.")
    
    await state.clear()

async def main() -> None:
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    asyncio.run(main())
