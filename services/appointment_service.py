# -*- coding: utf-8 -*-
import re
import sys
from datetime import datetime
from typing import List, Dict, Optional

# Устанавливаем правильное кодирование для консоли Windows
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

from services.google_sheets_service import GoogleSheetsService


class AppointmentService:
    def __init__(self):
        self.sheets_service = GoogleSheetsService()

    def process_appointment_request(self, question: str, user_name: str, user_id: str) -> str:
        """Обрабатывает запрос на запись"""
        question_lower = question.lower()

        # Извлекаем дату из вопроса
        target_date = self._extract_date(question)

        if "записаться" in question_lower or "запись" in question_lower:
            return self._handle_booking_request(question, user_name, user_id, target_date)
        elif "мои записи" in question_lower or "мои приемы" in question_lower:
            return self._handle_user_appointments(user_id)
        elif "отменить запись" in question_lower:
            return "❌ Функция отмены записи временно недоступна"
        else:
            return self._handle_availability_check(target_date)

    def _extract_date(self, question: str) -> Optional[str]:
        """Извлекает дату из вопроса"""
        # Паттерны для дат: 24 октября, 24.10, 24.10.2024
        patterns = [
            r'(\d{1,2})\s+(январ[ья]|феврал[ья]|март[а]?|апрел[ья]|ма[йя]|июн[ья]|июл[ья]|август[а]?|сентябр[ья]|октябр[ья]|ноябр[ья]|декабр[ья])',
            r'(\d{1,2})\.(\d{1,2})',
            r'(\d{1,2})\.(\d{1,2})\.(\d{4})'
        ]

        for pattern in patterns:
            match = re.search(pattern, question.lower())
            if match:
                if "январ" in question:
                    month = "01"
                elif "феврал" in question:
                    month = "02"
                elif "март" in question:
                    month = "03"
                elif "апрел" in question:
                    month = "04"
                elif "май" in question or "мая" in question:
                    month = "05"
                elif "июн" in question:
                    month = "06"
                elif "июл" in question:
                    month = "07"
                elif "август" in question:
                    month = "08"
                elif "сентябр" in question:
                    month = "09"
                elif "октябр" in question:
                    month = "10"
                elif "ноябр" in question:
                    month = "11"
                elif "декабр" in question:
                    month = "12"
                else:
                    # Для формата 24.10
                    if len(match.groups()) >= 2:
                        month = match.group(2).zfill(2)
                    else:
                        continue

                day = match.group(1).zfill(2)
                year = datetime.now().year
                return f"{day}.{month}.{year}"

        return None

    def _handle_booking_request(self, question: str, user_name: str, user_id: str, target_date: Optional[str]) -> str:
        """Обрабатывает запрос на бронирование"""
        if target_date:
            # Показываем доступные слоты на конкретную дату
            available_slots = self.sheets_service.get_available_slots(
                target_date)
            if available_slots:
                times = [slot['time'] for slot in available_slots[:5]]
                return f"📅 На {target_date} доступны следующие время:\n" + \
                       "\n".join([f"• {time}" for time in times]) + \
                       f"\n\nДля записи напишите: \"Запишите меня на {target_date} в [время]\""
            else:
                return f"❌ На {target_date} нет свободных записей.\n\n" + \
                       self._format_available_dates()
        else:
            # Показываем ближайшие доступные даты
            return "📅 Хотите записаться на индивидуальные стельки?\n\n" + \
                   self._format_available_dates() + \
                   "\n\nУкажите желаемую дату или выберите из доступных."

    def _handle_availability_check(self, target_date: Optional[str]) -> str:
        """Проверяет доступность дат"""
        if target_date:
            available_slots = self.sheets_service.get_available_slots(
                target_date)
            if available_slots:
                times = [slot['time'] for slot in available_slots[:5]]
                return f"✅ На {target_date} есть свободные записи:\n" + \
                       "\n".join([f"• {time}" for time in times]) + \
                       f"\n\nДля записи напишите: \"Запишите меня на {target_date} в [время]\""
            else:
                return f"❌ На {target_date} нет свободных записей.\n\n" + \
                       self._format_available_dates()
        else:
            return self._format_available_dates()

    def _handle_user_appointments(self, user_id: str) -> str:
        """Показывает записи пользователя"""
        appointments = self.sheets_service.get_user_appointments(user_id)
        if not appointments:
            return "У вас нет активных записей на стельки."

        result = "📋 Ваши записи на стельки:\n\n"
        for app in appointments:
            result += f"📅 {app['date']} в {app['time']}\n"

        return result

    def _format_available_dates(self) -> str:
        """Форматирует доступные даты для ответа"""
        next_dates = self.sheets_service.get_next_available_dates(3)
        if not next_dates:
            return "К сожалению, на ближайшее время нет свободных записей."

        result = "Ближайшие доступные даты:\n"
        for date_info in next_dates:
            result += f"📅 {date_info['date']} ({date_info['day_of_week']}) - {', '.join(date_info['available_times'][:3])}\n"

        return result

    def book_specific_slot(self, date: str, time: str, user_name: str, user_id: str, phone: str = "") -> str:
        """Записывает на конкретный слот с сбором контактов"""
        success = self.sheets_service.book_appointment(
            date, time, user_name, user_id, phone)
        if success:
            response = f"✅ Вы успешно записаны на {date} в {time}!\n\n"
            response += "📍 Адрес: ул. Гикало, 1 (салон ORTOS)\n"
            response += "📞 Телефон для подтверждения: +375 (29) 145-03-03\n\n"

            if not phone:
                response += "📱 Для связи оставьте, пожалуйста, ваш телефон:"
            elif user_name == "Пользователь":
                response += "👤 Как к вам обращаться?"
            else:
                response += "Если не сможете прийти, пожалуйста, отмените запись заранее."

            return response
        else:
            return f"❌ К сожалению, время {time} на {date} уже занято.\n\n" + \
                self._format_available_dates()

    def cancel_appointment(self, phone: str) -> str:
        """Отменяет записи по номеру телефона"""
        cancelled_appointments = self.sheets_service.cancel_appointment_by_phone(
            phone)

        if not cancelled_appointments:
            return "❌ Активных записей с этим номером телефона не найдено."

        result = "✅ Отменены следующие записи:\n\n"
        for appointment in cancelled_appointments:
            result += f"📅 {appointment['date']} в {appointment['time']} - {appointment['user_name']}\n"

        result += "\n💡 Запись успешно отменена."
        return result

    def get_user_appointments_by_phone(self, phone: str) -> str:
        """Показывает активные записи по номеру телефона"""
        appointments = self.sheets_service.get_user_appointments_by_phone(
            phone)

        if not appointments:
            return "📭 Активных записей с этим номером телефона не найдено."

        result = "📋 Ваши активные записи:\n\n"
        for appointment in appointments:
            result += f"📅 {appointment['date']} в {appointment['time']}\n"

        result += f"\n💡 Для отмены записи напишите: \"Отменить запись {phone}\""
        return result
