# punct.py
# Модуль для обработки заданий по пунктуации (17-20) для Telegram-бота ЕГЭ

from telebot import types
import random
import os
from optimization import get_optimization

opt = get_optimization()
__all__ = ['register_handlers', 'send_punct_question']

# Глобальные переменные, устанавливаемые через register_handlers
_bot = None
_user_state = None
_load_data = None
_save_data = None


# ==========================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ==========================================

def ensure_task_data(data, task_num):
    """Гарантирует наличие структуры данных для задания с ВСЕМИ ключами"""
    task_num = str(task_num)
    if "tasks" not in data:
        data["tasks"] = {}

    # Базовая структура с ВСЕМИ ключами
    if task_num not in data["tasks"]:
        data["tasks"][task_num] = {
            "stats": {
                "total": 0,
                "correct": 0,
                "streak": 0,
                "best_streak": 0
            },
            "wrong_words": [],
            "completed_words": []
        }
    else:
        # Проверяем наличие всех ключей
        if "stats" not in data["tasks"][task_num]:
            data["tasks"][task_num]["stats"] = {
                "total": 0,
                "correct": 0,
                "streak": 0,
                "best_streak": 0
            }
        else:
            # Проверяем каждый ключ в stats
            stats = data["tasks"][task_num]["stats"]
            if "total" not in stats:
                stats["total"] = 0
            if "correct" not in stats:
                stats["correct"] = 0
            if "streak" not in stats:
                stats["streak"] = 0
            if "best_streak" not in stats:
                stats["best_streak"] = 0

        if "wrong_words" not in data["tasks"][task_num]:
            data["tasks"][task_num]["wrong_words"] = []
        if "completed_words" not in data["tasks"][task_num]:
            data["tasks"][task_num]["completed_words"] = []

    return data


def load_punct_words(task_num):
    """Загружает предложения с использованием кеша"""
    filename = f'punct{task_num}.txt'
    return opt.load_words_file(filename)


def generate_from_sentence(full_sentence, task_num='0'):
    """
    Преобразует предложение в задание с цифрами.

    Формат строки в файле:
      - / (слеш с пробелами вокруг) = правильная запятая по нужному правилу
      - обычные запятые = остаются как есть, не заменяются
    
    Алгоритм:
      1. Находим все позиции слешей — это правильные ответы
      2. Добавляем ложные цифры в умные места (перед союзами, между длинными словами)
         но НЕ сразу после обычной запятой
      3. Итого цифр: от 5 до 9 (зависит от длины предложения)
    """
    if not full_sentence:
        return None

    # Разбиваем на токены (слово или знак препинания)
    # Токен — это всё между пробелами
    parts = full_sentence.split(' ')
    # Убираем пустые части (двойные пробелы)
    parts = [p for p in parts if p]

    if len(parts) < 3:
        return None

    # Определяем позиции слешей (правильные ответы)
    # Слеш стоит как отдельный токен " / "
    correct_positions = set()  # индексы пробелов ПЕРЕД которыми стоит слеш
    clean_parts = []  # части без слешей

    i = 0
    while i < len(parts):
        if parts[i] == '/':
            # Слеш обозначает запятую между clean_parts[-1] и следующим словом
            # Запятая ставится ПОСЛЕ предыдущего слова
            if clean_parts:
                correct_positions.add(len(clean_parts) - 1)
        else:
            clean_parts.append(parts[i])
        i += 1

    if not clean_parts or len(clean_parts) < 3:
        return None

    if not correct_positions:
        return None  # нет ни одного слеша — некорректная строка

    # Если слешей больше 5 — случайно оставляем только 5 как правильные,
    # остальные превращаем обратно в обычные запятые (добавляем к слову)
    MAX_CORRECT = 5
    if len(correct_positions) > MAX_CORRECT:
        keep = set(random.sample(sorted(correct_positions), MAX_CORRECT))
        demoted = correct_positions - keep
        # Добавляем запятую к концу слова для демотированных позиций
        for pos in demoted:
            clean_parts[pos] = clean_parts[pos] + ','
        correct_positions = keep

    num_words = len(clean_parts)
    # Пробелы между словами: индекс пробела i = между словом i и i+1
    num_gaps = num_words - 1

    if num_gaps < 1:
        return None

    # Определяем целевое количество цифр в зависимости от длины предложения
    if num_words <= 8:
        target_total = 5
    elif num_words <= 14:
        target_total = 6
    elif num_words <= 20:
        target_total = 7
    elif num_words <= 28:
        target_total = 8
    else:
        target_total = 9

    # Кандидаты для ложных цифр — умные позиции
    # Союзы и частицы перед которыми реально можно ошибиться (общий список)
    TRAP_WORDS = {
        'и', 'а', 'но', 'или', 'что', 'как', 'когда', 'если', 'хотя',
        'потому', 'чтобы', 'однако', 'зато', 'либо', 'то', 'да', 'же',
        'ведь', 'тоже', 'также', 'притом', 'причём', 'словно', 'будто',
        'пока', 'после', 'прежде', 'раз', 'коль', 'ибо'
    }

    # Для задания 17 — слова которые похожи на вводные, но НЕ являются ими
    TRAP_WORDS_17 = {
        'мало-помалу', 'вдруг', 'будто', 'ведь', 'якобы', 'вряд', 'все-таки',
        'даже', 'едва-ли', 'исключительно', 'именно', 'почти', 'просто',
        'приблизительно', 'притом', 'поэтому', 'решительно', 'однажды',
        'словно', 'вот', 'примерно', 'авось', 'буквально', 'вдобавок',
        'вроде', 'наверняка', 'небось', 'непременно', 'определенно',
        'отчасти', 'поистине', 'по-прежнему', 'пусть', 'лишь', 'только',
        'иногда', 'между', 'все', 'тем', 'к', 'по', 'как'
    }

    if str(task_num) == '17':
        TRAP_WORDS = TRAP_WORDS | TRAP_WORDS_17

    trap_candidates = []  # список одиночных позиций (до ИЛИ после слова)
    trap_pairs = []       # пары позиций (до И после слова) для задания 17

    for idx in range(num_gaps):
        if idx in correct_positions:
            continue
        if clean_parts[idx].endswith(','):
            continue
        next_word = clean_parts[idx + 1]
        if next_word in {'.', '!', '?'} or next_word.endswith(('.', '!', '?')):
            continue

        next_word_clean = next_word.lower().rstrip('.,!?')
        is_trap_word = next_word_clean in TRAP_WORDS

        if str(task_num) == '17' and is_trap_word:
            # Определяем позицию ПОСЛЕ слова-ловушки
            after_idx = idx + 1  # пробел после слова-ловушки
            after_valid = (
                after_idx < num_gaps
                and after_idx not in correct_positions
                and not clean_parts[after_idx + 1 if after_idx + 1 < num_words else after_idx].endswith(('.', '!', '?'))
            )

            # Есть ли запятая или слеш перед словом-ловушкой
            comma_before = (
                idx in correct_positions
                or clean_parts[idx].endswith(',')
            )

            if comma_before:
                # Запятая уже есть до — ставим цифру только после
                if after_valid and after_idx not in correct_positions:
                    trap_candidates.insert(0, after_idx)
            else:
                # Нет ничего — ставим и до и после (пара)
                if after_valid and after_idx not in correct_positions:
                    trap_pairs.insert(0, (idx, after_idx))
                else:
                    trap_candidates.insert(0, idx)
        elif is_trap_word:
            trap_candidates.insert(0, idx)
        else:
            trap_candidates.append(idx)

    # Сколько ложных нужно
    n_correct = len(correct_positions)
    n_fake_needed = target_total - n_correct

    if n_correct >= 9:
        correct_positions = set(sorted(correct_positions)[:9])
        n_fake_needed = 0
    elif n_correct > target_total:
        n_fake_needed = 0

    n_fake_needed = max(0, n_fake_needed)

    # Набираем ложные позиции — сначала пары, потом одиночные
    fake_positions = set()
    for before_idx, after_idx in trap_pairs:
        if n_fake_needed <= 0:
            break
        if before_idx not in fake_positions and after_idx not in fake_positions:
            fake_positions.add(before_idx)
            fake_positions.add(after_idx)
            n_fake_needed -= 2

    if n_fake_needed > 0 and trap_candidates:
        take = min(n_fake_needed, len(trap_candidates))
        for c in trap_candidates[:take]:
            if c not in fake_positions:
                fake_positions.add(c)

    all_positions = sorted(correct_positions | fake_positions)

    # Итоговое количество должно быть от 5 до 9
    if len(all_positions) < 5:
        # Добираем любые оставшиеся позиции
        remaining = [idx for idx in range(num_gaps)
                     if idx not in all_positions
                     and not clean_parts[idx].endswith(',')
                     and not clean_parts[idx + 1].endswith(('.', '!', '?'))
                     and clean_parts[idx + 1] not in {'.', '!', '?'}]
        need_more = 5 - len(all_positions)
        if len(remaining) < need_more:
            return None  # предложение слишком короткое
        extra = random.sample(remaining, need_more)
        all_positions = sorted(set(all_positions) | set(extra))

    if len(all_positions) > 9:
        # Обрезаем, но правильные сохраняем в приоритете
        keep_correct = sorted(correct_positions)[:9]
        keep_fake = [p for p in all_positions if p not in correct_positions]
        slots_for_fake = 9 - len(keep_correct)
        all_positions = sorted(set(keep_correct) | set(keep_fake[:slots_for_fake]))

    # Строим скрытое предложение
    hidden_parts = []
    for i, word in enumerate(clean_parts):
        hidden_parts.append(word)
        if i < num_words - 1:
            if i in all_positions:
                num = all_positions.index(i) + 1
                hidden_parts.append(f" ({num}) ")
            else:
                hidden_parts.append(' ')

    hidden_text = ''.join(hidden_parts)

    # Правильные ответы — номера позиций которые соответствуют слешам
    answer_nums = []
    for rank, pos in enumerate(all_positions):
        if pos in correct_positions:
            answer_nums.append(str(rank + 1))

    answer_code = ''.join(sorted(answer_nums))

    if not answer_code:
        return None

    return hidden_text, answer_code, full_sentence


def generate_punct_task(task_num, sentences):
    """Генерирует случайное задание из списка предложений"""
    if not sentences:
        return None, None, None

    attempts = 0
    while attempts < 20:
        sentence = opt.fast_choice(sentences)
        res = generate_from_sentence(sentence, task_num)
        if res is not None:
            return res
        attempts += 1
    return None, None, None


# ==========================================
# КЛАВИАТУРЫ
# ==========================================

def punct_choice_kb():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("Задание 17", "Задание 18", "Задание 19", "Задание 20", "🏠 В меню")
    return markup


def task_kb():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("Тренировка", "Блиц", "Статистика", "⬅️ Назад к заданиям")
    return markup


def words_kb():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("Играть", "Работа над ошибками", "⬅️ Назад к заданиям")
    return markup

def send_punct_question(chat_id):
    """Отправляет вопрос по пунктуации (публичная функция)"""
    state = _user_state.get(chat_id)
    if not state:
        return
    num = state['task_num']
    u = _load_data(str(chat_id))
    u = ensure_task_data(u, num)
    _save_data(str(chat_id), u)

    sentences = load_punct_words(num)
    if not sentences:
        _bot.send_message(chat_id, f"Ошибка! Файл punct{num}.txt не найден или пуст.")
        return

    hidden, ans, full = generate_punct_task(num, sentences)
    if not hidden:
        _bot.send_message(chat_id, "Ошибка генерации задания.")
        return

    state['correct_ans'] = ans
    state['explanation'] = full

    total = state.get('total_count', state['remaining'])
    done = total - state['remaining'] + 1

    if not state.get('instruction_shown'):
        instruction = "📌 Укажи номера позиций, где должны стоять запятые. Введи цифры слитно, например: 13\n\n"
        state['instruction_shown'] = True
    else:
        instruction = ""

    _bot.send_message(chat_id,
                      f"📝 Задание №{num}  [{done} из {total}]\n"
                      f"{instruction}{hidden}",
                      reply_markup=types.ReplyKeyboardRemove())

# ==========================================
# ОБРАБОТЧИКИ
# ==========================================

def register_handlers(bot, user_state, load_data, save_data):
    global _bot, _user_state, _load_data, _save_data
    _bot = bot
    _user_state = user_state
    _load_data = load_data
    _save_data = save_data

    # ===== Вход в раздел Пунктуация =====
    @_bot.message_handler(func=lambda m: m.text == "Пунктуация")
    def punct_main(m):
        _bot.send_message(m.chat.id, "📂 Раздел ПУНКТУАЦИЯ. Выбери задание:",
                          reply_markup=punct_choice_kb())

    # ===== Выбор задания 17-20 =====
    @_bot.message_handler(func=lambda m: m.text in ["Задание 17", "Задание 18", "Задание 19", "Задание 20"])
    def select_punct_task(m):
        num = m.text.split()[1]
        _user_state[m.chat.id] = {'task_num': num}
        _bot.send_message(m.chat.id, f"🎯 Выбрано задание {num}", reply_markup=task_kb())

    # ===== Назад к списку заданий =====
    @_bot.message_handler(func=lambda m: m.text == "⬅️ Назад к заданиям")
    def back_to_punct_choice(m):
        _bot.send_message(m.chat.id, "Выбери задание:", reply_markup=punct_choice_kb())

    # ===== СТАТИСТИКА =====
    @_bot.message_handler(func=lambda m: m.text == "Статистика" and
                                         _user_state.get(m.chat.id, {}).get('task_num') in ['17', '18', '19', '20'])
    def punct_stats_handler(m):
        cid = m.chat.id
        num = _user_state[cid]['task_num']
        u = _load_data(str(cid))
        u = ensure_task_data(u, num)
        t_data = u["tasks"][num]

        total = t_data["stats"]["total"]
        correct = t_data["stats"]["correct"]
        perc = int(correct / total * 100) if total > 0 else 0
        words_done = len(t_data.get("completed_words", []))

        text = (f"📊 СТАТИСТИКА (Задание {num})\n"
                f"──────────────────\n"
                f"🎯 Тренировка:\n"
                f"   • Решено: {total}\n"
                f"   • Верно: {correct} ({perc}%)\n\n"
                f"⚡ Блиц:\n"
                f"   • Выучено: {words_done}\n"
                f"   • Серия: {t_data['stats'].get('streak', 0)} (Лучшая: {t_data['stats'].get('best_streak', 0)})")

        _bot.send_message(cid, text)

    # ===== ТРЕНИРОВКА =====
    @_bot.message_handler(func=lambda m: m.text == "Тренировка" and
                                         _user_state.get(m.chat.id, {}).get('task_num') in ['17', '18', '19', '20'])
    def punct_train_init(m):
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add("1", "3", "5", "10", "Назад")
        _bot.send_message(m.chat.id, "Количество заданий?", reply_markup=markup)
        _user_state[m.chat.id]['mode'] = 'awaiting_punct_count'

    @_bot.message_handler(func=lambda m: m.text in ["1", "3", "5", "10"] and
                                         _user_state.get(m.chat.id, {}).get('mode') == 'awaiting_punct_count')
    def punct_train_start(m):
        cid = m.chat.id
        count = int(m.text)
        _user_state[cid].update({
            'mode': 'punct_train',
            'remaining': count,
            'total_count': count,
            'session_score': 0,
            'instruction_shown': False
        })
        send_punct_question(cid)

    @_bot.message_handler(func=lambda m: _user_state.get(m.chat.id, {}).get('mode') == 'punct_train')
    def handle_punct_train_answer(m):
        cid = m.chat.id
        state = _user_state[cid]
        user_ans = "".join(sorted(set(filter(str.isdigit, m.text))))

        uid = str(cid)
        u = _load_data(uid)
        num = state['task_num']
        u = ensure_task_data(u, num)
        t_data = u["tasks"][num]

        t_data["stats"]["total"] += 1

        if user_ans == state['correct_ans']:
            t_data["stats"]["correct"] += 1
            state['session_score'] += 1
            _bot.send_message(cid, "✅ Правильно!")
        else:
            _bot.send_message(cid,
                              f"❌ Ошибка!\nПравильный ответ: {state['correct_ans']}\n\nРазбор:\n{state['explanation']}")

        _save_data(uid, u)

        state['remaining'] -= 1
        if state['remaining'] > 0:
            send_punct_question(cid)
        else:
            _bot.send_message(cid, f"🏁 Тренировка окончена.\nРезультат: {state['session_score']} из {state['total_count']}",
                              reply_markup=task_kb())
            state.pop('mode', None)

    # ===== РЕЖИМ «БЛИЦ» (игра и работа над ошибками) =====
    @_bot.message_handler(func=lambda m: m.text == "Блиц" and
                                         _user_state.get(m.chat.id, {}).get('task_num') in ['17', '18', '19', '20'])
    def punct_words_init(m):
        _user_state[m.chat.id].pop('blitz_instruction_shown', None)
        _bot.send_message(m.chat.id, "⚡ Режим Блиц — угадай где ставить запятые!", reply_markup=words_kb())

    @_bot.message_handler(func=lambda m: m.text == "Играть" and
                                         _user_state.get(m.chat.id, {}).get('task_num') in ['17', '18', '19', '20'])
    def punct_game_start(m):
        cid = m.chat.id
        num = _user_state[cid]['task_num']
        uid = str(cid)
        u = _load_data(uid)
        u = ensure_task_data(u, num)

        sentences = load_punct_words(num)
        if not sentences:
            _bot.send_message(cid, f"Файл punct{num}.txt пуст!")
            return

        completed = u["tasks"][num].get("completed_words", [])
        available = [s for s in sentences if s not in completed]
        if not available:
            u["tasks"][num]["completed_words"] = []
            _save_data(uid, u)
            _bot.send_message(cid, "🏆 Ты прошел все предложения! Начинаем заново.")
            available = sentences

        full = random.choice(available)
        res = generate_from_sentence(full, num)
        if res is None:
            _bot.send_message(cid, "Ошибка генерации задания.")
            return
        hidden, ans, _ = res
        obj = {"hidden": hidden, "full": full, "answer": ans}

        first = _user_state[cid].get('blitz_instruction_shown', False)
        _user_state[cid].update({
            'mode': 'punct_word_game',
            'word_obj': obj,
            'blitz_instruction_shown': True
        })

        instruction = "" if first else "📌 Введи номера позиций, где должны стоять запятые:\n\n"
        _bot.send_message(cid, f"{instruction}{hidden}", reply_markup=types.ReplyKeyboardRemove())

    @_bot.message_handler(func=lambda m: m.text == "Работа над ошибками" and
                                         _user_state.get(m.chat.id, {}).get('task_num') in ['17', '18', '19', '20'])
    def punct_correction_start(m):
        cid = m.chat.id
        num = _user_state[cid]['task_num']
        uid = str(cid)
        u = _load_data(uid)
        u = ensure_task_data(u, num)

        wrong_list = u["tasks"][num].get("wrong_words", [])
        if not wrong_list:
            _bot.send_message(cid, "✅ Список ошибок пуст! Молодец.", reply_markup=words_kb())
            return
        target = random.choice(wrong_list)
        _user_state[cid].update({'mode': 'punct_correction', 'word_obj': target})
        _bot.send_message(cid, f"Исправь ошибки в предложении:\n\n{target['hidden']}",
                          reply_markup=types.ReplyKeyboardRemove())

    @_bot.message_handler(
        func=lambda m: _user_state.get(m.chat.id, {}).get('mode') in ['punct_word_game', 'punct_correction'])
    def handle_punct_game_answer(m):
        cid = m.chat.id
        state = _user_state[cid]
        mode = state['mode']
        user_ans = "".join(sorted(set(filter(str.isdigit, m.text))))
        obj = state['word_obj']
        correct = obj['answer']

        uid = str(cid)
        u = _load_data(uid)
        num = state['task_num']
        u = ensure_task_data(u, num)
        t_data = u["tasks"][num]

        if user_ans == correct:
            _bot.send_message(cid, "✅ Верно!")
            if mode == 'punct_word_game':
                t_data["stats"]["streak"] = t_data["stats"].get("streak", 0) + 1
                if t_data["stats"]["streak"] > t_data["stats"].get("best_streak", 0):
                    t_data["stats"]["best_streak"] = t_data["stats"]["streak"]
                if obj['full'] not in t_data['completed_words']:
                    t_data['completed_words'].append(obj['full'])
                _save_data(uid, u)
                punct_game_start(m)
            else:
                t_data["wrong_words"] = [w for w in t_data["wrong_words"] if w['full'] != obj['full']]
                _save_data(uid, u)
                _bot.send_message(cid, "Предложение исправлено!", reply_markup=words_kb())
                state.pop('mode', None)
        else:
            _bot.send_message(cid, f"❌ Ошибка! Правильно: {obj['full']}")
            if mode == 'punct_word_game':
                t_data["stats"]["streak"] = 0
                if not any(w['full'] == obj['full'] for w in t_data['wrong_words']):
                    t_data['wrong_words'].append(obj)
                _save_data(uid, u)
                _bot.send_message(cid, "Серия прервана. Предложение ушло в «Работу над ошибками».",
                                  reply_markup=words_kb())
                state.pop('mode', None)
            else:
                _bot.send_message(cid, "Попробуй еще раз позже.", reply_markup=words_kb())
                state.pop('mode', None)

    # ===== Назад из меню «Блиц» =====
    @_bot.message_handler(func=lambda m: m.text == "⬅️ Назад к заданиям" and
                                         _user_state.get(m.chat.id, {}).get('task_num') in ['17', '18', '19', '20'])
    def back_from_words(m):
        cid = m.chat.id
        if cid in _user_state:
            _user_state[cid].pop('mode', None)
        _bot.send_message(cid, "Меню задания:", reply_markup=task_kb())
