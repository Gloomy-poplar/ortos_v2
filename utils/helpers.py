import re
from typing import Optional, List

def extract_size_from_question(question: str) -> Optional[str]:
    """Извлекает размер из вопроса"""
    size_match = re.search(r'\b(\d{2})\b', question.lower())
    return size_match.group(1) if size_match else None

def extract_brand_from_question(question: str) -> List[str]:
    """Извлекает бренды из вопроса"""
    question_lower = question.lower()
    brands = []
    
    brand_keywords = {
        'ortmann': ['ortmann', 'ортман'],
        'berkemann': ['berkemann', 'беркеман'],
        'ortoped': ['ortoped', 'ортопед']
    }
    
    for brand, keywords in brand_keywords.items():
        if any(keyword in question_lower for keyword in keywords):
            brands.append(brand)
    
    return brands

def should_skip_cache(question: str) -> bool:
    """Определяет, нужно ли пропустить кэш для вопроса"""
    skip_words = ['еще', 'другие', 'покажи еще', 'что еще', '?', 'а']
    return any(word in question.lower() for word in skip_words)

def format_products_for_prompt(products: List, max_products: int = 15) -> str:
    """Форматирует товары для промпта"""
    if not products:
        return "Товары не найдены"
    
    products_text = ""
    for product in products[:max_products]:
        size = getattr(product, 'get_size', lambda: '')() if hasattr(product, 'get_size') else ''
        price = getattr(product, 'price', '')
        url = getattr(product, 'url', '')
        name = getattr(product, 'name', '')
        
        products_text += f"{name} | {price}р | {size} | {url}\n"
    
    return products_text