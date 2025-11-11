# -*- coding: utf-8 -*-
import time
import sys
from typing import Dict, Optional, List, Any

# Устанавливаем правильное кодирование для консоли Windows
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

from models.product import Product


class ContextService:
    def __init__(self, timeout: int = 300):  # 5 минут
        self.user_contexts = {}
        self.timeout = timeout

    def get_user_context(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Получаем контекст пользователя"""
        if user_id in self.user_contexts:
            context = self.user_contexts[user_id]
            # Проверяем не устарел ли контекст
            if time.time() - context.get('timestamp', 0) < self.timeout:
                return context
            else:
                del self.user_contexts[user_id]
                print(f"🗑️ Контекст для {user_id} устарел")
        return None

    def set_search_context(self, user_id: str, salon_name: str, original_question: str,
                           all_products: List[Product], shown_products: List[Product]):
        """Сохраняем контекст поиска"""
        self.user_contexts[user_id] = {
            'type': 'search',
            'salon_name': salon_name,
            'original_question': original_question,
            'all_products': all_products,
            'shown_products': shown_products,
            'timestamp': time.time()
        }
        print(
            f"💾 Сохраняем контекст поиска для {user_id}: {salon_name}, показано {len(shown_products)} из {len(all_products)}")

    def get_more_products(self, user_id: str, count: int = 5) -> Optional[List[Product]]:
        """Получаем следующие товары из контекста"""
        context = self.get_user_context(user_id)
        if not context or context['type'] != 'search':
            return None

        shown_ids = {p.id for p in context['shown_products']}
        all_products = context['all_products']

        # Ищем еще не показанные товары
        more_products = []
        for product in all_products:
            if product.id not in shown_ids:
                more_products.append(product)
            if len(more_products) >= count:
                break

        if more_products:
            # Обновляем контекст
            context['shown_products'].extend(more_products)
            context['timestamp'] = time.time()
            print(f"📦 Нашли еще {len(more_products)} товаров для {user_id}")

        return more_products

    def clear_user_context(self, user_id: str):
        """Очищаем контекст пользователя"""
        if user_id in self.user_contexts:
            del self.user_contexts[user_id]
            print(f"🧹 Очищаем контекст для {user_id}")

    def get_context_info(self, user_id: str) -> str:
        """Информация о текущем контексте (для отладки)"""
        context = self.get_user_context(user_id)
        if not context:
            return "Контекст отсутствует"

        if context['type'] == 'search':
            return f"Поиск в {context['salon_name']}, показано {len(context['shown_products'])} из {len(context['all_products'])}"

        return f"Контекст типа: {context['type']}"
