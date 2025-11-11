# -*- coding: utf-8 -*-
import re
import os
import sys
import threading
from datetime import datetime
from typing import List, Optional, Dict, Any, Tuple

# Устанавливаем правильное кодирование для консоли Windows
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

from groq import Groq
from models.product import Product
from config import Config
from services.feed_service import FeedService
from services.embeddings_service import EmbeddingsService
from services.cache_service import CacheService
from services.context_service import ContextService
from services.filter_service import FilterService
from services.search_service import SearchService
from services.prompt_service import PromptService
from services.consultation_service import ConsultationService
from services.appointment_service import AppointmentService


class BotService:
    def __init__(self):
        self.client = Groq(api_key=Config.GROQ_API_KEY)
        self.feed_service = FeedService()
        self.cache_service = CacheService(Config.CACHE_TIMEOUT)
        self.context_service = ContextService(Config.CACHE_TIMEOUT)
        self.filter_service = FilterService()
        self.search_service = SearchService(
            self.feed_service, self.filter_service)
        self.prompt_service = PromptService()
        self.consultation_service = ConsultationService()
        self.appointment_service = AppointmentService()
        self.quick_answers = Config.QUICK_ANSWERS
        self.user_sessions = {}  # Для хранения временных данных пользователей



    def process_question(self, question: str, user_id: str = "default") -> str:
        """Основной метод обработки вопроса"""
        print(f"🎯 Вопрос от {user_id}: {question}")
        question_clean = question.lower().strip()

        # 1. Приветствия
        greeting_response = self._handle_greeting(question)
        if greeting_response:
            return greeting_response

        # 2. Сессии сбора данных
        session_result = self._handle_user_session(question, user_id)
        if session_result:
            return session_result

        # 3. Короткие запросы ("еще" и т.д.)
        if question_clean in ['еще', 'другие', 'покажи еще', 'что еще', '?']:
            print("🔄 Обрабатываем запрос 'еще'")
            return self._handle_more_request(user_id)

        # 4. Кэш
        cache_key = f"bot:{user_id}:{question_clean}"
        cached_response = self.cache_service.get(cache_key)
        if cached_response:
            return cached_response

        # 5. Поиск по салонам (ПОВЫШАЕМ ПРИОРИТЕТ!)
        salon_name, feed_file = self.feed_service.detect_salon(question)
        if salon_name and feed_file:
            print(f"🏪 Найден салон {salon_name}, ищем товары...")
            result = self._search_in_salon(
                question, salon_name, feed_file, user_id)
            self.cache_service.set(cache_key, result)
            return result

        # 6. Быстрые ответы (ПОНИЖАЕМ ПРИОРИТЕТ - после поиска товаров)
        quick_answer = self._get_quick_answer(question_clean)
        if quick_answer:
            print(f"🎯 Используем быстрый ответ для: {question_clean}")
            return quick_answer

        # 7. Запросы на запись
        appointment_result = self._handle_appointment_requests(
            question, question_clean, user_id)
        if appointment_result:
            self.cache_service.set(cache_key, appointment_result)
            return appointment_result

        # 8. Консультации (RAG)
        result = self.consultation_service.get_consultation_response(
            question, self.client, self.data)
        self.cache_service.set(cache_key, result)
        return result

        # 9. Общая консультация
        result = self._get_general_consultation(question)
        self.cache_service.set(cache_key, result)
        return result

    def _handle_user_session(self, question: str, user_id: str) -> Optional[str]:
        """Обрабатывает сбор дополнительных данных пользователя"""
        if user_id not in self.user_sessions:
            return None

        session = self.user_sessions[user_id]

        # Обрабатываем отмену записи
        if session.get('awaiting_cancel_phone'):
            phone = self._extract_phone(question)
            if phone:
                del self.user_sessions[user_id]
                return self.appointment_service.cancel_appointment(phone)
            else:
                return "📱 Пожалуйста, введите корректный номер телефона (например: +375291234567)"

        # Обрабатываем просмотр записей
        if session.get('awaiting_view_phone'):
            phone = self._extract_phone(question)
            if phone:
                del self.user_sessions[user_id]
                return self.appointment_service.get_user_appointments_by_phone(phone)
            else:
                return "📱 Пожалуйста, введите корректный номер телефона (например: +375291234567)"

        # Обрабатываем телефон для записи
        if session.get('awaiting_phone'):
            phone = self._extract_phone(question)
            if phone:
                session['phone'] = phone
                session['awaiting_phone'] = False
                session['awaiting_name'] = True
                return "📞 Телефон сохранен! 👤 Как к вам обращаться?"
            else:
                return "📱 Пожалуйста, введите корректный номер телефона (например: +375291234567 или 291234567)"

        # Обрабатываем имя
        if session.get('awaiting_name'):
            name = question.strip()
            if len(name) > 1:
                session['name'] = name
                # Завершаем запись с собранными данными
                result = self._complete_booking(user_id)
                del self.user_sessions[user_id]  # Очищаем сессию
                return result
            else:
                return "👤 Пожалуйста, введите ваше имя"

        return None

    def _extract_phone(self, text: str) -> Optional[str]:
        """Извлекает телефон из текста"""
        # Паттерны для телефонов
        patterns = [
            r'(\+375\s?\(?\d{2}\)?\s?\d{3}[\s-]?\d{2}[\s-]?\d{2})',
            r'(375\s?\(?\d{2}\)?\s?\d{3}[\s-]?\d{2}[\s-]?\d{2})',
            r'(8\s?\(?0?\d{2}\)?\s?\d{3}[\s-]?\d{2}[\s-]?\d{2})',
            r'(\d{2}[\s-]?\d{3}[\s-]?\d{2}[\s-]?\d{2})'  # 29 123 45 67
        ]

        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                phone = re.sub(r'[\s\-\(\)]', '', match.group(1))
                if phone.startswith('8'):
                    phone = '+375' + phone[1:]
                elif phone.startswith('375'):
                    phone = '+' + phone
                elif len(phone) == 9:
                    phone = '+375' + phone
                return phone
        return None

    def _complete_booking(self, user_id: str) -> str:
        """Завершает запись с собранными данными"""
        session = self.user_sessions[user_id]

        # Обновляем запись в Google Sheets
        success = self.appointment_service.sheets_service.update_appointment_with_contacts(
            session['date'],
            session['time'],
            user_id,
            session.get('name', 'Пользователь'),
            session.get('phone', '')
        )

        if success:
            return (f"✅ Запись завершена!\n\n"
                    f"📅 {session['date']} в {session['time']}\n"
                    f"👤 {session.get('name', 'Пользователь')}\n"
                    f"📞 {session.get('phone', 'Не указан')}\n\n"
                    f"📍 Адрес: ул. Гикало, 1\n"
                    f"📞 Телефон салона: +375 (29) 145-03-03\n\n"
                    f"💡 Если не сможете прийти, отмените запись заранее.")
        else:
            return "❌ Ошибка при обновлении записи. Пожалуйста, свяжитесь с нами по телефону."

    def _handle_appointment_requests(self, question: str, question_clean: str, user_id: str) -> Optional[str]:
        """Обрабатывает запросы на запись на стельки"""
        print(f"🔍 Отладка: question_clean = '{question_clean}'")

        # 1. Сначала проверяем отмену записей с телефоном
        cancel_patterns = [
            r'отмени?те? запись\s*(\+?\d{7,15})',
            r'отмени?те? запись по телефону\s*(\+?\d{7,15})',
            r'удали?те? запись\s*(\+?\d{7,15})',
            r'отмени?те?\s*(\+?\d{7,15})',
            r'отмена записи\s*(\+?\d{7,15})'
        ]

        for pattern in cancel_patterns:
            cancel_match = re.search(pattern, question_clean)
            if cancel_match:
                phone = cancel_match.group(1)
                print(f"🗑️ Отмена записи по телефону: {phone}")
                return self.appointment_service.cancel_appointment(phone)

        # 2. Проверяем просмотр записей с телефоном
        view_patterns = [
            r'мои записи\s*(\+?\d{7,15})',
            r'покажи мои записи\s*(\+?\d{7,15})',
            r'записи по телефону\s*(\+?\d{7,15})'
        ]

        for pattern in view_patterns:
            view_match = re.search(pattern, question_clean)
            if view_match:
                phone = view_match.group(1)
                print(f"👀 Просмотр записей по телефону: {phone}")
                return self.appointment_service.get_user_appointments_by_phone(phone)

        # 3. Если просто "отменить" или "отмена" - просим телефон
        if question_clean in ['отменить', 'отмена', 'отменить запись']:
            self.user_sessions[user_id] = {
                'awaiting_cancel_phone': True
            }
            return "📱 Для отмены записи напишите, пожалуйста, ваш номер телефона:"

        # 4. Если просто "мои записи" - просим телефон
        if question_clean == 'мои записи':
            self.user_sessions[user_id] = {
                'awaiting_view_phone': True
            }
            return "📱 Чтобы посмотреть ваши записи, напишите, пожалуйста, ваш номер телефона:"

        # 5. Проверяем конкретные команды бронирования
        booking_patterns = [
            r'запишите? меня на (\d{1,2}\.\d{1,2}\.?\d{0,4}) в (\d{1,2}:\d{2})',
            r'запишите? на (\d{1,2}\.\d{1,2}\.?\d{0,4}) в (\d{1,2}:\d{2})',
            r'запишите? (\d{1,2}\.\d{1,2}\.?\d{0,4}) в (\d{1,2}:\d{2})',
            r'запишите? меня на (\d{1,2}\.\d{1,2}\.?\d{0,4}) в \[(\d{1,2}:\d{2})\]',
            r'запишите? на (\d{1,2}\.\d{1,2}\.?\d{0,4}) в \[(\d{1,2}:\d{2})\]'
        ]

        for i, pattern in enumerate(booking_patterns):
            booking_match = re.search(pattern, question_clean)
            print(
                f"🔍 Проверка паттерна {i}: '{pattern}' - результат: {booking_match}")
            if booking_match:
                date = booking_match.group(1)
                time = booking_match.group(2).replace('[', '').replace(']', '')
                if len(date.split('.')) == 2:
                    date = f"{date}.{datetime.now().year}"
                print(f"🎯 Найдено совпадение! Дата: {date}, Время: {time}")

                # Сохраняем данные для сессии
                self.user_sessions[user_id] = {
                    'date': date,
                    'time': time,
                    'awaiting_phone': True,
                    'awaiting_name': False
                }
                return self.appointment_service.book_specific_slot(date, time, "Пользователь", user_id)

        # 6. Проверяем общие запросы на запись
        appointment_keywords = ['записаться', 'запись', 'свободные даты']

        if any(keyword in question_clean for keyword in appointment_keywords):
            print(f"📅 Обрабатываем общий запрос на запись: {question}")
            return self.appointment_service.process_appointment_request(question, "Пользователь", user_id)

        # 7. Проверяем запросы на доступность конкретной даты
        date_patterns = [
            r'(\d{1,2})\s+(январ[ья]|феврал[ья]|март[а]?|апрел[ья]|ма[йя]|июн[ья]|июл[ья]|август[а]?|сентябр[ья]|октябр[ья]|ноябр[ья]|декабр[ья])',
            r'(\d{1,2})\.(\d{1,2})',
            r'(\d{1,2})\.(\d{1,2})\.(\d{4})'
        ]

        for pattern in date_patterns:
            if re.search(pattern, question_clean):
                print(f"📅 Проверяем доступность даты: {question}")
                return self.appointment_service.process_appointment_request(question, "Пользователь", user_id)

        print("❌ Не найдено подходящих паттернов для записи")
        return None

    def _handle_more_request(self, user_id: str) -> str:
        """Обработка запроса 'еще' - показываем следующие товары"""
        more_products = self.context_service.get_more_products(
            user_id, count=5)

        if not more_products:
            return "Больше товаров не найдено. Уточните ваш запрос для нового поиска."

        context = self.context_service.get_user_context(user_id)
        salon_name = context['salon_name'] if context else "салоне"

        prompt = self.prompt_service.create_more_products_prompt(
            more_products, salon_name)

        try:
            response = self.client.chat.completions.create(
                model=self.prompt_service.get_model_for_task("search"),
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=400
            )

            result = response.choices[0].message.content
            print(f"✅ Показали еще {len(more_products)} товаров для {user_id}")
            return result

        except Exception as e:
            print(f"❌ Ошибка обработки 'еще': {e}")
            return self._format_products_fallback(more_products, "Дополнительные товары:")

    def _search_in_salon(self, question: str, salon_name: str, feed_file: str, user_id: str) -> str:
        """Поиск товаров в фиде салона"""
        filtered_products = self.search_service.search_in_salon(
            question, salon_name, feed_file)

        if not filtered_products:
            return f"В салоне {salon_name} не найдено товаров по вашему запросу."

        shown_products = filtered_products[:10]
        self.context_service.set_search_context(
            user_id, salon_name, question, filtered_products, shown_products
        )

        return self._create_search_response(question, shown_products, salon_name, len(filtered_products))

    def _create_search_response(self, question: str, products: List[Product], salon_name: str, total_products: int) -> str:
        """Создаем ответ для поиска товаров"""
        prompt = self.prompt_service.create_search_prompt(
            question, products, salon_name, total_products)

        try:
            response = self.client.chat.completions.create(
                model=self.prompt_service.get_model_for_task("search"),
                messages=[
                    {
                        "role": "system",
                        "content": "Ты точный помощник в ортопедическом салоне. Всегда давай ссылки на товары."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.1,
                max_tokens=800
            )

            result = response.choices[0].message.content
            print(f"✅ Результат поиска получен")
            return result

        except Exception as e:
            print(f"❌ Ошибка поиска: {str(e)}")
            return self._format_products_fallback(products, f"Товары в салоне {salon_name}:")

    def _format_products_fallback(self, products: List[Product], title: str) -> str:
        """Форматирование товаров без AI (fallback)"""
        if not products:
            return "Товары не найдены"

        result = f"{title}\n\n"
        for i, product in enumerate(products, 1):
            size = product.get_size()
            result += f"{i}. {product.name} - {product.price}р"
            if size:
                result += f" (размер: {size})"
            result += f"\n{product.url}\n\n"

        if len(products) > 5:
            result += "💡 Напишите 'еще' чтобы увидеть больше товаров"

        return result

    def _get_quick_answer(self, question: str) -> Optional[str]:
        """Проверяем быстрые ответы"""
        for keyword, answer in self.quick_answers.items():
            if keyword in question:
                print(f"🎯 Используем быстрый ответ для: {keyword}")
                return answer
        return None

    def _get_general_consultation(self, question: str) -> str:
        """Общая консультация через AI"""
        try:
            response = self.client.chat.completions.create(
                model=self.prompt_service.get_model_for_task("consultation"),
                messages=[
                    {
                        "role": "system",
                        "content": """Ты дружелюбный консультант ортопедического салона ORTOS. 

Правила общения:
1. Будь естественным и полезным, как живой консультант
2. Не повторяй одну информацию несколько раз
3. Упоминай адрес ТОЛЬКО когда спрашивают про запись или консультацию
4. На вопросы про контакты - давай телефоны сразу
5. Отвечай кратко по сути вопроса
6. Используй эмодзи для дружелюбия

Информация для справки:
• Срок изготовления индивидуальных стелек: ДО 20 ДНЕЙ
• Адрес консультаций: ул. Гикало, 1, Минск
• Телефоны: +375 (29) 145-03-03, +375 (17) 355-77-03
• Сайт: ortos.by
• Есть выездные консультации по регионам"""
                    },
                    {
                        "role": "user",
                        "content": question
                    }
                ],
                temperature=0.3,
                max_tokens=400
            )

            return response.choices[0].message.content

        except Exception as e:
            error_msg = "Извините, произошла ошибка. Попробуйте позже."
            print(f"❌ Ошибка общей консультации: {e}")
            return error_msg

    def _handle_greeting(self, question: str) -> Optional[str]:
        """Обрабатывает приветствия естественно"""
        greetings = ['привет', 'добрый день', 'добрый вечер',
                     'доброе утро', 'здравствуйте', 'здраствуйте']

        if any(greeting in question.lower() for greeting in greetings):
            responses = [
                "Добрый день! 👋 Чем могу помочь?",
                "Здравствуйте! Рад вас видеть. Какой вопрос вас интересует?",
                "Приветствую! Чем могу быть полезен?",
                "Добрый день! Задавайте ваш вопрос - с радостью помогу!"
            ]
            import random
            return random.choice(responses)

        return None


class EmbeddingsBotService:
    def __init__(self):
        self._init_lock = threading.Lock()
        self._initializing = False
        self.embeddings_service: Optional[EmbeddingsService] = None
        self.client: Optional[Groq] = None

    def _initialize_embeddings(self):
        print("⚙️ Инициализация EmbeddingsBotService...")
        service = None
        client = None
        try:
            service = EmbeddingsService()
            print("✅ EmbeddingsService создан")
            loaded = False
            try:
                loaded = service.load_indices()
                print(f"📦 Индексы загружены: {loaded}")
            except Exception as e:
                print(f"❌ Ошибка загрузки индексов: {e}")
            if not loaded:
                try:
                    print("🔨 Строим индексы...")
                    service.build_indices()
                    service.save_indices()
                    print("✅ Индексы созданы и сохранены")
                except Exception as e:
                    print(f"❌ Ошибка создания индексов: {e}")
            if Config.GROQ_API_KEY:
                try:
                    client = Groq(api_key=Config.GROQ_API_KEY)
                    print("✅ Groq клиент инициализирован")
                except Exception as e:
                    print(f"❌ Ошибка инициализации Groq: {e}")
        except Exception as e:
            print(f"❌ Ошибка инициализации EmbeddingsService: {e}")
        finally:
            with self._init_lock:
                if service and not self.embeddings_service:
                    self.embeddings_service = service
                    print("✅ EmbeddingsService активирован")
                if client:
                    self.client = client
                self._initializing = False
                print("⚙️ Инициализация EmbeddingsBotService завершена")

    def _ensure_initialized(self) -> bool:
        if self.embeddings_service is not None:
            return True
        with self._init_lock:
            if self.embeddings_service is not None:
                return True
            if self._initializing:
                return False
            self._initializing = True
            threading.Thread(target=self._initialize_embeddings, daemon=True).start()
        return False

    def process_question(self, question: str, user_id: str = "telegram") -> str:
        print(f"📝 [EmbeddingsBotService] Получен вопрос от {user_id}: {question}")
        if not self._ensure_initialized():
            print("⏳ EmbeddingsService еще инициализируется")
            return "🔄 Бот запускается, попробуйте еще раз через минуту."
        query = question.strip()
        if not query:
            return "Пожалуйста, напишите вопрос."
        if not self.embeddings_service:
            print("⚠️ EmbeddingsService недоступен")
            return "Сервис поиска временно недоступен."
        try:
            results = self.embeddings_service.search(query, top_k=7)
            print(f"🔍 Найдено результатов: {len(results)}")
        except Exception as e:
            print(f"❌ Ошибка поиска: {e}")
            return "Произошла ошибка при поиске. Попробуйте позже."
        if not results:
            return "Информация не найдена. Уточните вопрос."
        answer = self._generate_answer(query, results)
        summary = self._format_results(results)
        parts = [p for p in [answer, summary] if p]
        if not parts:
            print("⚠️ Ответ не сформирован")
            return "Информация обработана, но ответ не сформирован."
        response_text = "\n\n".join(parts)
        print(f"✅ Ответ сформирован ({len(response_text)} символов)")
        return response_text

    def _generate_answer(self, question: str, results: List[Tuple[Dict[str, Any], float]]) -> str:
        if not self.client or not results:
            print("⚠️ Нет клиента или результатов для генерации ответа")
            return ""
        context_parts = []
        for doc, score in results[:5]:
            if doc['type'] == 'section':
                context_parts.append(f"[РАЗДЕЛ: {doc['title']}]\n{doc['text']}")
            else:
                full_info = doc.get('full_text', doc.get('address', ''))
                context_parts.append(
                    f"[САЛОН: {doc.get('city', 'Неизвестно')}]\n{full_info}"
                )
        context = "\n\n".join(context_parts)
        system_prompt = """Ты — профессиональный консультант ORTOS (Беларусь). Отвечай ТОЛЬКО по контексту.
        - 2–3 предложения
        - Уверенно: "подходят", "помогают", "снимают"
        - 1 факт + 1 польза
        - Без повторения вопроса

        ## ПРИМЕР
        Вопрос: Подойдут ли при шпоре?
        Ответ: Да, стельки подходят при пяточной шпоре. Они амортизируют ударную нагрузку. Это снижает боль при ходьбе.

        ## КРИТИЧЕСКИ ВАЖНО
        - ОТВЕЧАЙ ТОЛЬКО НА ВОПРОС. Ничего лишнего.
        - Говори уверенно: "подходят", "помогают", "снимают" — БЕЗ "могут", "возможно", "привести к"
        - НЕ используй: "мы", "наши", "ORTOS делает", "рекомендуем"
        - НЕ выдумывай:
        • НЕТ онлайн-календаря, личного кабинета
        • Стельки: ТОЛЬКО самовывоз (Гикало, 1), НЕТ возврата, НЕТ гарантии
        • Консультации: ТОЛЬКО Минск (Гикало, 1) + выездные (по ссылке)
        • Салоны в городах: ТОЛЬКО продажа товаров (НЕ консультации)
        • Процедура: запись → консультация → 20 дней → самовывоз
                Остальное — ТОЛЬКО из контекста."""
        user_message = f"""Вопрос: {question}

База знаний:
{context}

Дай точный краткий ответ БЕЗ повторения вопроса. Максимум 2-3 предложения."""
        try:
            response = self.client.chat.completions.create(
                model=Config.CONSULT_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message}
                ],
                max_tokens=400,
                temperature=0.0
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"❌ Ошибка Groq: {e}")
            return ""

    def _format_results(self, results: List[Tuple[Dict[str, Any], float]]) -> str:
        if not results:
            return ""
        lines = ["🔎 Источники поиска:"]
        for doc, score in results[:3]:
            if doc['type'] == 'section':
                lines.append(f"• {doc['title']} (score {score:.2f})")
            else:
                lines.append(f"• {doc['city']} — {doc['address']} (score {score:.2f})")
        return "\n".join(lines)
