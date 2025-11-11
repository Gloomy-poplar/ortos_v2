# -*- coding: utf-8 -*-

import sys
import time
import json
from typing import List, Tuple, Dict, Any

if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

from services.embeddings_service import EmbeddingsService
from config import Config

try:
    from groq import Groq
    GROQ_AVAILABLE = True
except ImportError:
    GROQ_AVAILABLE = False
    print("⚠️  groq library not installed")


def get_groq_answer(query: str, search_results: List[Tuple[Dict[str, Any], float]]) -> str:
    """Получить ответ от Groq"""
    if not GROQ_AVAILABLE or not Config.GROQ_API_KEY:
        return "❌ Groq API не доступен"

    try:
        context_parts = []
        for doc, score in search_results:
            if doc['type'] == 'section':
                context_parts.append(
                    f"[РАЗДЕЛ: {doc['title']}]\n{doc['text']}")
            else:
                full_info = doc.get('full_text', doc.get('address', ''))
                context_parts.append(
                    f"[САЛОН: {doc.get('city', 'Неизвестно')}]\n{full_info}")

        context = "\n\n".join(context_parts)

        client = Groq(api_key=Config.GROQ_API_KEY)

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

        user_message = f"""Вопрос: {query}

База знаний:
{context}

Дай точный краткий ответ БЕЗ повторения вопроса. Максимум 2-3 предложения."""

        response = client.chat.completions.create(
            model=Config.CONSULT_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            max_tokens=800,
            temperature=0.0
        )

        return response.choices[0].message.content

    except Exception as e:
        return f"❌ Ошибка: {str(e)}"


def save_results_to_file(results_summary: Dict, scores: List[float], questions: List[str], output_file: str = "test_results.txt"):
    """Сохранить результаты теста в txt файл с поддержкой русского языка"""
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write("="*100 + "\n")
            f.write("📈 РЕЗУЛЬТАТЫ ТЕСТА ПОИСКА - ДЕТАЛЬНЫЙ АНАЛИЗ\n")
            f.write("="*100 + "\n\n")

            f.write(f"Всего вопросов: {results_summary['total_questions']}\n")
            f.write(f"Модель: intfloat/multilingual-e5-base\n")
            f.write(
                f"Время теста: {results_summary.get('test_time', 'N/A')}\n\n")

            f.write("ДЕТАЛЬНЫЕ РЕЗУЛЬТАТЫ ПО ВОПРОСАМ:\n")
            f.write("-"*100 + "\n\n")

            for idx, result in enumerate(results_summary['questions_results'], 1):
                f.write(f"{'='*100}\n")
                f.write(f"❓ ВОПРОС {idx}: {result['question']}\n")
                f.write(f"{'='*100}\n\n")

                f.write(f"📊 СТАТИСТИКА ПОИСКА:\n")
                f.write(f"  • Top Score: {result['top_score']:.4f}\n")
                f.write(
                    f"  • Найдено результатов: {result['results_count']}\n")
                f.write(
                    f"  • Средний score: {result.get('avg_score', 0):.4f}\n\n")

                f.write(f"📚 НАЙДЕННЫЕ КАТЕГОРИИ И ИСТОЧНИКИ:\n")
                for i, res in enumerate(result['search_results'], 1):
                    doc_type = res['type']
                    if doc_type == 'section':
                        f.write(f"  [{i}] 📚 РАЗДЕЛ: {res['title']}\n")
                        f.write(f"      Score: {res['score']:.4f}\n")
                        f.write(f"      Ключ: {res.get('key', 'N/A')}\n")
                        f.write(f"      Превью: {res['text'][:150]}...\n\n")
                    else:
                        f.write(f"  [{i}] 📍 САЛОН: {res['city']}\n")
                        f.write(f"      Score: {res['score']:.4f}\n")
                        f.write(f"      Адрес: {res['address']}\n")
                        f.write(
                            f"      Телефоны: {', '.join(res.get('phones', []))}\n\n")

                if 'answer' in result and result['answer']:
                    f.write(f"🤖 ОТВЕТ AI:\n")
                    f.write(f"{result['answer']}\n\n")

                f.write("\n")

            f.write("="*100 + "\n")
            f.write("📊 ИТОГОВАЯ СТАТИСТИКА\n")
            f.write("="*100 + "\n\n")

            avg_score = sum(scores) / len(scores) if scores else 0
            min_score = min(scores) if scores else 0
            max_score = max(scores) if scores else 0

            f.write(f"Средний score поиска: {avg_score:.4f}\n")
            f.write(f"Минимальный score: {min_score:.4f}\n")
            f.write(f"Максимальный score: {max_score:.4f}\n")
            f.write(f"Диапазон: {max_score - min_score:.4f}\n\n")

            good = sum(1 for s in scores if s >= 0.5)
            medium = sum(1 for s in scores if 0.3 <= s < 0.5)
            bad = sum(1 for s in scores if s < 0.3)

            f.write(
                f"✅ Хорошие результаты (score >= 0.5): {good}/{len(questions)}\n")
            f.write(
                f"⚠️  Средние результаты (0.3 <= score < 0.5): {medium}/{len(questions)}\n")
            f.write(
                f"❌ Плохие результаты (score < 0.3): {bad}/{len(questions)}\n\n")

            f.write(f"Процент успеха: {(good/len(questions)*100):.1f}%\n")

        print(f"✅ Результаты сохранены в файл: {output_file}")
    except Exception as e:
        print(f"❌ Ошибка при сохранении результатов: {str(e)}")


def main():

    embeddings_service = EmbeddingsService(
        knowledge_base_path="d:\\ortos-bot\\data\\knowledge_base.json"
    )

    print("🔍 Проверяем наличие сохраненных индексов...")
    if embeddings_service.load_indices():
        print("✅ Индексы загружены с диска\n")
    else:
        print("🔨 Индексы не найдены, создаем новые...")
        start = time.time()
        embeddings_service.build_indices()
        build_time = time.time() - start
        print(f"✅ Индексы созданы за {build_time:.2f} сек")

        print("💾 Сохраняем индексы на диск...")
        save_start = time.time()
        embeddings_service.save_indices()
        save_time = time.time() - save_start
        print(f"✅ Индексы сохранены за {save_time:.2f} сек\n")

    questions = []

    results_summary = {
        "total_questions": len(questions),
        "avg_score": 0,
        "test_time": "N/A",
        "questions_results": []
    }

    scores = []
    test_start = time.time()

    question_index = 0

    while True:
        query = input(
            "\nВведите вопрос (пустая строка для завершения): ").strip()
        if not query:
            break

        question_index += 1
        questions.append(query)

        print(f"\n{'='*100}")
        print(f"❓ Вопрос {question_index}: '{query}'")
        print('='*100)

        results = embeddings_service.search(query, top_k=7)

        top_score = results[0][1] if results else 0
        scores.append(top_score)

        print(f"\n📊 Результаты поиска (top score: {top_score:.4f}):")

        search_results_detail = []
        for i, (doc, score) in enumerate(results, 1):
            doc_type = doc['type']
            if doc_type == 'section':
                print(f"  [{i}] 📚 {doc['title'][:50]:50} | score: {score:.4f}")
                search_results_detail.append({
                    'type': 'section',
                    'title': doc['title'],
                    'key': doc.get('key', 'N/A'),
                    'text': doc['text'],
                    'score': score
                })
            else:
                print(f"  [{i}] 📍 {doc['city']:20} | score: {score:.4f}")
                search_results_detail.append({
                    'type': 'location',
                    'city': doc['city'],
                    'address': doc['address'],
                    'phones': doc.get('phones', []),
                    'score': score
                })

        answer = ""
        if GROQ_AVAILABLE and Config.GROQ_API_KEY:
            print("\n🤖 Ответ AI:")
            answer = get_groq_answer(query, results)
            answer_preview = answer[:200] + \
                "..." if len(answer) > 200 else answer
            print(f"  {answer_preview}")

        avg_score = sum(s for _, s in results) / len(results) if results else 0

        results_summary['questions_results'].append({
            'question': query,
            'top_score': top_score,
            'avg_score': avg_score,
            'results_count': len(results),
            'search_results': search_results_detail,
            'answer': answer
        })

        time.sleep(2)

    if not questions:
        print("\n❔ Вопросы не были заданы. Завершение.")
        return

    test_time = time.time() - test_start
    results_summary['total_questions'] = len(questions)
    results_summary['test_time'] = f"{test_time:.2f} сек"

    print(f"\n{'='*100}")
    print("📈 ИТОГОВАЯ СТАТИСТИКА")
    print('='*100)

    avg_score = sum(scores) / len(scores) if scores else 0
    results_summary['avg_score'] = avg_score
    min_score = min(scores) if scores else 0
    max_score = max(scores) if scores else 0

    print(f"\n📊 Средний score поиска: {avg_score:.4f}")
    print(f"   Минимальный score: {min_score:.4f}")
    print(f"   Максимальный score: {max_score:.4f}")

    good = sum(1 for s in scores if s >= 0.5)
    medium = sum(1 for s in scores if 0.3 <= s < 0.5)
    bad = sum(1 for s in scores if s < 0.3)

    print(f"\n✅ Хорошие результаты (score >= 0.5): {good}/{len(questions)}")
    print(
        f"⚠️  Средние результаты (0.3 <= score < 0.5): {medium}/{len(questions)}")
    print(f"❌ Плохие результаты (score < 0.3): {bad}/{len(questions)}")

    print(f"\n💾 Сохраняем результаты теста...")
    save_results_to_file(results_summary, scores, questions)

    print(f"\n✅ Готово!")


if __name__ == "__main__":
    main()
