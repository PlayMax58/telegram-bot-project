# optimization.py
# Модуль с оптимизациями для ускорения работы бота

import json
import os
import time
from functools import lru_cache
from typing import Any, Dict, List, Optional, Tuple, Union

# ==========================================
# 1. БЫСТРЫЙ JSON (пытаемся использовать ujson или orjson)
# ==========================================

# Пробуем импортировать быстрые JSON библиотеки
_USE_FAST_JSON = False
try:
    import ujson as fast_json

    _USE_FAST_JSON = True
    _JSON_LIB = "ujson"
except ImportError:
    try:
        import orjson as fast_json

        _USE_FAST_JSON = True
        _JSON_LIB = "orjson"
    except ImportError:
        _JSON_LIB = "standard"

print(f"[Optimization] Используется JSON библиотека: {_JSON_LIB}")


def json_dumps(data: Any, **kwargs) -> str:
    """Быстрый дамп JSON"""
    if _USE_FAST_JSON and _JSON_LIB == "orjson":
        return fast_json.dumps(data).decode()
    elif _USE_FAST_JSON and _JSON_LIB == "ujson":
        return fast_json.dumps(data, **kwargs)
    else:
        return json.dumps(data, ensure_ascii=False, indent=kwargs.get('indent', None))


def json_loads(data: Union[str, bytes], **kwargs) -> Any:
    """Быстрая загрузка JSON"""
    if _USE_FAST_JSON:
        return fast_json.loads(data)
    else:
        return json.loads(data, **kwargs)


# ==========================================
# 2. КЕШ ДЛЯ STATS.JSON
# ==========================================

class StatsCache:
    """Кеш для stats.json с автоматической инвалидацией"""

    def __init__(self, stats_file: str, cache_ttl: int = 5):
        self.stats_file = stats_file
        self.cache_ttl = cache_ttl  # время жизни кеша в секундах
        self._cache = None
        self._last_load_time = 0
        self._last_file_mtime = 0
        self._save_pending = False
        self._dirty = False  # были ли изменения после последнего сохранения

    def load(self, force_reload: bool = False) -> Dict:
        """Загружает данные с использованием кеша"""
        current_time = time.time()

        # Проверяем, нужно ли перезагрузить
        if not force_reload and self._cache is not None:
            # Если есть ожидающие сохранения изменения, возвращаем кеш
            if self._dirty:
                return self._cache

            # Проверяем время жизни кеша
            if current_time - self._last_load_time < self.cache_ttl:
                return self._cache

            # Проверяем, изменился ли файл
            if os.path.exists(self.stats_file):
                file_mtime = os.path.getmtime(self.stats_file)
                if file_mtime <= self._last_file_mtime:
                    return self._cache

        # Загружаем данные из файла
        try:
            if os.path.exists(self.stats_file):
                with open(self.stats_file, 'r', encoding='utf-8') as f:
                    self._cache = json_loads(f.read())
                self._last_file_mtime = os.path.getmtime(self.stats_file)
            else:
                self._cache = {}

            self._last_load_time = current_time
            self._dirty = False
        except Exception as e:
            print(f"[Optimization] Ошибка загрузки stats.json: {e}")
            if self._cache is None:
                self._cache = {}

        return self._cache

    def save(self, data: Dict) -> bool:
        """Сохраняет данные и обновляет кеш"""
        try:
            # Создаём директорию, если нужно
            os.makedirs(os.path.dirname(os.path.abspath(self.stats_file)) or '.', exist_ok=True)

            # Сохраняем в файл
            with open(self.stats_file, 'w', encoding='utf-8') as f:
                f.write(json_dumps(data, indent=4))

            # Обновляем кеш
            self._cache = data
            self._last_load_time = time.time()
            self._last_file_mtime = os.path.getmtime(self.stats_file)
            self._dirty = False
            return True
        except Exception as e:
            print(f"[Optimization] Ошибка сохранения stats.json: {e}")
            return False

    def mark_dirty(self):
        """Помечает, что данные были изменены, но ещё не сохранены"""
        self._dirty = True

    def clear(self):
        """Очищает кеш"""
        self._cache = None
        self._last_load_time = 0
        self._last_file_mtime = 0
        self._dirty = False


# ==========================================
# 3. КЕШ ДЛЯ ФАЙЛОВ СО СЛОВАМИ
# ==========================================

class WordsFileCache:
    """Кеш для текстовых файлов со словами/предложениями"""

    def __init__(self, max_cache_size: int = 10):
        self.cache = {}  # {filename: (mtime, data)}
        self.max_cache_size = max_cache_size
        self.access_times = {}  # для LRU

    def get(self, filename: str, loader_func=None) -> Optional[Any]:
        """Получает данные из кеша или загружает через loader_func"""
        current_time = time.time()

        # Обновляем время доступа
        self.access_times[filename] = current_time

        # Проверяем наличие в кеше
        if filename in self.cache:
            cache_time, cache_data = self.cache[filename]
            # Проверяем, не изменился ли файл
            if os.path.exists(filename):
                file_mtime = os.path.getmtime(filename)
                if file_mtime <= cache_time:
                    return cache_data

        # Если нет в кеше или файл изменился, загружаем
        if loader_func:
            data = loader_func(filename)
            if data is not None:
                # Добавляем в кеш
                self._add_to_cache(filename, data, current_time)
            return data

        return None

    def _add_to_cache(self, filename: str, data: Any, current_time: float):
        """Добавляет данные в кеш с LRU вытеснением"""
        # Если кеш переполнен, удаляем самый старый по доступу
        if len(self.cache) >= self.max_cache_size:
            # Находим самый старый файл
            oldest = min(self.access_times.items(), key=lambda x: x[1])
            del self.cache[oldest[0]]
            del self.access_times[oldest[0]]

        # Добавляем новый
        file_mtime = os.path.getmtime(filename) if os.path.exists(filename) else current_time
        self.cache[filename] = (file_mtime, data)

    def clear(self):
        """Очищает кеш"""
        self.cache.clear()
        self.access_times.clear()


# ==========================================
# 4. ДЕКОРАТОР ДЛЯ КЕШИРОВАНИЯ ФУНКЦИЙ
# ==========================================

def cached(ttl_seconds: int = 60):
    """Декоратор для кеширования результатов функций"""

    def decorator(func):
        cache = {}

        def wrapper(*args, **kwargs):
            key = str(args) + str(sorted(kwargs.items()))
            current_time = time.time()

            if key in cache:
                result, timestamp = cache[key]
                if current_time - timestamp < ttl_seconds:
                    return result

            result = func(*args, **kwargs)
            cache[key] = (result, current_time)
            return result

        return wrapper

    return decorator


# ==========================================
# 5. ТАЙМЕР ДЛЯ ОТЛАДКИ (опционально)
# ==========================================

class Timer:
    """Простой таймер для замера времени выполнения"""

    def __init__(self, name: str = ""):
        self.name = name

    def __enter__(self):
        self.start = time.time()
        return self

    def __exit__(self, *args):
        self.end = time.time()
        self.interval = self.end - self.start
        if self.name:
            print(f"[Timer] {self.name}: {self.interval:.3f} сек")


# ==========================================
# 6. УМНЫЙ ЗАГРУЗЧИК ФАЙЛОВ С АВТО-КОДИРОВКОЙ
# ==========================================

class FileLoader:
    """Умный загрузчик файлов с автоопределением кодировки"""

    ENCODINGS = ['utf-8', 'windows-1251', 'cp1251', 'koi8-r']

    @staticmethod
    def load_lines(filename: str) -> Optional[List[str]]:
        """Загружает строки из файла с автоопределением кодировки"""
        if not os.path.exists(filename):
            return None

        for enc in FileLoader.ENCODINGS:
            try:
                with open(filename, 'r', encoding=enc) as f:
                    return [line.strip() for line in f if line.strip()]
            except UnicodeDecodeError:
                continue
            except Exception:
                continue

        # Последняя попытка с игнорированием ошибок
        try:
            with open(filename, 'r', encoding='utf-8', errors='ignore') as f:
                return [line.strip() for line in f if line.strip()]
        except:
            return None


# ==========================================
# 7. БЫСТРЫЙ ГЕНЕРАТОР СЛУЧАЙНЫХ ЧИСЕЛ
# ==========================================

class FastRandom:
    """Быстрый генератор случайных чисел (если нужно много random операций)"""

    def __init__(self, seed=None):
        import random
        self.random = random
        if seed:
            self.random.seed(seed)

    def choice(self, seq):
        """Быстрый выбор случайного элемента"""
        return seq[self.random.randint(0, len(seq) - 1)]

    def sample(self, population, k):
        """Быстрая выборка (для маленьких списков)"""
        if k > len(population):
            return population
        # Для маленьких списков используем простой метод
        if len(population) < 100:
            indices = set()
            while len(indices) < k:
                indices.add(self.random.randint(0, len(population) - 1))
            return [population[i] for i in indices]
        # Для больших - стандартный sample
        return self.random.sample(population, k)


# ==========================================
# 8. СОЗДАЁМ ЕДИНЫЙ ИНТЕРФЕЙС
# ==========================================

class Optimization:
    """Единый интерфейс для всех оптимизаций"""

    def __init__(self, stats_file: str = 'stats.json'):
        self.stats_cache = StatsCache(stats_file)
        self.words_cache = WordsFileCache()
        self.file_loader = FileLoader()
        self.random = FastRandom()

    def load_stats(self) -> Dict:
        """Загружает статистику с кешированием"""
        return self.stats_cache.load()

    def save_stats(self, data: Dict) -> bool:
        """Сохраняет статистику"""
        return self.stats_cache.save(data)

    def mark_stats_dirty(self):
        """Помечает статистику как изменённую"""
        self.stats_cache.mark_dirty()

    def load_words_file(self, filename: str) -> Optional[List[str]]:
        """Загружает файл со словами с кешированием"""
        return self.words_cache.get(filename, self.file_loader.load_lines)

    def clear_all_caches(self):
        """Очищает все кеши"""
        self.stats_cache.clear()
        self.words_cache.clear()

    def fast_choice(self, seq):
        """Быстрый random.choice"""
        return self.random.choice(seq)

    def fast_sample(self, population, k):
        """Быстрый random.sample"""
        return self.random.sample(population, k)


# Создаём глобальный экземпляр для использования во всём приложении
_optimization_instance = None


def get_optimization(stats_file: str = 'stats.json') -> Optimization:
    """Возвращает глобальный экземпляр оптимизации"""
    global _optimization_instance
    if _optimization_instance is None:
        _optimization_instance = Optimization(stats_file)
    return _optimization_instance


# ==========================================
# 9. ДЕКОРАТОР ДЛЯ АВТОМАТИЧЕСКОГО СОХРАНЕНИЯ
# ==========================================

def auto_save_stats(func):
    """Декоратор для автоматического сохранения статистики после выполнения функции"""

    def wrapper(self, *args, **kwargs):
        result = func(self, *args, **kwargs)
        if hasattr(self, 'save_data'):
            self.save_data()
        return result

    return wrapper
