# -*- coding: utf-8 -*-
"""
Запуск теста 30 вопросов с сохранением вывода в UTF-8 файл
"""
from test_30_questions import main
import sys
import io
import os

if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

# Перенаправляем вывод в файл
output_file = "d:\\ortos-bot\\test_results_30.txt"
output_stream = io.open(output_file, 'w', encoding='utf-8', buffering=1)


class TeeOutput:
    def __init__(self, *streams):
        self.streams = streams

    def write(self, data):
        for stream in self.streams:
            stream.write(data)
            stream.flush()

    def flush(self):
        for stream in self.streams:
            stream.flush()


# Перенаправляем stdout и stderr
sys.stdout = TeeOutput(sys.stdout, output_stream)
sys.stderr = TeeOutput(sys.stderr, output_stream)

# Запускаем основной скрипт
sys.path.insert(0, 'd:\\ortos-bot')


try:
    main()
except Exception as e:
    print(f"\n❌ ОШИБКА: {str(e)}")
    import traceback
    traceback.print_exc()
finally:
    output_stream.close()
    print(f"\n✅ Результаты сохранены в {output_file}")
