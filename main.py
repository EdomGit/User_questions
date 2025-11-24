"""
FastAPI приложение для генерации вопросов из веб-страниц.
"""

import logging
from typing import List

import requests
from fastapi import FastAPI, HTTPException, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, HttpUrl, ValidationError

from agent import generate_questions_from_url

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Создание FastAPI приложения
app = FastAPI(
    title="Question Generator API",
    description="API для генерации вопросов на основе содержимого веб-страниц",
    version="1.0.0"
)


# Pydantic модели для валидации
class GenerateQuestionsRequest(BaseModel):
    """Модель запроса для генерации вопросов."""
    url: str

    class Config:
        json_schema_extra = {
            "example": {
                "url": "https://example.com/article"
            }
        }


class GenerateQuestionsResponse(BaseModel):
    """Модель ответа с вопросами."""
    questions: List[str]

    class Config:
        json_schema_extra = {
            "example": {
                "questions": [
                    "Какой основной вопрос рассматривается в статье?",
                    "Какие ключевые моменты выделены?",
                    "Какие примеры приведены?",
                    "Какие выводы можно сделать?",
                    "Какие вопросы остались открытыми?"
                ]
            }
        }


class ErrorResponse(BaseModel):
    """Модель ответа с ошибкой."""
    error: str
    detail: str


@app.get("/", tags=["Root"])
async def root():
    """
    Корневой endpoint с информацией об API.
    """
    return {
        "message": "Question Generator API",
        "version": "1.0.0",
        "description": "API для генерации вопросов на основе содержимого веб-страниц",
        "endpoints": {
            "POST /generate-questions": "Генерация вопросов из URL веб-страницы",
            "GET /docs": "Интерактивная документация API (Swagger UI)",
            "GET /redoc": "Альтернативная документация API (ReDoc)"
        }
    }


@app.post(
    "/generate-questions",
    response_model=GenerateQuestionsResponse,
    status_code=status.HTTP_200_OK,
    tags=["Questions"],
    summary="Генерация вопросов из веб-страницы",
    description="Принимает URL веб-страницы и возвращает список из 5 вопросов на основе её содержимого"
)
async def generate_questions(request: GenerateQuestionsRequest):
    """
    Генерирует вопросы на основе содержимого веб-страницы.

    Args:
        request: Запрос с URL веб-страницы

    Returns:
        JSON с массивом из 5 вопросов

    Raises:
        HTTPException: При ошибках валидации, сетевых ошибках или ошибках OpenAI API
    """
    try:
        logger.info(f"Получен запрос на генерацию вопросов для URL: {request.url}")

        # Валидация URL через Pydantic (опционально, можно использовать HttpUrl)
        # Но для совместимости с существующей функцией validate_url используем строку
        
        # Генерация вопросов
        questions = generate_questions_from_url(request.url)

        # Проверяем, что получили вопросы
        if not questions or len(questions) == 0:
            error_msg = "Не удалось сгенерировать вопросы"
            logger.error(error_msg)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=error_msg
            )

        # Ограничиваем до 5 вопросов (на случай если вернулось больше)
        questions = questions[:5]

        logger.info(f"Успешно сгенерировано {len(questions)} вопросов")
        return GenerateQuestionsResponse(questions=questions)

    except ValueError as e:
        # Ошибки валидации URL или недостаточного текста
        error_msg = str(e)
        logger.error(f"Ошибка валидации: {error_msg}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_msg
        )

    except requests.exceptions.HTTPError as e:
        # HTTP ошибки (4xx, 5xx)
        error_msg = f"HTTP ошибка при загрузке страницы: {str(e)}"
        logger.error(error_msg)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_msg
        )

    except requests.exceptions.Timeout as e:
        # Таймаут при загрузке страницы
        error_msg = f"Таймаут при загрузке страницы: {str(e)}"
        logger.error(error_msg)
        raise HTTPException(
            status_code=status.HTTP_408_REQUEST_TIMEOUT,
            detail=error_msg
        )

    except requests.exceptions.ConnectionError as e:
        # Ошибки соединения
        error_msg = f"Ошибка соединения при загрузке страницы: {str(e)}"
        logger.error(error_msg)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=error_msg
        )

    except requests.exceptions.RequestException as e:
        # Другие сетевые ошибки
        error_msg = f"Сетевая ошибка при загрузке страницы: {str(e)}"
        logger.error(error_msg)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=error_msg
        )

    except Exception as e:
        # Ошибки OpenAI API и другие неожиданные ошибки
        error_msg = f"Ошибка при генерации вопросов: {str(e)}"
        logger.error(error_msg, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_msg
        )


@app.exception_handler(ValidationError)
async def validation_exception_handler(request, exc: ValidationError):
    """
    Обработчик ошибок валидации Pydantic.
    """
    logger.error(f"Ошибка валидации запроса: {exc}")
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": "Validation Error",
            "detail": exc.errors()
        }
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8001,
        reload=True
    )

