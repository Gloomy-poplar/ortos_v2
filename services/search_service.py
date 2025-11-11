# -*- coding: utf-8 -*-
import sys
from typing import List, Optional

# Устанавливаем правильное кодирование для консоли Windows
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

from models.product import Product
from services.feed_service import FeedService
from services.filter_service import FilterService


class SearchService:
    def __init__(self, feed_service: FeedService, filter_service: FilterService):
        self.feed_service = feed_service
        self.filter_service = filter_service

    def search_in_salon(self, question: str, salon_name: str, feed_file: str) -> List[Product]:
        """Поиск товаров в указанном салоне"""
        print(f"🔍 Поиск в салоне {salon_name}, файл: {feed_file}")

        # Загружаем фид
        feed_content = self.feed_service.load_feed(feed_file)
        if not feed_content:
            print(f"❌ Не удалось загрузить фид: {feed_file}")
            return []

        # Парсим товары
        products = self.feed_service.parse_feed(feed_content)
        if not products:
            print(f"📦 В салоне {salon_name} нет товаров")
            return []

        # Фильтруем товары по запросу
        filtered_products = self.filter_service.filter_products(
            question, products)
        print(f"🎯 Найдено товаров после фильтрации: {len(filtered_products)}")

        return filtered_products

    def search_across_all_salons(self, question: str) -> List[Product]:
        """Поиск товаров во всех салонах"""
        print(f"🔍 Поиск по всем салонам: '{question}'")
        all_products = []

        for salon_name, feed_file in self.feed_service.salons.items():
            salon_products = self.search_in_salon(
                question, salon_name, feed_file)
            all_products.extend(salon_products)

        print(f"🌐 Всего найдено товаров: {len(all_products)}")
        return all_products

    def get_salon_products_count(self, salon_name: str, feed_file: str) -> int:
        """Получаем общее количество товаров в салоне"""
        feed_content = self.feed_service.load_feed(feed_file)
        if not feed_content:
            return 0

        products = self.feed_service.parse_feed(feed_content)
        return len(products) if products else 0
