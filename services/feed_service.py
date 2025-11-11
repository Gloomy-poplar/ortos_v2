# -*- coding: utf-8 -*-
import xml.etree.ElementTree as ET
import re
import sys
from typing import List, Optional, Dict, Tuple

# Устанавливаем правильное кодирование для консоли Windows
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

from models.product import Product
from config import Config


class FeedService:
    def __init__(self):
        self.salons = Config.SALONS
        self.feeds_dir = Config.FEEDS_DIR

    def detect_salon(self, question: str) -> Tuple[Optional[str], Optional[str]]:
        """Определяем салон из вопроса"""
        question_lower = question.lower()
        for salon_name, feed_file in self.salons.items():
            if salon_name in question_lower:
                return salon_name, feed_file
        return None, None

    def load_feed(self, salon_file: str) -> Optional[str]:
        """Загружаем фид салона"""
        try:
            feed_path = f"{self.feeds_dir}/{salon_file}"
            print(f"📁 Загружаем фид: {feed_path}")

            with open(feed_path, 'r', encoding='utf-8') as f:
                content = f.read()
                print(f"✅ Фид загружен, размер: {len(content)} символов")
                return content
        except Exception as e:
            print(f"❌ Ошибка загрузки фида {salon_file}: {e}")
            return None

    def parse_feed(self, feed_content: str) -> List[Product]:
        """Парсим XML фид и извлекаем структурированные данные"""
        try:
            print("🔍 Начинаем парсинг фида...")

            # Пробуем распарсить как XML
            try:
                root = ET.fromstring(feed_content)
            except ET.ParseError as e:
                print(f"❌ Ошибка парсинга XML: {e}")
                return []

            products = []

            # Парсим категории
            categories = self._parse_categories(root)

            # Парсим товары
            offers = root.findall('.//offer')
            print(f"📦 Найдено offer'ов: {len(offers)}")

            for offer in offers:
                product = self._parse_offer(offer, categories)
                if product:
                    products.append(product)

            print(f"✅ Успешно распаршено товаров: {len(products)}")
            return products

        except Exception as e:
            print(f"❌ Критическая ошибка парсинга фида: {e}")
            return []

    def _parse_categories(self, root: ET.Element) -> Dict[str, str]:
        """Парсим категории из XML"""
        categories = {}
        for category in root.findall('.//category'):
            cat_id = category.get('id')
            cat_name = category.text
            if cat_id and cat_name:
                categories[cat_id] = cat_name
        return categories

    def _parse_offer(self, offer: ET.Element, categories: Dict[str, str]) -> Optional[Product]:
        """Парсим один товар"""
        try:
            # Проверяем доступность
            available = offer.get('available')
            if available != 'true':
                return None

            product = Product(
                id=offer.get('id', ''),
                name=self._get_text(offer, 'name'),
                price=self._get_text(offer, 'price'),
                url=self._get_text(offer, 'url'),
                quantity=self._get_text(offer, 'step-quantity', '0'),
                category_id=self._get_text(offer, 'categoryId'),
                params=self._parse_params(offer)
            )

            # Добавляем информацию о категории
            if product.category_id in categories:
                product.category_name = categories[product.category_id]

            return product

        except Exception as e:
            print(f"❌ Ошибка парсинга товара: {e}")
            return None

    def _get_text(self, element: ET.Element, tag_name: str, default: str = "") -> str:
        """Безопасное получение текста из тега"""
        elem = element.find(tag_name)
        return elem.text if elem is not None else default

    def _parse_params(self, offer: ET.Element) -> Dict[str, str]:
        """Парсим параметры товара"""
        params = {}
        for param in offer.findall('param'):
            param_name = param.get('name')
            param_value = param.text
            if param_name and param_value:
                params[param_name] = param_value
        return params
