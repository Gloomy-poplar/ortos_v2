import re
from typing import List, Optional
from models.product import Product

class FilterService:
    def __init__(self):
        self.brand_keywords = {
            'bauerfeind': ['bauerfeind', 'бауэрфайнд', 'бауэрфаинд'],
            'berkemann': ['berkemann', 'беркеман', 'беркеманн', 'berkeman'],
            'sigvaris': ['sigvaris', 'сигварис'],
            'orlett': ['orlett', 'орлет', 'арлет'],
            'venoteks': ['venoteks', 'венотек'],
            'ortmann': ['ortmann', 'ortman', 'ортманн', 'ортман'],
            'dr. thomas': ['dr. thomas', 'доктор томас', 'доктора томас'],
            'anatomic help': ['anatomic help', 'анатомик хелп'],
            'kinerapy': ['kinerapy', 'кинерапи'],
            'göekken': ['göekken', 'гекен', 'геккен'],
            'орто-кэа': ['орто-кэа', 'ортокэа'],
            'viproactive': ['viproactive', 'випроактив'],
            'bbtape': ['bbtape'],
            'antar': ['antar', 'антар'],
            'орто косметикс': ['орто косметикс', 'ортокосметикс'],
            'футмастер': ['футмастер', 'futmaster'],
            'tonus elast': ['tonus elast', 'тонус эласт'],
            'тривес': ['тривес', 'trives'],
            'intraros': ['intraros', 'интрарос'],
            'trelax': ['trelax', 'трелакс'],
            'footwell': ['footwell', 'футвел'],
            'ipsum': ['ipsum', 'ипсум'],
            'masterheal': ['masterheal', 'мастерхил'],
            'twiki': ['twiki', 'твики'],
            'navimeso': ['navimeso', 'навимесо'],
            'optio': ['optio', 'оптио']
        }
    
    def filter_products(self, question: str, products: List[Product]) -> List[Product]:
        """Основной метод фильтрации товаров"""
        print(f"🔍 Фильтрация товаров по запросу: '{question}'")
        
        question_lower = question.lower()
        filtered = []
        
        # Извлекаем критерии фильтрации
        target_size = self._extract_size(question)
        target_brands = self._extract_brands(question_lower)
        
        for product in products:
            if self._matches_criteria(product, question_lower, target_size, target_brands):
                filtered.append(product)
        
        print(f"✅ После фильтрации: {len(filtered)} товаров")
        return filtered
    
    def _extract_size(self, question: str) -> Optional[str]:
        """Извлекает размер из вопроса"""
        size_match = re.search(r'\b(\d{2})\b', question)
        if size_match:
            size = size_match.group(1)
            print(f"🎯 Ищем размер: {size}")
            return size
        return None
    
    def _extract_brands(self, question_lower: str) -> List[str]:
        """Извлекает бренды из вопроса с улучшенным сопоставлением"""
        brands = []
        
        for brand, keywords in self.brand_keywords.items():
            for keyword in keywords:
                if keyword in question_lower:
                    brands.append(brand)
                    print(f"🎯 Найден бренд: {brand} (по ключу: '{keyword}')")
                    break  # Не проверяем остальные варианты для этого бренда
        
        print(f"📋 Извлеченные бренды: {brands}")
        return brands
    
    def _matches_criteria(self, product: Product, question: str, 
                         target_size: Optional[str], target_brands: List[str]) -> bool:
        """Проверяет соответствие товара критериям"""
        
        # Проверяем размер (если указан в запросе)
        if target_size and not product.has_size(target_size):
            return False
        
        # Проверяем бренд (если указан в запросе) - СТРОГАЯ ПРОВЕРКА
        if target_brands:
            product_brand_match = False
            for target_brand in target_brands:
                if product.matches_brand(target_brand):
                    product_brand_match = True
                    break
            if not product_brand_match:
                return False
        
        # Проверяем тип товара
        if 'стельк' in question and not product.is_insoles():
            return False
        elif 'обув' in question and not product.is_footwear():
            return False
        
        return True
    
    def filter_by_category(self, products: List[Product], category: str) -> List[Product]:
        """Фильтрация по категории"""
        if category == 'footwear':
            return [p for p in products if p.is_footwear()]
        elif category == 'insoles':
            return [p for p in products if p.is_insoles()]
        return products