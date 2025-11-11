# -*- coding: utf-8 -*-
import time
import sys
from typing import Any, Optional, Tuple

# Устанавливаем правильное кодирование для консоли Windows
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')


class CacheService:
    def __init__(self, timeout: int = 300):
        self.cache = {}
        self.timeout = timeout

    def get(self, key: str) -> Optional[Any]:
        if key in self.cache:
            cache_time, cached_response = self.cache[key]
            if time.time() - cache_time < self.timeout:
                print(f"♻️ Используем кэшированный ответ для: {key}")
                return cached_response
            else:
                # Удаляем просроченный кэш
                del self.cache[key]
        return None

    def set(self, key: str, value: Any) -> None:
        self.cache[key] = (time.time(), value)
        print(f"💾 Сохраняем в кэш: {key}")

    def clear(self) -> None:
        self.cache.clear()
        print("🧹 Очищаем кэш")

    def remove_short_queries(self) -> None:
        """Удаляем кэш для коротких запросов"""
        short_keys = [k for k in self.cache.keys() if any(
            word in k for word in ['еще', 'другие', '?'])]
        for key in short_keys:
            del self.cache[key]
        if short_keys:
            print(f"🗑️ Удаляем кэш для коротких запросов: {len(short_keys)}")
