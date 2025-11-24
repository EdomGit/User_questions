"""
Модуль для загрузки и обработки веб-страниц.
Извлекает текст из HTML-страниц с обработкой ошибок и повторами.
"""

import argparse
import logging
import re
import sys
from typing import Optional, List
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from openai_module import get_questions_from_text

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Максимальная длина текста (10000 символов)
MAX_TEXT_LENGTH = 10000

# Максимальная длина текста для OpenAI API (примерно 8000 символов для безопасности)
MAX_TEXT_LENGTH_FOR_OPENAI = 8000

# Минимальная длина текста для генерации вопросов
MIN_TEXT_LENGTH = 50

# Значимые теги для извлечения текста
CONTENT_TAGS = [
    'p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'li', 'article', 'section',
    'div', 'span', 'main', 'blockquote', 'td', 'th', 'dd', 'dt'
]

# Теги для удаления
REMOVE_TAGS = ['script', 'style', 'nav', 'header', 'footer', 'aside', 'noscript']


def validate_url(url: str) -> bool:
    """
    Проверяет валидность URL.

    Args:
        url: URL для проверки

    Returns:
        True если URL валиден, False иначе
    """
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except Exception:
        return False


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((
        requests.exceptions.Timeout,
        requests.exceptions.ConnectionError,
        requests.exceptions.RequestException
    )),
    reraise=True
)
def fetch_html(url: str, timeout: int = 10) -> str:
    """
    Загружает HTML-контент с веб-страницы с повторами при ошибках.

    Args:
        url: URL страницы для загрузки
        timeout: Таймаут запроса в секундах

    Returns:
        HTML-контент страницы

    Raises:
        ValueError: Если URL невалиден
        requests.exceptions.HTTPError: При HTTP ошибках (4xx, 5xx)
        requests.exceptions.Timeout: При таймауте
        requests.exceptions.RequestException: При других сетевых ошибках
    """
    if not validate_url(url):
        error_msg = f'Невалидный URL: {url}'
        logger.error(error_msg)
        raise ValueError(error_msg)

    logger.info(f'Загрузка страницы: {url}')

    try:
        headers = {
            'User-Agent': (
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                'AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/91.0.4472.124 Safari/537.36'
            )
        }

        response = requests.get(url, headers=headers, timeout=timeout)
        response.raise_for_status()

        logger.info(f'Страница успешно загружена. Размер: {len(response.text)} символов')
        return response.text

    except requests.exceptions.HTTPError as e:
        error_msg = f'HTTP ошибка {response.status_code}: {str(e)}'
        logger.error(error_msg)
        raise requests.exceptions.HTTPError(error_msg) from e

    except requests.exceptions.Timeout as e:
        error_msg = f'Таймаут при загрузке страницы: {str(e)}'
        logger.error(error_msg)
        raise requests.exceptions.Timeout(error_msg) from e

    except requests.exceptions.ConnectionError as e:
        error_msg = f'Ошибка соединения: {str(e)}'
        logger.error(error_msg)
        raise requests.exceptions.ConnectionError(error_msg) from e

    except requests.exceptions.RequestException as e:
        error_msg = f'Ошибка при запросе: {str(e)}'
        logger.error(error_msg)
        raise requests.exceptions.RequestException(error_msg) from e


def clean_text(text: str) -> str:
    """
    Очищает текст от лишних пробелов и переносов строк.

    Args:
        text: Исходный текст

    Returns:
        Очищенный текст
    """
    # Заменяем множественные пробелы на один
    text = re.sub(r'\s+', ' ', text)
    # Удаляем пробелы в начале и конце строк
    text = text.strip()
    return text


def extract_text_from_url(url: str) -> str:
    """
    Извлекает текст из веб-страницы.

    Args:
        url: URL страницы для обработки

    Returns:
        Извлеченный и очищенный текст (до 6000 символов)

    Raises:
        ValueError: Если URL невалиден
        requests.exceptions.HTTPError: При HTTP ошибках
        requests.exceptions.RequestException: При сетевых ошибках
    """
    logger.info(f'Начало извлечения текста из URL: {url}')

    # Загружаем HTML
    html_content = fetch_html(url)

    # Парсим HTML
    logger.info('Парсинг HTML...')
    soup = BeautifulSoup(html_content, 'html.parser')

    # Удаляем ненужные элементы
    for tag_name in REMOVE_TAGS:
        for element in soup.find_all(tag_name):
            element.decompose()

    # Извлекаем текст из значимых тегов
    text_parts = []
    for tag_name in CONTENT_TAGS:
        elements = soup.find_all(tag_name)
        for element in elements:
            # Используем separator для лучшей обработки пробелов
            text = element.get_text(separator=' ', strip=True)
            if text and len(text.strip()) > 0:
                text_parts.append(text)

    logger.info(f'Найдено {len(text_parts)} элементов с текстом в значимых тегах')

    # Если не нашли текст в значимых тегах, берем весь текст body
    if not text_parts:
        logger.warning('Не найдено текста в значимых тегах, извлекаем весь текст body')
        body = soup.find('body')
        if body:
            body_text = body.get_text(separator=' ', strip=True)
            if body_text and len(body_text.strip()) > 0:
                text_parts.append(body_text)
                logger.info(f'Извлечен текст из body, длина: {len(body_text)} символов')
            else:
                logger.warning('Body найден, но текст пустой')
        else:
            logger.warning('Body не найден, извлекаем весь документ')
        
        # Если body тоже пустой, берем весь документ
        if not text_parts:
            full_doc_text = soup.get_text(separator=' ', strip=True)
            if full_doc_text and len(full_doc_text.strip()) > 0:
                text_parts.append(full_doc_text)
                logger.info(f'Извлечен текст из всего документа, длина: {len(full_doc_text)} символов')
            else:
                logger.error('Не удалось извлечь текст из документа')

    # Объединяем части текста
    full_text = ' '.join(text_parts) if text_parts else ''

    if not full_text or len(full_text.strip()) == 0:
        error_msg = (
            'Не удалось извлечь текст из страницы. '
            'Возможно, контент загружается динамически через JavaScript.'
        )
        logger.error(error_msg)
        raise ValueError(error_msg)

    # Очищаем текст
    cleaned_text = clean_text(full_text)

    if not cleaned_text or len(cleaned_text.strip()) == 0:
        error_msg = 'Текст стал пустым после очистки'
        logger.error(error_msg)
        raise ValueError(error_msg)

    # Ограничиваем длину
    if len(cleaned_text) > MAX_TEXT_LENGTH:
        logger.warning(
            f'Текст обрезан с {len(cleaned_text)} до {MAX_TEXT_LENGTH} символов'
        )
        cleaned_text = cleaned_text[:MAX_TEXT_LENGTH].rsplit(' ', 1)[0] + '...'

    logger.info(f'Текст успешно извлечен. Длина: {len(cleaned_text)} символов')
    return cleaned_text


def smart_truncate_text(text: str, max_length: int = MAX_TEXT_LENGTH_FOR_OPENAI) -> str:
    """
    Умная обрезка текста с сохранением смысла.
    Обрезает текст до максимальной длины, стараясь закончить на границе предложения.

    Args:
        text: Исходный текст
        max_length: Максимальная длина текста

    Returns:
        Обрезанный текст
    """
    if len(text) <= max_length:
        return text

    logger.info(f'Текст слишком длинный ({len(text)} символов), обрезка до {max_length} символов')

    # Пытаемся обрезать на границе предложения
    truncated = text[:max_length]
    
    # Ищем последнюю точку, восклицательный или вопросительный знак
    sentence_endings = ['.', '!', '?', '。', '！', '？']
    last_sentence_end = -1
    
    for ending in sentence_endings:
        pos = truncated.rfind(ending)
        if pos > max_length * 0.7:  # Ищем только в последних 30% текста
            last_sentence_end = max(last_sentence_end, pos)
    
    if last_sentence_end > 0:
        truncated = text[:last_sentence_end + 1]
        logger.info(f'Текст обрезан на границе предложения на позиции {last_sentence_end + 1}')
    else:
        # Если не нашли границу предложения, обрезаем на границе слова
        last_space = truncated.rfind(' ')
        if last_space > max_length * 0.7:
            truncated = text[:last_space]
            logger.info(f'Текст обрезан на границе слова на позиции {last_space}')
        else:
            truncated = text[:max_length]
            logger.warning(f'Текст обрезан без сохранения границ предложения/слова')

    return truncated


def generate_questions_from_url(url: str) -> List[str]:
    """
    Полнофункциональный агент для генерации вопросов из веб-страницы.
    
    Логика работы:
    1. Загружает HTML по URL
    2. Извлекает и очищает текст
    3. Проверяет достаточность текста
    4. Обрезает текст при необходимости с сохранением смысла
    5. Передает текст в OpenAI для генерации вопросов
    6. Возвращает список из 5 вопросов
    
    Args:
        url: URL веб-страницы для обработки
    
    Returns:
        Список из 5 вопросов по содержанию сайта
    
    Raises:
        ValueError: При некорректном URL или недостаточном тексте
        requests.exceptions.RequestException: При проблемах с сетью
        Exception: При ошибках OpenAI API
    """
    try:
        logger.info(f'Начало работы агента для URL: {url}')
        
        # Шаг 1: Загрузка HTML и извлечение текста
        logger.info('Шаг 1: Загрузка HTML и извлечение текста')
        try:
            text = extract_text_from_url(url)
        except ValueError as e:
            error_msg = f'Ошибка при извлечении текста: {str(e)}'
            logger.error(error_msg)
            raise ValueError(error_msg) from e
        except requests.exceptions.RequestException as e:
            error_msg = f'Сетевая ошибка при загрузке страницы: {str(e)}'
            logger.error(error_msg)
            raise requests.exceptions.RequestException(error_msg) from e
        
        # Шаг 2: Проверка достаточности текста
        logger.info('Шаг 2: Проверка достаточности текста')
        if not text or len(text.strip()) < MIN_TEXT_LENGTH:
            error_msg = (
                f'Недостаточно текста на странице для генерации вопросов. '
                f'Минимум: {MIN_TEXT_LENGTH} символов, получено: {len(text.strip()) if text else 0}'
            )
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        logger.info(f'Текст успешно извлечен. Длина: {len(text)} символов')
        
        # Шаг 3: Обрезка текста при необходимости
        logger.info('Шаг 3: Проверка и обрезка текста при необходимости')
        if len(text) > MAX_TEXT_LENGTH_FOR_OPENAI:
            text = smart_truncate_text(text, MAX_TEXT_LENGTH_FOR_OPENAI)
            logger.info(f'Текст обрезан до {len(text)} символов')
        
        # Шаг 4: Генерация вопросов через OpenAI
        logger.info('Шаг 4: Генерация вопросов через OpenAI API')
        try:
            questions = get_questions_from_text(text)
            logger.info(f'Успешно сгенерировано {len(questions)} вопросов')
            
            if len(questions) < 5:
                logger.warning(f'Получено только {len(questions)} вопросов вместо 5')
            
            return questions
            
        except ValueError as e:
            error_msg = f'Ошибка валидации при работе с OpenAI API: {str(e)}'
            logger.error(error_msg)
            raise ValueError(error_msg) from e
        except Exception as e:
            error_msg = f'Ошибка OpenAI API: {str(e)}'
            logger.error(error_msg, exc_info=True)
            raise Exception(error_msg) from e
        
    except ValueError:
        # Переподнимаем ValueError без изменений
        raise
    except requests.exceptions.RequestException:
        # Переподнимаем сетевые ошибки без изменений
        raise
    except Exception as e:
        # Обрабатываем все остальные неожиданные ошибки
        error_msg = f'Неожиданная ошибка при работе агента: {str(e)}'
        logger.error(error_msg, exc_info=True)
        raise Exception(error_msg) from e


def main() -> None:
    """
    Основная функция для запуска модуля из командной строки.
    Генерирует вопросы на основе содержимого веб-страницы.
    """
    parser = argparse.ArgumentParser(
        description='Генерация вопросов на основе содержимого веб-страницы'
    )
    parser.add_argument(
        'url',
        type=str,
        help='URL веб-страницы для обработки'
    )

    args = parser.parse_args()

    try:
        # Генерируем вопросы
        questions = generate_questions_from_url(args.url)
        
        # Выводим вопросы
        print('\nСгенерированные вопросы:')
        print('=' * 50)
        for i, question in enumerate(questions, 1):
            print(f'{i}. {question}')
        print('=' * 50)
        
        # Сохранение вопросов в файл
        output_file = 'questions.txt'
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                for i, question in enumerate(questions, 1):
                    f.write(f'{i}. {question}\n')
            logger.info(f'Вопросы сохранены в файл: {output_file}')
            print(f'\nВопросы сохранены в файл: {output_file}')
        except IOError as e:
            logger.error(f'Ошибка при сохранении в файл: {str(e)}')
            print(f'Ошибка при сохранении в файл: {str(e)}', file=sys.stderr)
        
        sys.exit(0)

    except ValueError as e:
        logger.error(f'Ошибка валидации: {str(e)}')
        print(f'Ошибка: {str(e)}', file=sys.stderr)
        sys.exit(1)

    except requests.exceptions.HTTPError as e:
        logger.error(f'HTTP ошибка: {str(e)}')
        print(f'HTTP ошибка: {str(e)}', file=sys.stderr)
        sys.exit(1)

    except requests.exceptions.Timeout as e:
        logger.error(f'Таймаут: {str(e)}')
        print(f'Таймаут при загрузке страницы: {str(e)}', file=sys.stderr)
        sys.exit(1)

    except requests.exceptions.ConnectionError as e:
        logger.error(f'Ошибка соединения: {str(e)}')
        print(f'Ошибка соединения: {str(e)}', file=sys.stderr)
        sys.exit(1)

    except requests.exceptions.RequestException as e:
        logger.error(f'Сетевая ошибка: {str(e)}')
        print(f'Сетевая ошибка: {str(e)}', file=sys.stderr)
        sys.exit(1)

    except Exception as e:
        logger.error(f'Ошибка OpenAI API: {str(e)}', exc_info=True)
        print(f'Ошибка OpenAI API: {str(e)}', file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()

