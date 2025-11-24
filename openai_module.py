"""
Модуль для работы с OpenAI API.
Генерирует пользовательские вопросы на основе текста.
"""

import logging
import os

from dotenv import load_dotenv
from openai import OpenAI
from openai import APIError, RateLimitError, APIConnectionError, APITimeoutError
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Загрузка переменных окружения
load_dotenv()

# Инициализация клиента OpenAI
API_KEY = os.getenv('OPENAI_API_KEY')
OPENAI_BASE_URL = os.getenv('OPENAI_BASE_URL')

if not API_KEY:
    logger.warning('OPENAI_API_KEY не найден в .env файле')

# Инициализация клиента с опциональным base_url
if API_KEY:
    client_kwargs = {'api_key': API_KEY}
    if OPENAI_BASE_URL:
        client_kwargs['base_url'] = OPENAI_BASE_URL
        logger.info(f'Используется кастомный URL: {OPENAI_BASE_URL}')
    client = OpenAI(**client_kwargs)
else:
    client = None

MODEL_NAME = 'gpt-4o-mini'


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((Exception,)),
    reraise=True
)
def get_questions_from_text(text: str) -> list[str]:
    """
    Генерирует список из 5 пользовательских вопросов на основе текста.

    Args:
        text: Исходный текст для анализа

    Returns:
        Список из 5 строк с вопросами

    Raises:
        ValueError: Если API ключ не настроен или текст пустой
        Exception: При ошибках API запроса
    """
    if not client:
        error_msg = 'OpenAI API ключ не настроен. Проверьте .env файл.'
        logger.error(error_msg)
        raise ValueError(error_msg)

    if not text or not text.strip():
        error_msg = 'Текст не может быть пустым'
        logger.error(error_msg)
        raise ValueError(error_msg)

    try:
        logger.info('Отправка запроса к OpenAI API...')

        prompt = (
            "Ты пользователь. Какие вопросы у тебя возникли после прочтения?\n\n"
            f"Текст:\n{text}\n\n"
            "Сгенерируй ровно 5 содержательных вопросов, связанных с темой страницы. "
            "Каждый вопрос должен быть на отдельной строке, без нумерации и без дополнительных символов."
        )

        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {
                    'role': 'system',
                    'content': (
                        'Ты помощник, который генерирует вопросы на основе текста. '
                        'Всегда возвращай ровно 5 вопросов, каждый на отдельной строке. '
                        'Не используй нумерацию и маркеры списка.'
                    )
                },
                {
                    'role': 'user',
                    'content': prompt
                }
            ],
            max_completion_tokens=1000
        )

        # Проверяем ответ
        if not response.choices:
            error_msg = 'API вернул ответ без choices'
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        message_content = response.choices[0].message.content
        
        # Если контент пустой, но есть reasoning tokens, значит ответ был обрезан
        if not message_content or not message_content.strip():
            finish_reason = response.choices[0].finish_reason
            usage = response.usage
            error_msg = (
                f'API вернул пустой контент. '
                f'Finish reason: {finish_reason}, '
                f'Completion tokens: {usage.completion_tokens if usage else "N/A"}, '
                f'Reasoning tokens: {usage.completion_tokens_details.reasoning_tokens if usage and usage.completion_tokens_details else "N/A"}. '
                f'Увеличьте max_completion_tokens или используйте другую модель.'
            )
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        result_text = response.choices[0].message.content.strip()
        logger.info(f'Получен ответ от API (полный текст, {len(result_text)} символов): {repr(result_text)}')

        # Разбиваем на строки
        all_lines = [line.strip() for line in result_text.split('\n') if line.strip()]
        
        questions = []
        for line in all_lines:
            # Удаляем нумерацию в начале (1., 2., 3., и т.д.)
            cleaned = line
            # Проверяем, начинается ли строка с цифры и точки
            if cleaned and cleaned[0].isdigit():
                # Удаляем нумерацию (1., 2., 10. и т.д.)
                parts = cleaned.split('.', 1)
                if len(parts) == 2:
                    cleaned = parts[1].strip()
            
            # Удаляем маркеры списка (-, *, •)
            if cleaned.startswith(('-', '*', '•')):
                cleaned = cleaned[1:].strip()
            
            # Пропускаем пустые строки и слишком короткие
            if cleaned and len(cleaned) > 3:
                questions.append(cleaned)
        
        # Если вопросов меньше 5, пробуем более простой подход
        if len(questions) < 5:
            # Берем все непустые строки
            questions = [q for q in all_lines if q and len(q) > 3]
            # Удаляем нумерацию и маркеры
            questions = [
                q.split('.', 1)[-1].strip().lstrip('-*•').strip()
                for q in questions
            ]
            questions = [q for q in questions if q and len(q) > 3]

        # Ограничиваем до 5 вопросов
        questions = questions[:5]

        if len(questions) < 5:
            logger.warning(
                f'Получено только {len(questions)} вопросов вместо 5. '
                f'Сырой ответ: {result_text[:500]}'
            )

        logger.info(f'Успешно сгенерировано {len(questions)} вопросов')
        return questions[:5]

    except RateLimitError as e:
        error_msg = f'Превышен лимит запросов к OpenAI API: {str(e)}'
        logger.error(error_msg)
        raise Exception(error_msg) from e
    except APIConnectionError as e:
        error_msg = f'Ошибка соединения с OpenAI API: {str(e)}'
        logger.error(error_msg)
        raise Exception(error_msg) from e
    except APITimeoutError as e:
        error_msg = f'Таймаут при запросе к OpenAI API: {str(e)}'
        logger.error(error_msg)
        raise Exception(error_msg) from e
    except APIError as e:
        error_msg = f'Ошибка OpenAI API: {str(e)}'
        logger.error(error_msg)
        raise Exception(error_msg) from e
    except Exception as e:
        error_msg = f'Неожиданная ошибка при работе с OpenAI API: {str(e)}'
        logger.error(error_msg, exc_info=True)
        raise Exception(error_msg) from e

