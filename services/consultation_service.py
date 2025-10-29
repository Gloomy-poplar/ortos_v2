import os
import re
from typing import Optional, Dict, Any
from config import Config


class ConsultationService:
    def __init__(self):
        self.stelki_file = Config.STELKI_FILE

    def get_consultation_response(self, question: str, groq_client, data: Optional[Dict[str, str]] = None) -> str:
        """Консультация по стелькам — RAG: используем локальную базу и модель.

        Параметры:
        - question: текст вопроса клиента
        - groq_client: инициализированный клиент Groq
        - data: опциональный словарь с загруженными файлами (ключ 'stelki' предпочтителен)

        Логика:
        1. Берём локальную базу (data['stelki'] или файл)
        2. Если вопрос явно про индивидуальные стельки — сначала пробуем истончить
           релевантный фрагмент из локальной базы и, при возможности, скомбинировать
           с вызовом модели для формирования ответа.
        3. Если модель недоступна или ошибка — возвращаем лучший локальный фрагмент.
        """
        try:
            # Приоритет — данные, переданные из BotService (RAG loader)
            stelki_text = ""
            if data and isinstance(data, dict):
                stelki_text = data.get('stelki') or data.get('stelki.txt') or ""

            if not stelki_text:
                stelki_text = self._load_stelki_text()

            # Если вопрос про индивидуальные стельки — сначала используем локальную базу
            if self._is_about_individual_insoles(question):
                # Попытка: сформировать промпт и вызвать модель через groq
                try:
                    from services.prompt_service import PromptService
                    prompt_service = PromptService()

                    prompt, system_role = prompt_service.create_consultation_prompt(
                        question, stelki_text)

                    response = groq_client.chat.completions.create(
                        model=prompt_service.get_model_for_task("consultation"),
                        messages=[
                            {"role": "system", "content": system_role},
                            {"role": "user", "content": prompt}
                        ],
                        temperature=0.1,
                        max_tokens=400
                    )

                    # Возвращаем ответ модели при наличии
                    model_ans = getattr(response.choices[0].message, 'content', None) if response else None
                    if model_ans:
                        return model_ans
                    # Если модель вернула пусто — падаем к локальному ранжированию
                except Exception as e:
                    print(f"⚠️ Ошибка вызова модели в консультации: {e}")

                # Фоллбек — берём лучший фрагмент из локальной базы
                return self._get_answer_from_file(question, stelki_text)

            # По умолчанию (вне темы стелек) — возвращаем общее сообщение
            return "❗ Сейчас я могу давать консультации только по индивидуальным стелькам."

        except Exception as e:
            error_msg = "Извините, произошла ошибка. Попробуйте позже."
            print(f"❌ Ошибка консультации: {e}")
            return error_msg

    def _is_about_individual_insoles(self, question: str) -> bool:
        """Проверяет, касается ли вопрос индивидуальных стелек"""
        individual_keywords = ['индивидуальн', 'ортопедическ', 'стельк']
        question_lower = question.lower()
        return any(keyword in question_lower for keyword in individual_keywords)

    def _get_answer_from_file(self, question: str, stelki_text: str) -> str:
        """Простой локальный ранжировщик: ищет наиболее релевантный абзац в тексте.

        Если релевантный фрагмент не найден — возвращает дружелюбное сообщение.
        """
        try:
            if not stelki_text or stelki_text.strip() == "":
                return "База знаний о стельках временно недоступна. Попробуйте позже."

            # Разбиваем на абзацы — чаще всего в базе есть разделы, разделённые пустой строкой
            paragraphs = [p.strip() for p in re.split(r"\n\s*\n", stelki_text) if p.strip()]
            if not paragraphs:
                # Как fallback — возвращаем первые 1000 символов
                return stelki_text[:2000]

            # Простая релевантность: количество пересечений уникальных слов
            q_words = set(re.findall(r"[\w\-]{3,}", question.lower()))
            if not q_words:
                return paragraphs[0]

            best_para = None
            best_score = 0
            for p in paragraphs:
                p_words = set(re.findall(r"[\w\-]{3,}", p.lower()))
                # Оценка — количество общих слов
                score = len(q_words & p_words)
                if score > best_score:
                    best_score = score
                    best_para = p

            if best_para and best_score > 0:
                return best_para

            # Если совпадений мало — вернем короткую справку (первые 2 абзаца)
            return "\n\n".join(paragraphs[:2])

        except Exception as e:
            print(f"❌ Ошибка локального поиска по базе стелек: {e}")
            return "Извините, произошла ошибка при поиске в локальной базе." 

    

    # Закомментированный метод для общих вопросов
    # def _get_general_answer(self, question: str, groq_client) -> str:
    #     """Общий ответ для других вопросов"""
    #     try:
    #         from services.prompt_service import PromptService
    #         prompt_service = PromptService()
    #
    #         stelki_text = self._load_stelki_text()
    #         prompt, system_role = prompt_service.create_consultation_prompt(
    #             question, stelki_text)
    #
    #         response = groq_client.chat.completions.create(
    #             model=prompt_service.get_model_for_task("consultation"),
    #             messages=[
    #                 {"role": "system", "content": system_role},
    #                 {"role": "user", "content": prompt}
    #             ],
    #             temperature=0.1,
    #             max_tokens=400
    #         )
    #
    #         return response.choices[0].message.content
    #
    #     except Exception as e:
    #         return "Извините, произошла ошибка. Попробуйте позже."

    def _load_stelki_text(self) -> str:
        """Загружает информацию о стельках"""
        try:
            if os.path.exists(self.stelki_file):
                with open(self.stelki_file, 'r', encoding='utf-8') as f:
                    return f.read()
            else:
                return "База знаний о стельках временно недоступна."
        except Exception as e:
            return f"Ошибка загрузки базы знаний: {str(e)}"

    def is_consultation_question(self, question: str) -> bool:
        """Определяет, является ли вопрос консультационным"""
        consultation_keywords = [
            'стельк', 'ортопед', 'плоскостоп', 'стопа', 'нога', 'боль',
            'осанк', 'походк', 'коррекц', 'индивидуальн', 'изготовлен'
        ]

        question_lower = question.lower()
        return any(keyword in question_lower for keyword in consultation_keywords)
