# -*- coding: utf-8 -*-
import os
import sys
import json
import time
import numpy as np
from typing import List, Tuple, Dict, Optional
from pathlib import Path

if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

try:
    from sentence_transformers import SentenceTransformer
    import faiss
except ImportError:
    raise ImportError(
        "Требуются зависимости: pip install sentence-transformers faiss-cpu numpy"
    )

try:
    from rank_bm25 import BM25Okapi
except ImportError:
    print("⚠️  BM25Okapi не установлен")
    BM25Okapi = None


class EmbeddingsService:
    """
    Гибридный поиск с переранжированием по категориям.
    """

    def __init__(
        self,
        model_name: str = "intfloat/multilingual-e5-base",
        knowledge_base_path: str = os.path.join(os.path.dirname(
            __file__), "..", "data", "knowledge_base.json"),
        cache_dir: Optional[str] = None,
    ):
        if cache_dir:
            os.environ["HF_HOME"] = cache_dir

        self.model_name = model_name
        self.knowledge_base_path = knowledge_base_path

        print(f"📥 Загружаем модель: {model_name}...")
        model_start = time.perf_counter()
        self.model = SentenceTransformer(model_name, device="cpu")
        self.embedding_dim = self.model.get_sentence_embedding_dimension()
        model_elapsed = time.perf_counter() - model_start
        print(f"✅ Модель загружена за {model_elapsed:.2f}s. Размер вектора: {self.embedding_dim}")

        self.locations = []
        self.sections = []
        self.all_documents = []

        self.semantic_index = None
        self.bm25_index = None

        # Маппинг вопросов на категории
        self.category_keywords = {
            'indications': [
                'плоскостопие', 'шпора', 'вальгус', 'артроз', 'мозоли', 'диабет',
                'колени', 'сколиоз', 'остеохондроз', 'беременность', 'варикоз',
                'фасциит', 'метатарзалгия', 'молоткообразные', 'боль в спине',
                'подходят при', 'помогают при', 'заболевания', 'деформации'],
            'process': [
                'материалы', 'ЭВА', 'слепок', 'по слепку', 'Trives', 'Amcube', 'сканирование', '3D', 'моделирование', 'изготовление'],
            'delivery': [
                'доставка', 'самовывоз', 'курьером', 'забрать', 'получить', 'Гикало 1', 'выдача'],
            'manufacturing_time': ['сроки', 'время', 'дней', 'ждать', 'как долго'],
            'specialists': ['врачи', 'ортопеды', 'консультация', 'прием', 'специалист'],
            'locations': ['адреса', 'филиалы', 'салоны', 'города', 'где', 'находится'],
            'contacts': ['телефон', 'контакты', 'связь', 'email', 'мессенджер'],
            'prices': ['цены', 'стоимость', 'рубли', 'скидка', 'акция'],

            'payment': ['оплата', 'платежи', 'способы', 'расчет', 'карта', 'наличные'],
            'advantages': ['преимущества', 'эффект', 'результаты', 'пользу', 'устойчивость', 'кровообращение'],
            'target_audience': ['аудитория', 'назначение', 'для кого', 'кому', 'подходит', 'спортсмены', 'спортивной'],
            'specialists': ['врачи', 'ортопеды', 'консультация', 'прием', 'специалист', 'записаться', 'запись'],
            'mobile_cabinet': ['выездные', 'выездной', 'выезд', 'расписание', 'запись на выезд'],
            'contacts': ['телефон', 'контакты', 'связь', 'email', 'мессенджер', 'позвонить', 'написать'],
        }

        self._load_knowledge_base()

    def _load_knowledge_base(self) -> None:
        """Загружает структурированные данные"""
        if not os.path.exists(self.knowledge_base_path):
            raise FileNotFoundError(
                f"Knowledge base не найдена: {self.knowledge_base_path}")

        load_start = time.perf_counter()
        with open(self.knowledge_base_path, 'r', encoding='utf-8') as f:
            kb = json.load(f)
        load_elapsed = time.perf_counter() - load_start

        self.locations = kb.get('locations', [])
        print(f"📍 Загружено адресов: {len(self.locations)}")

        self.sections = kb.get('sections', {})
        print(f"📚 Загружено секций: {len(self.sections)}")
        print(f"🧾 Загрузка базы знаний заняла {load_elapsed:.2f}s")

        self.all_documents = []

        # Добавляем sections
        section_idx = 0
        for key, section in self.sections.items():
            section_text = f"{section['title']}. {section['content']}"

            self.all_documents.append({
                'id': f"section_{section_idx}",
                'type': 'section',
                'title': section['title'],
                'text': section_text,
                'lines': section.get('lines', []),
                'key': key,
            })
            section_idx += 1

        # Добавляем locations
        for i, loc in enumerate(self.locations):
            location_text = f"Салон ORTOS {loc['city']}. Адрес: {loc['address']}. Часы: {loc['working_hours']}. Телефоны: {', '.join(loc.get('phones', []))}."

            self.all_documents.append({
                'id': f"location_{i}",
                'type': 'location',
                'city': loc['city'],
                'address': loc['address'],
                'text': location_text,
                'full_text': loc['full_text'],
                'phones': loc.get('phones', []),
                'working_hours': loc.get('working_hours', ''),
            })

        print(f"📄 Всего документов: {len(self.all_documents)}")

    def _build_indices(self) -> None:
        """Создает индексы"""
        print(f"\n🔨 Создаем индексы...")
        build_start = time.perf_counter()

        texts = [doc['text'] for doc in self.all_documents]

        print("  📊 Создаем semantic индекс...")
        semantic_start = time.perf_counter()
        embeddings = self.model.encode(
            texts,
            convert_to_tensor=False,
            show_progress_bar=True,
            batch_size=32,
        )
        embeddings = np.array(embeddings, dtype=np.float32)
        print(f"  📐 Embeddings shape: {embeddings.shape}")
        faiss.normalize_L2(embeddings)

        self.semantic_index = faiss.IndexFlatIP(self.embedding_dim)
        self.semantic_index.add(embeddings)
        semantic_elapsed = time.perf_counter() - semantic_start
        print(f"  ✅ Semantic индекс: {self.semantic_index.ntotal} векторов за {semantic_elapsed:.2f}s, dim={self.embedding_dim}")

        if BM25Okapi:
            print("  🔤 Создаем BM25 индекс...")
            bm25_start = time.perf_counter()
            tokenized_texts = [text.lower().split() for text in texts]
            self.bm25_index = BM25Okapi(tokenized_texts)
            bm25_elapsed = time.perf_counter() - bm25_start
            print(f"  ✅ BM25 индекс создан за {bm25_elapsed:.2f}s, документов={len(tokenized_texts)}")

        total_elapsed = time.perf_counter() - build_start
        print(f"⏱️ Построение индексов завершено за {total_elapsed:.2f}s")

    def _get_category_boost(self, query: str, doc_key: str) -> float:
        """Вычисляет boost для категории на основе ключевых слов в вопросе"""
        query_lower = query.lower()

        if doc_key in self.category_keywords:
            keywords = self.category_keywords[doc_key]
            matches = sum(1 for kw in keywords if kw in query_lower)
            if matches > 0:
                return 1.0 + (matches * 0.15)

        return 1.0

    def search(
        self,
        query: str,
        top_k: int = 5,
        min_score: float = 0.30,
    ) -> List[Tuple[Dict, float]]:
        """
        Гибридный поиск с переранжированием по категориям.
        """
        if not self.semantic_index:
            raise RuntimeError("Индексы не инициализированы!")
        if not query or not query.strip():
            return []

        print(f"🔎 Запрос поиска: '{query.strip()}', top_k={top_k}, min_score={min_score}")
        results = {}

        # ===== SEMANTIC SEARCH =====
        query_embedding = self.model.encode([query], convert_to_tensor=True)
        query_embedding = query_embedding.cpu().numpy()
        faiss.normalize_L2(query_embedding)

        distances, indices = self.semantic_index.search(
            query_embedding, min(top_k * 4, len(self.all_documents)))

        for i, idx in enumerate(indices[0]):
            if idx == -1:
                continue
            doc_id = self.all_documents[idx]['id']
            score = float(distances[0][i])
            results[doc_id] = score

        # ===== BM25 BOOST =====
        if self.bm25_index:
            query_tokens = query.lower().split()
            bm25_scores = self.bm25_index.get_scores(query_tokens)
            max_bm25 = bm25_scores.max()

            if max_bm25 > 0:
                bm25_scores = bm25_scores / max_bm25

                for idx, score in enumerate(bm25_scores):
                    if score > 0.05:
                        doc_id = self.all_documents[idx]['id']
                        if doc_id in results:
                            results[doc_id] = results[doc_id] * \
                                0.6 + score * 0.4
                        else:
                            results[doc_id] = score * 0.3

        # ===== ПЕРЕРАНЖИРОВАНИЕ ПО КАТЕГОРИЯМ =====
        for doc_id, score in list(results.items()):
            doc = next(
                (d for d in self.all_documents if d['id'] == doc_id), None)
            if doc and doc['type'] == 'section':
                category_boost = self._get_category_boost(query, doc['key'])
                if category_boost != 1.0:
                    print(f"  🎯 Boost категории для {doc['title']} ({doc['key']}): x{category_boost:.2f}")
                results[doc_id] = score * category_boost

        # ===== СОРТИРОВКА И ФИЛЬТРАЦИЯ =====
        sorted_results = sorted(
            results.items(), key=lambda x: x[1], reverse=True)

        output = []
        for doc_id, score in sorted_results:
            if len(output) >= top_k:
                break

            if score < min_score:
                break

            doc = next(
                (d for d in self.all_documents if d['id'] == doc_id), None)
            if not doc:
                continue

            output.append((doc, score))

        if output:
            top_score = output[0][1]
            print(f"📈 Итог поиска: {len(output)} документов, top_score={top_score:.4f}")
            for doc, score in output:
                if doc['type'] == 'section':
                    print(f"  • Раздел: {doc['title']} | score={score:.4f} | key={doc.get('key')}")
                else:
                    print(f"  • Салон: {doc['city']} | score={score:.4f} | адрес={doc['address']}")
        else:
            print("📉 Итог поиска: результатов нет")

        return output

    def build_indices(self) -> None:
        """Публичный метод для создания индексов"""
        self._build_indices()

    def save_indices(self, index_dir: str = os.path.join(os.path.dirname(__file__), "..", "data", "embeddings_v2")) -> None:
        """Сохраняет индексы на диск"""
        Path(index_dir).mkdir(parents=True, exist_ok=True)

        if self.semantic_index:
            faiss.write_index(self.semantic_index,
                              f"{index_dir}/semantic.faiss")
            print(f"✅ Semantic индекс сохранен")

        metadata = {
            'model_name': self.model_name,
            'embedding_dim': self.embedding_dim,
            'total_documents': len(self.all_documents),
            'has_bm25': self.bm25_index is not None,
        }

        with open(f"{index_dir}/metadata.json", 'w', encoding='utf-8') as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)

        print(f"✅ Метаданные сохранены")

    def load_indices(self, index_dir: str = os.path.join(os.path.dirname(__file__), "..", "data", "embeddings_v2")) -> bool:
        """Загружает индексы с диска, если они существуют"""
        semantic_path = f"{index_dir}/semantic.faiss"
        metadata_path = f"{index_dir}/metadata.json"

        if not os.path.exists(semantic_path) or not os.path.exists(metadata_path):
            return False

        try:
            load_start = time.perf_counter()
            self.semantic_index = faiss.read_index(semantic_path)
            metadata = {}
            try:
                with open(metadata_path, 'r', encoding='utf-8') as f:
                    metadata = json.load(f)
            except Exception as meta_error:
                print(f"⚠️ Не удалось прочитать метаданные: {meta_error}")
            load_elapsed = time.perf_counter() - load_start
            print(
                f"✅ Semantic индекс загружен: {self.semantic_index.ntotal} векторов за {load_elapsed:.2f}s")
            if metadata:
                print(f"ℹ️ Метаданные индекса: model={metadata.get('model_name')}, dim={metadata.get('embedding_dim')}, docs={metadata.get('total_documents')}")
            return True
        except Exception as e:
            print(f"❌ Ошибка загрузки индексов: {e}")
            return False

    def get_stats(self) -> Dict:
        """Статистика индексов"""
        return {
            'total_documents': len(self.all_documents),
            'total_locations': len(self.locations),
            'total_sections': len(self.sections),
            'embedding_dim': self.embedding_dim,
            'model_name': self.model_name,
            'has_semantic_index': self.semantic_index is not None,
            'has_bm25_index': self.bm25_index is not None,
        }
