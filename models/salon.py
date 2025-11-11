# -*- coding: utf-8 -*-
import sys
from dataclasses import dataclass
from typing import Optional

# Устанавливаем правильное кодирование для консоли Windows
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')


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
