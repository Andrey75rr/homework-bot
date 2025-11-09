import logging
import os
import sys
import time

import requests
from dotenv import load_dotenv
from telebot import TeleBot


load_dotenv()


PRACTICUM_TOKEN = os.getenv('PR_TOKEN')
TELEGRAM_TOKEN = os.getenv('TOKEN')
TELEGRAM_CHAT_ID = 273347472

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)


def check_tokens():
    """Проверяет доступность обязательных переменных окружения."""
    return all([PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID])


def send_message(bot, message):
    """Отправляет сообщение в Telegram-чат."""
    try:
        bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text=message
        )
        logging.debug('Сообщение отправленно успешно')
    except Exception as error:
        logging.error(f'Сообщение отправлено с ошибкой {error}')


def get_api_answer(timestamp):
    """Делает запрос к API-сервису."""
    try:
        params = {'from_date': timestamp}
        response = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params=params
        )
        if response.status_code != 200:
            raise Exception(f"API вернул код состояния {response.status_code}")
        return response.json()
    except requests.exceptions.RequestException as error:
        logging.error(f'Ошибка соединения с API: {error}')


def check_response(response):
    """Проверяет ответ API на соответствие документации."""
    try:
        if not isinstance(response, dict):
            raise TypeError('Ответ API должен быть словарем')
        if 'homeworks' not in response:
            raise KeyError('В ответе API отсутствует ключ homeworks')
        homeworks = response['homeworks']
        if not isinstance(homeworks, list):
            raise TypeError('homeworks должен быть списком')
        if homeworks is None:
            raise KeyError('homeworks не может быть None')
        return homeworks
    except (TypeError, KeyError) as error:
        logging.error(f'Неверная структура ответа API: {error}')
        raise


def parse_status(homework):
    """Извлекает статус домашней работы и возвращает сообщение."""
    try:
        homework_name = homework.get('homework_name')
        homework_status = homework.get('status')
        if not homework_name or not homework_status:
            raise KeyError('В ответе отсутствуют обязательные поля')
        if homework_status not in HOMEWORK_VERDICTS:
            raise ValueError(f'Неизвестный статус работы: {homework_status}')
        verdict = HOMEWORK_VERDICTS[homework_status]

        return f'Изменился статус проверки работы "{homework_name}". {verdict}'
    except (KeyError, ValueError) as error:
        logging.error(f'Ошибка парсинга статуса: {error}')
        raise


def main():
    """Основная логика работы бота."""
    bot = TeleBot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    previous_status = None
    previous_error = None

    if not check_tokens():
        logging.critical('Отсутствуют обязательные переменные окружения')
        exit(1)

    while True:
        try:
            response = get_api_answer(timestamp)
            homeworks_list = check_response(response)
            previous_error = None

            if not homeworks_list:
                logging.debug('Нет новых домашних работ')
            else:
                homework = homeworks_list[0]
                if homework['status'] != previous_status:
                    message = parse_status(homework)
                    send_message(bot, message)
                previous_status = homework['status']

            timestamp = int(time.time())

        except Exception as error:
            error_message = f'Сбой в работе программы: {error}'
            logging.error(error_message)
            if str(error) != previous_error:
                send_message(bot, error_message)
                previous_error = str(error)
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
