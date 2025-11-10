import logging
import os
import sys
import time

import requests
from dotenv import load_dotenv
from telebot import TeleBot
from http import HTTPStatus


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
    tokens_ok = True

    if not PRACTICUM_TOKEN:
        logging.critical('Отсутствует переменная окружения: PRACTICUM_TOKEN')
        tokens_ok = False

    if not TELEGRAM_TOKEN:
        logging.critical('Отсутствует переменная окружения: TELEGRAM_TOKEN')
        tokens_ok = False

    if not TELEGRAM_CHAT_ID:
        logging.critical('Отсутствует переменная окружения: TELEGRAM_CHAT_ID')
        tokens_ok = False

    return tokens_ok


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
    params = {'from_date': timestamp}
    try:
        response = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params=params
        )
    except requests.exceptions.RequestException as error:
        logging.error(f'Ошибка соединения с API: {error}')
        raise Exception(f'Ошибка запроса к API: {error}')

    if response.status_code != HTTPStatus.OK:
        raise Exception(f"API вернул код состояния {response.status_code}")
    return response.json()


def check_response(response):
    """Проверяет ответ API на соответствие документации."""
    if not isinstance(response, dict):
        raise TypeError('Ответ API должен быть словарем')
    if 'homeworks' not in response:
        raise KeyError('В ответе API отсутствует ключ homeworks')
    homeworks = response['homeworks']
    if not isinstance(homeworks, list):
        raise TypeError('homeworks должен быть списком')
    return homeworks


def parse_status(homework):
    """Извлекает статус домашней работы и возвращает сообщение."""
    if 'homework_name' not in homework or 'status' not in homework:
        raise KeyError('В ответе отсутствуют обязательные поля')

    homework_name = homework['homework_name']
    homework_status = homework['status']

    if homework_status not in HOMEWORK_VERDICTS:
        raise ValueError(f'Неизвестный статус работы: {homework_status}')

    verdict = HOMEWORK_VERDICTS[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        logging.critical('Отсутствуют обязательные переменные окружения')
        exit(1)

    bot = TeleBot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    previous_status = None
    previous_error = None

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
