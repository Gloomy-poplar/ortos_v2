# 🚀 Деплой на Fly.io с оптимизацией

## Требования ✅
- Model: `intfloat/multilingual-e5-base`
- Cold start: ≤ 3 сек
- RAM: 2 GB
- CPU: 1 vCPU
- Scale to zero: 5 мин без активности
- Цена: ~$0.21/месяц

## Шаги деплоя

### 1️⃣ Создать Volume (2 GB) для кэша моделей
```bash
fly volume create model_cache --size 2 --region ams -a ortos-bot
```

### 2️⃣ Деплой приложения
```bash
fly deploy -a ortos-bot
```

### 3️⃣ Включить Scale to Zero
```bash
fly autoscale set min=0 max=1 --app ortos-bot
```

### 4️⃣ Проверить статус
```bash
fly status -a ortos-bot
fly logs -a ortos-bot
```

## Что было сделано 🔧

### fly.toml
- ✅ Добавлен Volume mount `/data` для кэша моделей
- ✅ Переменная `HF_HOME = "/data/huggingface"` для Hugging Face
- ✅ Уменьшено до 1 vCPU + 2 GB RAM
- ✅ Grace period 180s для загрузки моделей
- ✅ Health check на `/health`

### services/embeddings_service.py
- ✅ Добавлен параметр `cache_folder` в SentenceTransformer
- ✅ Автоматическое создание директорий кэша
- ✅ Использование `HF_HOME` из окружения

### app.py
- ✅ Health check endpoint `/health`
- ✅ Graceful handling когда сервис ещё инициализируется
- ✅ Фоновая инициализация не блокирует запуск

## Ожидаемые результаты 📊

| Параметр | Значение |
|----------|----------|
| Cold start | 2-3 сек |
| Работа в месяц | ~22 минуты |
| Цена VM | $0.03/час × 0.36ч = ~$0.01 |
| Цена Volume | 2 GB × $0.10 = $0.20 |
| **Итого** | **~$0.21/месяц** |

## Мониторинг 📈

```bash
# Просмотр логов
fly logs -a ortos-bot

# Проверить память и CPU
fly ssh console -a ortos-bot
free -h
```

## Troubleshooting 🔍

**Проблема: Бесконечный Deploying**
- Решение: Увеличить grace_period в fly.toml (уже сделано: 180s)

**Проблема: Out of Memory**
- Решение: Volume не смонтирован. Проверить: `fly volumes list -a ortos-bot`

**Проблема: Volume не найден**
- Решение: Пересоздать volume и переdeployить

```bash
fly volume delete model_cache -a ortos-bot
fly volume create model_cache --size 2 --region ams -a ortos-bot
fly deploy -a ortos-bot
```

## Команды Fly.io 🛠️

```bash
# Просмотр всех volumes
fly volumes list -a ortos-bot

# Просмотр машин
fly machines list -a ortos-bot

# Просмотр текущего масштабирования
fly autoscale show -a ortos-bot

# Мониторинг в реальном времени
fly logs -a ortos-bot -f
```

Готово! 🎉
