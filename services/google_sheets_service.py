# -*- coding: utf-8 -*-
import gspread
import re
import sys
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta
from typing import List, Dict, Optional

# Устанавливаем правильное кодирование для консоли Windows
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

from config import Config


class GoogleSheetsService:

    def __init__(self):
        self.scope = [
            "https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/drive"
        ]
        self._init_sheets_client()

    def _init_sheets_client(self):
        """Initialize Google Sheets client"""
        try:
            # Получаем учетные данные из конфига
            credentials_info = Config.get_google_credentials()

            # Создаем credentials из JSON данных
            self.creds = Credentials.from_service_account_info(
                credentials_info, scopes=self.scope)

            self.client = gspread.authorize(self.creds)
            self.sheet = self.client.open(Config.GOOGLE_SHEET_NAME).sheet1

            print("✅ Google Sheets service initialized successfully")

        except Exception as e:
            print(f"❌ Ошибка инициализации Google Sheets: {e}")
            # Создаем заглушки для продолжения работы
            self.creds = None
            self.client = None
            self.sheet = None

    def get_available_slots(self, target_date: str = None) -> List[Dict]:
        """Получаем доступные слоты на дату"""
        try:
            # Проверяем инициализацию
            if not self.sheet:
                print("❌ Google Sheets не инициализирован")
                return []

            records = self.sheet.get_all_records()
            available_slots = []

            # Если дата не указана, берем ближайшие 7 дней
            if not target_date:
                start_date = datetime.now().date()
                dates_to_check = [start_date +
                                  timedelta(days=i) for i in range(7)]
            else:
                dates_to_check = [datetime.strptime(
                    target_date, "%d.%m.%Y").date()]

            # Все возможные временные слоты
            all_slots = [
                "09:00", "10:00", "11:00", "12:00", "13:00", "14:00",
                "15:00", "16:00", "17:00", "18:00"
            ]

            for date in dates_to_check:
                date_str = date.strftime("%d.%m.%Y")
                # Получаем занятые слоты на эту дату
                booked_slots = [
                    record['time'] for record in records
                    if record.get('date') == date_str and record.get('status') == 'booked'
                ]

                # Формируем доступные слоты
                for slot in all_slots:
                    if slot not in booked_slots:
                        available_slots.append({
                            'date': date_str,
                            'time': slot,
                            'datetime': datetime.strptime(f"{date_str} {slot}", "%d.%m.%Y %H:%M")
                        })

            # Сортируем по дате и времени
            available_slots.sort(key=lambda x: x['datetime'])
            return available_slots[:15]  # Ограничиваем количество

        except Exception as e:
            print(f"❌ Ошибка получения слотов: {e}")
            return []

    def book_appointment(self, date: str, time: str, user_name: str, user_id: str, phone: str = "") -> bool:
        """Записываем клиента на прием"""
        try:
            if not self.sheet:
                print("❌ Google Sheets не инициализирован")
                return False

            # Получаем текущее время в Минске (UTC+3)
            utc_now = datetime.utcnow()
            minsk_time = utc_now + timedelta(hours=3)
            created_at = minsk_time.strftime("%d.%m.%Y %H:%M")

            # Добавляем запись
            self.sheet.append_row([
                date, time, user_name, user_id, phone, 'booked', created_at
            ])

            print(
                f"✅ Запись создана: {date} {time} для {user_name} ({phone}) в {created_at}")
            return True

        except Exception as e:
            print(f"❌ Ошибка записи: {e}")
            return False

    def get_next_available_dates(self, count: int = 3) -> List[Dict]:
        """Получаем ближайшие доступные даты со свободными слотами"""
        available_slots = self.get_available_slots()

        # Группируем по датам
        dates = {}
        for slot in available_slots:
            date = slot['date']
            if date not in dates:
                dates[date] = []
            dates[date].append(slot['time'])

        # Форматируем результат
        result = []
        for date, times in list(dates.items())[:count]:
            result.append({
                'date': date,
                'available_times': times[:3],  # Первые 3 времени
                'day_of_week': self._get_day_of_week(date)
            })

        return result

    def _get_day_of_week(self, date_str: str) -> str:
        """Получаем день недели"""
        days = ["понедельник", "вторник", "среда",
                "четверг", "пятница", "суббота", "воскресенье"]
        date_obj = datetime.strptime(date_str, "%d.%m.%Y")
        return days[date_obj.weekday()]

    def get_user_appointments(self, user_id: str) -> List[Dict]:
        """Получаем записи пользователя"""
        try:
            if not self.sheet:
                return []

            records = self.sheet.get_all_records()
            user_records = [
                record for record in records
                if record.get('user_id') == user_id and record.get('status') == 'booked'
            ]
            return user_records
        except Exception as e:
            print(f"❌ Ошибка получения записей: {e}")
            return []

    def update_appointment_with_contacts(self, date: str, time: str, user_id: str, user_name: str, phone: str) -> bool:
        """Обновляет запись с контактными данными"""
        try:
            if not self.sheet:
                return False

            # Получаем все данные из таблицы
            all_data = self.sheet.get_all_values()

            # Ищем запись для обновления (начинаем с индекса 1, пропуская заголовок)
            for i, row in enumerate(all_data[1:], start=2):
                if len(row) >= 5:  # Проверяем что в строке достаточно данных
                    record_date = row[0] if len(row) > 0 else ""
                    record_time = row[1] if len(row) > 1 else ""
                    record_user_id = row[3] if len(row) > 3 else ""

                    if (record_date == date and
                        record_time == time and
                            record_user_id == user_id):

                        print(
                            f"🔍 Найдена запись для обновления: строка {i}, {date} {time}")

                        # Обновляем имя и телефон
                        if len(row) > 2:
                            # user_name колонка (индекс 3)
                            self.sheet.update_cell(i, 3, user_name)
                        if len(row) > 4:
                            # phone колонка (индекс 5)
                            self.sheet.update_cell(i, 5, phone)

                        print(f"✅ Контакты обновлены: {user_name}, {phone}")
                        return True

            print(f"❌ Запись не найдена: {date} {time} для user_id {user_id}")
            return False

        except Exception as e:
            print(f"❌ Ошибка обновления контактов: {e}")
            return False

    def cancel_appointment_by_phone(self, phone: str) -> List[Dict]:
        """Отменяет записи по номеру телефона"""
        try:
            if not self.sheet:
                return []

            # Получаем все данные как есть (без преобразования в records)
            all_data = self.sheet.get_all_values()
            cancelled_appointments = []

            # Нормализуем телефон для сравнения
            normalized_phone = self._normalize_phone(phone)
            print(
                f"🔍 Ищем записи для телефона: '{phone}' (нормализован: '{normalized_phone}')")
            print(f"📊 Всего строк в таблице: {len(all_data)}")

            # Пропускаем заголовок (первая строка)
            for i, row in enumerate(all_data[1:], start=2):
                if len(row) >= 5:  # Проверяем что в строке достаточно данных
                    record_date = row[0] if len(row) > 0 else ""
                    record_time = row[1] if len(row) > 1 else ""
                    record_user_name = row[2] if len(row) > 2 else ""
                    record_user_id = row[3] if len(row) > 3 else ""
                    record_phone = row[4] if len(row) > 4 else ""
                    record_status = row[5] if len(row) > 5 else ""

                    if record_phone:
                        normalized_record_phone = self._normalize_phone(
                            record_phone)
                        print(
                            f"🔍 Строка {i}: '{record_phone}' -> '{normalized_record_phone}', статус: '{record_status}'")

                        if (normalized_record_phone == normalized_phone and
                                record_status == 'booked'):

                            # Обновляем статус на 'cancelled'
                            self.sheet.update_cell(i, 6, 'cancelled')

                            cancelled_appointments.append({
                                'date': record_date,
                                'time': record_time,
                                'user_name': record_user_name
                            })

                            print(
                                f"✅ Отменена запись: {record_date} {record_time} для {record_user_name}")

            print(
                f"📊 Найдено отмененных записей: {len(cancelled_appointments)}")
            return cancelled_appointments

        except Exception as e:
            print(f"❌ Ошибка отмены записи: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _normalize_phone(self, phone: str) -> str:
        """Нормализует телефон для сравнения"""
        if not phone:
            return ""

        # Убираем все нецифровые символы
        digits = re.sub(r'\D', '', phone)

        # Если номер начинается с 375 и имеет 12 цифр, оставляем как есть
        if digits.startswith('375') and len(digits) == 12:
            return digits
        # Если номер начинается с 80 и имеет 11 цифр, преобразуем в 375
        elif digits.startswith('80') and len(digits) == 11:
            return '375' + digits[2:]
        # Если номер имеет 9 цифр, добавляем 375
        elif len(digits) == 9:
            return '375' + digits
        else:
            return digits

    def get_user_appointments_by_phone(self, phone: str) -> List[Dict]:
        """Получает активные записи по номеру телефона"""
        try:
            if not self.sheet:
                return []

            all_data = self.sheet.get_all_values()
            user_appointments = []

            normalized_phone = self._normalize_phone(phone)
            print(
                f"🔍 Ищем активные записи для телефона: '{phone}' (нормализован: '{normalized_phone}')")

            for i, row in enumerate(all_data[1:], start=2):
                if len(row) >= 6:
                    record_phone = row[4] if len(row) > 4 else ""
                    record_status = row[5] if len(row) > 5 else ""

                    if record_phone:
                        normalized_record_phone = self._normalize_phone(
                            record_phone)

                        if (normalized_record_phone == normalized_phone and
                                record_status == 'booked'):

                            user_appointments.append({
                                'date': row[0] if len(row) > 0 else "",
                                'time': row[1] if len(row) > 1 else "",
                                'user_name': row[2] if len(row) > 2 else "",
                                'user_id': row[3] if len(row) > 3 else ""
                            })

            print(f"📊 Найдено активных записей: {len(user_appointments)}")
            return user_appointments

        except Exception as e:
            print(f"❌ Ошибка получения записей: {e}")
            import traceback
            traceback.print_exc()
            return []

    def get_all_appointments(self) -> List[Dict]:
        """Получает все записи для отладки"""
        try:
            if not self.sheet:
                return []

            records = self.sheet.get_all_records()
            all_appointments = []

            for record in records:
                all_appointments.append({
                    'date': record.get('date'),
                    'time': record.get('time'),
                    'user_name': record.get('user_name'),
                    'phone': record.get('phone'),
                    'status': record.get('status')
                })

            return all_appointments

        except Exception as e:
            print(f"❌ Ошибка получения всех записей: {e}")
            return []
