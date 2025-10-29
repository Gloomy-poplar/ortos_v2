from dataclasses import dataclass
from typing import Dict, Optional

@dataclass
class Product:
    id: str
    name: str
    price: str
    url: str
    quantity: str
    category_id: str
    category_name: Optional[str] = None
    params: Dict = None
    
    def __post_init__(self):
        if self.params is None:
            self.params = {}
    
    def get_size(self) -> str:
        return self.params.get('Размер', '')
    
    def get_brand(self) -> str:
        return self.params.get('Бренд', '')
    
    def has_size(self, target_size: str) -> bool:
        product_size = self.get_size()
        # Проверяем точное совпадение размера (40 в "40", "40 ⅔", "36-40" и т.д.)
        if not product_size:
            return False
        return target_size in product_size.split()
    
    def matches_brand(self, brand_keyword: str) -> bool:
        product_text = f"{self.name} {self.get_brand()}".lower()
        return brand_keyword.lower() in product_text
    
    def is_footwear(self) -> bool:
        return 'обув' in self.category_name.lower() if self.category_name else False
    
    def is_insoles(self) -> bool:
        return 'стельк' in self.name.lower() or 'стельк' in (self.category_name.lower() if self.category_name else '')