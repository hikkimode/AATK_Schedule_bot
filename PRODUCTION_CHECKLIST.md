# Production-Ready Чек-лист

## ✅ Data Integrity & Validation

- [x] **Pydantic Schema** — валидация Excel через `schemas/lesson.py`
- [x] **Автоматическая очистка** строк от пробелов и nan
- [x] **Типизированные поля** — str | None для nullable полей
- [ ] Добавить unique constraint в БД: `(group_name, day, lesson_number)`

```sql
-- Выполнить при миграции БД
ALTER TABLE schedule ADD CONSTRAINT unique_lesson 
UNIQUE (group_name, day, lesson_number);
```

## ✅ Database Layer

- [x] **Repository Pattern** — `BulkImportService`, `ResetService`
- [x] **Batch Insert** — пакеты по 100 записей
- [x] **Atomic Transactions** — commit/rollback
- [x] **UPSERT** — PostgreSQL ON CONFLICT DO UPDATE
- [ ] Добавить индексы:

```sql
CREATE INDEX idx_schedule_group_day ON schedule(group_name, day);
CREATE INDEX idx_schedule_is_change ON schedule(is_change) WHERE is_change = true;
```

## ✅ Error Handling & Logging

- [x] **Custom Exceptions** — `ExcelParseError`, `DatabaseIntegrityError`
- [x] **Loguru** — структурированные логи с ротацией
- [x] **User-friendly errors** — "Строка 45, колонка B" вместо трейсбэка
- [x] **Admin notifications** — отправка ошибок админам
- [ ] Настроить мониторинг (Sentry)

## ✅ Performance

- [x] **Оптимизированный сброс** — DELETE + INSERT SELECT
- [x] **Batch processing** — 300 записей за 1-2 запроса
- [x] **Lazy loading** — scalars() вместо all()

| Операция | Было | Стало |
|----------|------|-------|
| Импорт 300 записей | 300+ запросов | 2-3 запроса |
| Сброс расписания | N запросов | 2 SQL запроса |
| Ошибка Excel | "ValueError" | "Строка 45, поле 'teacher'" |

## 🚀 Перед деплоем

### 1. База данных
```bash
# Создать миграцию для base_schedule
# Убедиться что constraints настроены
# Проверить индексы
```

### 2. Окружение
```bash
# .env файл
DATABASE_URL=postgresql+asyncpg://user:pass@host/db
BOT_TOKEN=...
TEACHER_IDS=123456,789012
SUPERADMIN_IDS=123456
```

### 3. Логи
```bash
mkdir -p logs
chmod 755 logs
```

### 4. Зависимости
```bash
pip install loguru pydantic
```

### 5. Тестирование
- [ ] Загрузить первичный Excel (323 записи)
- [ ] Проверить заполнение base_schedule
- [ ] Загрузить изменения
- [ ] Нажать "Сбросить" — проверить что восстановлено 323 записи
- [ ] Проверить логи в logs/

## 📊 Мониторинг (опционально)

Добавить в `main.py`:
```python
from sentry_sdk import init as sentry_init

sentry_init(
    dsn="your-sentry-dsn",
    traces_sample_rate=0.1,
)
```

## 🔒 Безопасность

- [ ] Проверить что только teacher/superadmin имеют доступ к импорту
- [ ] Включить rate limiting на импорт
- [ ] Проверить SQL injection protection (SQLAlchemy ORM ✅)

## 📈 Метрики

Добавить в `ImportReport`:
- Время выполнения импорта
- Количество batch-операций
- Размер данных в MB
