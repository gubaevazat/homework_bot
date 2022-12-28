import http
import json
import logging
import os
import sys
import time
from logging import Formatter, StreamHandler

from dotenv import load_dotenv

from exeptions import NoEnvironmentVarError

import requests

import telegram

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


def get_logger(name):
    """Функция возвращает экземпляр логгера."""
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    handler = StreamHandler(stream=sys.stdout)
    handler.setFormatter(Formatter(
        '%(asctime)s [%(levelname)s] %(message)s, %(funcName)s'
    ))
    logger.addHandler(handler)
    return logger


logger = get_logger(__name__)


def check_tokens():
    """Проверка переменных окружения."""
    tokens = {
        'Яндекс-практикум токен': PRACTICUM_TOKEN,
        'Телеграмм токен': TELEGRAM_TOKEN,
        'Телеграмм chat_id': TELEGRAM_CHAT_ID,
    }
    for name, token in tokens.items():
        if token is None:
            logger.critical(
                f'Отсутствует переменная - {name}, бот завершает работу!'
            )
            raise NoEnvironmentVarError


def send_message(bot, message):
    """Отправка сообщения в чат."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.debug('Отправлено сообщение.')
    except telegram.error.TelegramError as error:
        logger.error(f'Ошибка отпрвки сообщения: {error}')


def get_api_answer(timestamp):
    """Запрос и ответ API."""
    try:
        response = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params={'from_date': timestamp}
        )
        if response.status_code != http.HTTPStatus.OK:
            raise ConnectionError(
                f'Ошибка соединения код-{response.status_code}'
            )
        return response.json()
    except requests.RequestException('Ошибка запроса к API!'):
        raise
    except json.JSONDecodeError:
        raise
    except Exception:
        raise


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
    if response['homeworks'] == []:
        return False
    return True


def parse_status(homework):
    """Возврат информации о статусе домашней работы."""
    if 'homework_name' not in homework or 'status' not in homework:
        raise KeyError('Отсутствую необходимы ключи в ответе API!')
    homework_status = homework['status']
    if homework_status not in HOMEWORK_VERDICTS:
        raise KeyError('Несуществующий статус домашней работы!')
    homework_name = homework['homework_name']
    verdict = HOMEWORK_VERDICTS[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    check_tokens()
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
