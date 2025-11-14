# Архитектура проекта OpenVPN Control

## Принципы проектирования

Проект следует принципам **SOLID**, **Clean Code** и **Clean Architecture**:

### SOLID Principles

1. **Single Responsibility Principle (SRP)**
   - Каждый модуль отвечает за одну функциональность
   - API views разделены по доменам: server, client, monitoring, stats
   - Services изолированы по типам операций

2. **Open/Closed Principle (OCP)**
   - Базовые классы с абстракциями (IServerManager, IClientManager)
   - Расширение функциональности через наследование, не модификацию

3. **Liskov Substitution Principle (LSP)**
   - Все реализации интерфейсов взаимозаменяемы
   - SSH сервисы могут быть заменены мок-объектами в тестах

4. **Interface Segregation Principle (ISP)**
   - Узкие специализированные интерфейсы
   - Клиенты не зависят от неиспользуемых методов

5. **Dependency Inversion Principle (DIP)**
   - Зависимость от абстракций, не конкретных реализаций
   - Инъекция зависимостей через конструкторы

## Структура проекта

```
ovpn_control/
├── ovpn_app/               # Основное приложение
│   ├── api/                # API endpoints (модульная структура)
│   │   ├── __init__.py     # Экспорт всех API views
│   │   ├── base.py         # Базовые классы и интерфейсы
│   │   ├── server_views.py # Управление серверами (~300 строк)
│   │   ├── client_views.py # Управление клиентами (~150 строк)
│   │   ├── monitoring_views.py # Мониторинг (~200 строк)
│   │   ├── stats_views.py  # Статистика (~150 строк)
│   │   └── viewsets.py     # DRF ViewSets (~200 строк)
│   ├── core/               # Ядро приложения
│   │   ├── services/       # Бизнес-логика
│   │   ├── interfaces/     # Абстракции и протоколы
│   │   └── exceptions/     # Кастомные исключения
│   ├── models.py           # Django модели
│   ├── forms.py            # Django формы
│   ├── views.py            # Django views (presentation layer)
│   ├── ssh_service.py      # SSH connectivity
│   ├── vpn_monitor.py      # VPN monitoring service
│   └── tests/              # Unit и integration тесты
│       ├── conftest.py     # Pytest фикстуры
│       ├── test_models.py
│       ├── test_views.py
│       └── test_services.py
├── ovpn_project/           # Настройки Django
├── static/                 # Статические файлы
├── pyproject.toml          # Конфигурация инструментов
├── .flake8                 # Настройки Flake8
├── requirements.txt        # Production зависимости
├── requirements-dev.txt    # Dev зависимости
└── check_code_quality.sh   # Скрипт проверки качества

```

## Слои приложения

### 1. Presentation Layer (views.py, api/)
- Обработка HTTP запросов/ответов
- Валидация входных данных
- Сериализация/десериализация
- **Не содержит бизнес-логику**

### 2. Business Logic Layer (core/services/)
- Бизнес-правила и логика
- Оркестрация операций
- Транзакции
- **Не зависит от фреймворка**

### 3. Data Access Layer (models.py)
- ORM модели Django
- Работа с БД
- Миграции

### 4. Infrastructure Layer (ssh_service.py, vpn_monitor.py)
- Внешние интеграции (SSH, OpenVPN)
- Файловая система
- Сетевые операции

## Code Quality Tools

### Форматирование
- **Black**: автоформатирование кода (line-length=100)
- **isort**: сортировка импортов

### Линтинг
- **Flake8**: проверка стиля кода (PEP 8)
- **MyPy**: статическая проверка типов

### Тестирование
- **pytest**: unit и integration тесты
- **pytest-django**: интеграция с Django
- **pytest-cov**: coverage reports
- **factory-boy**: тестовые фикстуры

## Использование

### Проверка качества кода
```bash
# Запустить все проверки
./check_code_quality.sh

# Форматирование кода
black ovpn_app/ ovpn_project/
isort ovpn_app/ ovpn_project/

# Линтинг
flake8 ovpn_app/ ovpn_project/
mypy ovpn_app/ ovpn_project/

# Тесты
pytest
pytest --cov=ovpn_app --cov-report=html
```

### CI/CD Integration
Добавить в `.github/workflows/ci.yml`:
```yaml
name: CI
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.12'
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install -r requirements-dev.txt
      - name: Run checks
        run: ./check_code_quality.sh
```

## Правила разработки

### Именование
- **Классы**: PascalCase (OpenVPNServer)
- **Функции/методы**: snake_case (install_openvpn)
- **Константы**: UPPER_SNAKE_CASE (MAX_RETRY_COUNT)
- **Private**: префикс _ (_internal_method)

### Docstrings
Используем Google Style:
```python
def function(arg1: str, arg2: int) -> bool:
    """
    Short description of function.
    
    Args:
        arg1: Description of arg1
        arg2: Description of arg2
        
    Returns:
        Description of return value
        
    Raises:
        ValueError: When arg2 is negative
    """
    pass
```

### Type Hints
Всегда используем аннотации типов:
```python
from typing import Optional, List, Dict, Any

def process_data(
    data: List[Dict[str, Any]],
    timeout: Optional[int] = None
) -> Dict[str, Any]:
    ...
```

### Error Handling
```python
# Специфичные исключения
try:
    result = risky_operation()
except SpecificError as e:
    logger.error(f"Operation failed: {e}", exc_info=True)
    raise CustomException("User-friendly message") from e
```

## Метрики качества

### Целевые показатели
- **Test Coverage**: >80%
- **Complexity**: <10 (cyclomatic complexity)
- **Lines per file**: <500
- **Lines per function**: <50
- **Type hints coverage**: >90%

### Инструменты мониторинга
- `pytest --cov` - coverage reports
- `radon cc` - cyclomatic complexity
- `mypy --strict` - type checking
