import http
import json
import logging
import os
import sys
import time
from logging.handlers import RotatingFileHandler

import requests
import telegram
from dotenv import load_dotenv

load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

file_handler = RotatingFileHandler(
    'homework_bot.log',
    maxBytes=50000000,
    backupCount=5,
    encoding='utf8'
)
stream_handler = logging.StreamHandler(stream=sys.stdout)
logging.basicConfig(
    level=logging.ERROR,
    format='%(asctime)s [%(levelname)s] %(message)s, %(funcName)s',
    handlers=(file_handler, stream_handler)
)
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


def check_tokens():
    """Проверка переменных окружения."""
    return all([PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID])


def send_message(bot, message):
    """Отправка сообщения в чат."""
    logger.debug(f'Отправляется сообщение: {message}')
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.debug('Сообщение оправлено.')
    except telegram.error.TelegramError as error:
        logger.error(f'Ошибка отправки сообщения: {error}')


def get_api_answer(timestamp):
    """Запрос и ответ API."""
    try:
        response = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params={'from_date': timestamp}
        )
        if response.status_code != http.HTTPStatus.OK:
            template = (
                'Ошибка соединения!!! '
                'Заголовки ответа сервера: {headers}. '
                'Контент запрашиваемой страницы: {text}. '
                'Заголовки запроса: {request_headers}. '
                'Метод запроса: {request_method}. '
            )
            raise ConnectionError(template.format(
                headers=response.headers,
                text=response.text,
                request_headers=response.request.headers,
                request_method=response.request.method
            ))
    except requests.RequestException as error:
        raise error('Ошибка запроса к API!')
    except json.JSONDecodeError as error:
        raise error(
            'Ошибка декодирования файла json ответа API!'
        )
    return response.json()


def check_response(response):
    """Проверка ответа API на соответствие."""
    if not isinstance(response, dict):
        raise TypeError('Ответ API должен быть словарем!')
    if 'homeworks' not in response:
        raise KeyError('В ответе API отсутствует ключ homeworks!')
    if 'current_date' not in response:
        raise KeyError('В ответе API отсутствует ключ current_date!')
    if not isinstance(response['homeworks'], list):
        raise TypeError('По ключу homeworks должен быть список!')
    if len(response['homeworks']) == 0:
        return False
    return True


def parse_status(homework):
    """Возврат информации о статусе домашней работы."""
    if 'homework_name' not in homework:
        raise KeyError('Отсутствует ключ homework_name в ответе API!')
    if 'status' not in homework:
        raise KeyError('Отсутствует ключ status в ответе API!')
    homework_status = homework['status']
    if homework_status not in HOMEWORK_VERDICTS:
        raise KeyError('Несуществующий статус домашней работы!')
    homework_name = homework['homework_name']
    verdict = HOMEWORK_VERDICTS[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        logger.critical(
            'Отсутствует переменные окружения, бот завершает работу!'
        )
        sys.exit('Отсутствует переменные окружения, бот завершает работу!')
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    status = None
    message = None
    while True:
        try:
            api_answer = get_api_answer(int(time.time()))
            if check_response(api_answer):
                new_status = parse_status(api_answer['homeworks'][-1])
                if new_status != status:
                    status = new_status
                    send_message(bot, status)
                else:
                    logger.debug('Статус работы не изменился.')
            else:
                logger.debug('Статус работы не изменился.')
        except Exception as error:
            new_message = f'Сбой в работе программы: {error}'
            logger.error(message)
            if new_message != message:
                message = new_message
                send_message(bot, message)
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
