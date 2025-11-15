<!-- Use this file to provide workspace-specific custom instructions to Copilot.
For more details, visit https://code.visualstudio.com/docs/copilot/copilot-customization#_use-a-githubcopilotinstructionsmd-file -->

# OpenVPN Web Management System

Веб-приложение Django для управления OpenVPN серверами через веб-интерфейс.

## 🎯 Критические требования разработки

### CLEAN CODE (обязательно!)
- ❌ **Файлы НЕ ДОЛЖНЫ превышать 500 строк**
- ❌ **Методы/функции НЕ ДОЛЖНЫ превышать 50 строк**
- ❌ **Классы НЕ ДОЛЖНЫ превышать 300 строк**
- ✅ **Один метод = одна ответственность**
- ✅ **Понятные имена** (без `data`, `info`, `manager`)
- ✅ **Никаких магических чисел** - только константы
- ✅ **DRY** - не повторяйся!
- ✅ **Комментарии объясняют "ПОЧЕМУ", не "ЧТО"**

### SOLID принципы (строго!)
- **S** - Single Responsibility: один класс = одна задача
- **O** - Open/Closed: открыт для расширения, закрыт для изменения
- **L** - Liskov Substitution: наследники заменяют родителей
- **I** - Interface Segregation: узкие интерфейсы лучше широких
- **D** - Dependency Inversion: зависимость от абстракций, не деталей

### CI/CD готовность
- ✅ Код должен проходить `python manage.py check --deploy`
- ✅ Все изменения покрыты тестами
- ✅ Типизация (type hints) везде
- ✅ Docstrings для публичных методов
- ✅ Логирование вместо print()
- ✅ Безопасность: CSRF, XSS, SQL Injection защита

### 🔒 БЕЗОПАСНОСТЬ (критично!)

#### Django Security Checklist
- ✅ **CSRF Protection**: `@csrf_protect` на всех формах, `csrf_token` в templates
- ✅ **XSS Protection**: автоэкранирование в templates, `mark_safe` только после валидации
- ✅ **SQL Injection**: ТОЛЬКО Django ORM, НИКАКИХ raw SQL queries
- ✅ **Clickjacking**: `X-Frame-Options: DENY` в headers
- ✅ **HTTPS**: `SECURE_SSL_REDIRECT = True` в production
- ✅ **HSTS**: `SECURE_HSTS_SECONDS = 31536000` (1 год)
- ✅ **Secure Cookies**: `SESSION_COOKIE_SECURE = True`, `CSRF_COOKIE_SECURE = True`
- ✅ **Content Security Policy**: строгая CSP для защиты от XSS

#### Input Validation
- ✅ **Все пользовательские данные валидируются** через Django Forms/Serializers
- ✅ **Санитизация HTML**: используй `bleach.clean()` для user-generated content
- ✅ **Path Traversal защита**: валидируй файловые пути, используй `os.path.abspath()`
- ✅ **Command Injection защита**: НИКОГДА не передавай user input в shell commands
- ✅ **SSH команды**: параметризация через JSON, валидация на стороне Agent

#### Authentication & Authorization
- ✅ **Strong passwords**: `AUTH_PASSWORD_VALIDATORS` с минимум 8 символов
- ✅ **Rate limiting**: защита от brute-force атак на login
- ✅ **Permission checks**: `@login_required`, `@permission_required` на всех views
- ✅ **User isolation**: каждый пользователь видит только свои серверы
- ✅ **Session security**: `SESSION_COOKIE_HTTPONLY = True`, `SESSION_COOKIE_SAMESITE = 'Strict'`

#### Sensitive Data Protection
- ✅ **SSH ключи**: хранятся зашифрованными в БД (django-cryptography или Fernet)
- ✅ **Пароли**: НИКОГДА в plaintext, используй `make_password()` / `check_password()`
- ✅ **Secrets в .env**: `SECRET_KEY`, DB credentials, API keys
- ✅ **Логирование**: НЕ логируй пароли, токены, приватные ключи
- ✅ **API responses**: НЕ возвращай sensitive data без необходимости

#### File Upload Security
- ✅ **Whitelist расширений**: только `.ovpn`, `.conf`, `.crt`, `.key`
- ✅ **Size limits**: `FILE_UPLOAD_MAX_MEMORY_SIZE = 5MB`
- ✅ **Virus scanning**: интеграция с ClamAV для production
- ✅ **Storage outside MEDIA_ROOT**: конфиги не должны быть публично доступны
- ✅ **Filename sanitization**: удаляй `../`, специальные символы

#### API Security
- ✅ **Authentication**: JWT tokens или Django Session для API
- ✅ **CORS**: строгая настройка `CORS_ALLOWED_ORIGINS`
- ✅ **Rate limiting**: `django-ratelimit` на API endpoints
- ✅ **Input validation**: DRF Serializers с валидацией
- ✅ **Error messages**: НЕ раскрывай внутренние детали в ошибках

#### SSH/Agent Security
- ✅ **SSH key validation**: проверка формата ключей перед сохранением
- ✅ **Command whitelist**: Agent принимает только разрешенные команды
- ✅ **JSON параметризация**: все параметры через структурированный JSON
- ✅ **Timeout limits**: SSH команды с таймаутом (max 10 минут)
- ✅ **Sudo hardening**: минимальные sudo права на серверах

#### Database Security
- ✅ **Prepared statements**: Django ORM автоматически защищает
- ✅ **Least privilege**: БД пользователь с минимальными правами
- ✅ **Encryption at rest**: для sensitive данных (ssh_private_key)
- ✅ **Backups**: регулярные зашифрованные бэкапы БД
- ✅ **Audit logging**: логирование всех изменений критичных данных

#### Production Settings (settings/production.py)
```python
# Security
DEBUG = False
ALLOWED_HOSTS = ['your-domain.com']
SECRET_KEY = env('SECRET_KEY')  # из .env файла

# HTTPS
SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

# Cookies
SESSION_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Strict'
CSRF_COOKIE_SECURE = True
CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SAMESITE = 'Strict'

# Headers
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True
X_FRAME_OPTIONS = 'DENY'

# CSP
CSP_DEFAULT_SRC = ("'self'",)
CSP_SCRIPT_SRC = ("'self'", "'unsafe-inline'")  # минимизировать unsafe-inline
CSP_STYLE_SRC = ("'self'", "'unsafe-inline'")
CSP_IMG_SRC = ("'self'", "data:")
CSP_FONT_SRC = ("'self'",)

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator', 'OPTIONS': {'min_length': 12}},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]
```

### Запрещено (SECURITY VIOLATION!)
- 🚫 **`mark_safe()` без sanitization** - XSS уязвимость!
- 🚫 **`.raw()` SQL queries** - SQL Injection риск!
- 🚫 **User input в `os.system()`** - Command Injection!
- 🚫 **Хранение паролей plaintext** - критичная уязвимость!
- 🚫 **DEBUG=True в production** - раскрытие sensitive данных!
- 🚫 **Отключение CSRF** - открытие для CSRF атак!
- 🚫 **`eval()` / `exec()` с user input** - Remote Code Execution!
- 🚫 **Логирование паролей/токенов** - утечка credentials!

### Запрещено (код-ревью провалится!)
- 🚫 **Хардкод** (IP, порты, пути) - только через constants
- 🚫 **Дублирование кода** - используй наследование/композицию
- 🚫 **God Objects** - монолитные классы на 1000+ строк
- 🚫 **Прямые SQL запросы** - только ORM (защита от SQL Injection)
- 🚫 **Прямые SSH в views** - только через Service Layer
- 🚫 **Try-except без обработки** - логируй ошибки!
- 🚫 **ЛЕНЬ В АРХИТЕКТУРНЫХ РЕШЕНИЯХ** - быстрое неправильное решение тратит больше ресурсов чем медленное правильное!
- 🚫 **User input без валидации** - критичная уязвимость безопасности!

### ⚠️ КРИТИЧНО: Никакой лени в архитектуре!
- ✅ **ВСЕГДА проверяй архитектуру ПЕРЕД реализацией**
- ✅ **Потрать ресурсы на валидацию решения СРАЗУ**
- ✅ **"Быстро и неправильно" ХУЖЕ чем "медленно и правильно"**
- ❌ **НЕ предлагай решения без проверки совместимости**
- ❌ **НЕ экономь на исследовании - это приводит к кратному перерасходу ресурсов**

**Пример плохого подхода:**
- Предложить STunnel для OpenVPN TCP без проверки TCP-over-TCP проблемы
- Потратить часы на отладку заведомо нерабочей схемы
- Итог: потрачено 10x ресурсов вместо экономии

**Правильный подход:**
- Проверить совместимость технологий ПЕРЕД предложением
- Убедиться что решение 100% рабочее
- Только потом приступать к реализации

## 📋 Требования проекта

- Django веб-приложение для управления OpenVPN серверами
- Веб-интерфейс для настройки серверов
- Управление сертификатами через веб-форму
- Мониторинг подключений в реальном времени
- Все параметры настройки вводятся вручную через веб-формы
- Работа с серверами через Agent (автономный агент на удаленных серверах)
- Безопасная передача файлов через веб-сервер

## Progress Tracker
- [x] Verify that the copilot-instructions.md file in the .github directory is created
- [x] Clarify Project Requirements - Django OpenVPN web management system
- [x] Scaffold the Project - Create Django project structure
- [x] Customize the Project - Implement OpenVPN management modules
- [x] Install Required Extensions - Python/Django extensions
- [x] Compile the Project - Install dependencies and run migrations
- [x] Create and Run Task - Setup Django development server
- [x] Launch the Project - Start web application
- [x] Implement SSH Terminal Integration - Real SSH connectivity
- [x] Create Production-Ready SSH Service - SOLID principles
- [x] Fix OpenVPN Installation Issues - Resolved sudo privileges
- [x] Refactor to CLEAN CODE & SOLID - Service Layer architecture
- [x] Ensure Documentation is Complete

## 🏗️ Архитектура (SOLID compliance)

### Текущая архитектура (Agent-first)

```
User → Django Views/API → Service Layer → AgentClient → SSH → Agent (на сервере) → OpenVPN
```

**Service Layer** (следует SOLID):
- **ServerManagementService** (204 строки): install, configure, reinstall, start, stop, restart
- **ClientManagementService** (179 строк): create_client, revoke_client, list_clients, download_config
- **MonitoringService** (163 строки): get_status, disconnect_client, get_stats, is_running

**Agent** (автономный):
- **ovpn_agent.py** (1014 строк): Python скрипт на удаленном сервере
- 8 команд: install, configure, reinstall, list-clients, create-client, get-status, revoke-client, disconnect-client
- Работает локально на сервере, получает команды через SSH

**Конфигурация**:
- `config/constants.py` (42 строки): централизованные константы
- `config/agent_config.py` (55 строк): type-safe конфигурация агента

### Компоненты

- **Frontend**: Django Templates с Bootstrap для адаптивного интерфейса
- **Backend**: Django с моделями для серверов, клиентов, сертификатов
- **Agent Module**: Автономный агент на удаленных серверах
- **Service Layer**: SOLID-compliant сервисы (SRP, DIP, OCP)
- **Real-time**: WebSockets для мониторинга в реальном времени
- **Security**: Django аутентификация и авторизация

### Принципы разработки

1. **Все операции через Agent** - никаких прямых SSH команд в views/API
2. **Service Layer** - единственный интерфейс между views и Agent
3. **Централизованная конфигурация** - `config/constants.py`
4. **Type hints везде** - mypy compliance
5. **Async-first** - сервисы используют asyncio
6. **Mock-friendly** - легко тестировать с моками

### Запрещенные паттерны

❌ **НЕ делай так:**
```python
# В views/API напрямую:
ssh_service.execute_command(server, "openvpn --status")
```

✅ **Делай так:**
```python
# Через Service Layer:
service = MonitoringService(server)
status = await service.get_status()
```

## 📚 Документация

- **CLEAN_CODE_REFACTORING_COMPLETE.md** - полный отчет о рефакторинге
- **ARCHITECTURE.md** - детальная архитектура проекта
- **README.md** - основная документация
- **API_MIGRATION_VERIFICATION.md** - миграция на новую архитектуру
