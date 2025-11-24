"""
Тестовый модуль для проверки работы openai_module.
"""

import logging
from openai_module import get_questions_from_text

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_openai_module() -> None:
    """
    Тестирует функцию get_questions_from_text на примере текста.
    Выводит результат и проверяет, что возвращается ровно 5 вопросов.
    """
    # Пример текста для тестирования
    test_text = """
    Искусственный интеллект (ИИ) - это область компьютерных наук, 
    которая занимается созданием систем, способных выполнять задачи, 
    обычно требующие человеческого интеллекта. Машинное обучение является 
    подмножеством ИИ, которое позволяет компьютерам учиться на данных без 
    явного программирования. Глубокое обучение, в свою очередь, является 
    подмножеством машинного обучения, использующим нейронные сети с 
    множеством слоев для обработки сложных паттернов в данных.
    """

    logger.info('Начало тестирования функции get_questions_from_text')
    logger.info(f'Тестовый текст: {test_text[:100]}...')

    try:
        questions = get_questions_from_text(test_text)

        # Вывод результата
        print('\n' + '=' * 60)
        print('РЕЗУЛЬТАТ ТЕСТИРОВАНИЯ')
        print('=' * 60)
        print(f'\nПолучено вопросов: {len(questions)}\n')

        for i, question in enumerate(questions, 1):
            print(f'{i}. {question}')

        print('\n' + '=' * 60)

        # Проверка результата
        assert len(questions) == 5, (
            f'Ожидалось 5 вопросов, получено {len(questions)}'
        )
        assert all(isinstance(q, str) for q in questions), (
            'Все элементы должны быть строками'
        )
        assert all(q.strip() for q in questions), (
            'Все вопросы должны быть непустыми'
        )

        logger.info('✓ Тест пройден успешно!')
        print('\n✓ Тест пройден успешно!')
        print('✓ Возвращено ровно 5 вопросов')
        print('✓ Все вопросы являются непустыми строками')

    except AssertionError as e:
        logger.error(f'Тест не пройден: {e}')
        print(f'\n✗ Тест не пройден: {e}')
        raise

    except Exception as e:
        logger.error(f'Ошибка при тестировании: {e}', exc_info=True)
        print(f'\n✗ Ошибка при тестировании: {e}')
        raise


if __name__ == '__main__':
    test_openai_module()

