from dataclasses import dataclass
from typing import Optional

@dataclass
class Salon:
    name: str
    feed_file: str
    display_name: Optional[str] = None
    
    def __post_init__(self):
        if self.display_name is None:
            self.display_name = self.name.capitalize()
    
    def get_feed_path(self, base_dir: str) -> str:
        return f"{base_dir}/data/feeds/{self.feed_file}"