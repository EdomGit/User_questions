# Модуль для работы с OpenAI API

## Установка и настройка

### 1. Создание виртуального окружения

Виртуальное окружение уже создано в папке `venv`. Если нужно создать заново:

```bash
python -m venv venv
```

### 2. Активация виртуального окружения

**Windows (PowerShell):**
```powershell
.\venv\Scripts\Activate.ps1
```

**Windows (CMD):**
```cmd
venv\Scripts\activate.bat
```

**Linux/Mac:**
```bash
source venv/bin/activate
```

### 3. Установка зависимостей

Зависимости уже установлены. Если нужно переустановить:

```bash
pip install -r requirements.txt
```

### 4. Настройка переменных окружения

Создайте файл `.env` в корне проекта со следующим содержимым:

```
OPENAI_API_KEY=your_api_key_here
OPENAI_BASE_URL=https://api.openai.com/v1  # Опционально, по умолчанию используется стандартный URL
```

Если `OPENAI_BASE_URL` не указан, будет использован стандартный URL OpenAI API.

## Использование

### Запуск тестов

```bash
python test_openai_module.py
```

### Использование модуля

```python
from openai_module import get_questions_from_text

questions = get_questions_from_text("Ваш текст здесь")
print(questions)
```