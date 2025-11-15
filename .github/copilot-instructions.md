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
- ✅ Код должен проходить `python manage.py check`
- ✅ Все изменения покрыты тестами
- ✅ Типизация (type hints) везде
- ✅ Docstrings для публичных методов
- ✅ Логирование вместо print()

### Запрещено (код-ревью провалится!)
- 🚫 **Хардкод** (IP, порты, пути) - только через constants
- 🚫 **Дублирование кода** - используй наследование/композицию
- 🚫 **God Objects** - монолитные классы на 1000+ строк
- 🚫 **Прямые SQL запросы** - только ORM
- 🚫 **Прямые SSH в views** - только через Service Layer
- 🚫 **Try-except без обработки** - логируй ошибки!

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
