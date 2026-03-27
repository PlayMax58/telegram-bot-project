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


def generate_from_sentence(full_sentence):
    """
    Преобразует полное предложение (с запятыми) в задание с цифрами.
    Возвращает (hidden_text, answer_code, full_sentence) или None, если не удалось.
    """
    if not full_sentence:
        return None

    # Разбиваем по пробелам, сохраняя знаки при словах
    parts = full_sentence.split(' ')
    words = []
    comma_after = []  # True, если после слова была запятая
    for part in parts:
        if part.endswith(','):
            words.append(part[:-1])  # убираем запятую
            comma_after.append(True)
        else:
            words.append(part)
            comma_after.append(False)

    num_spaces = len(words) - 1
    if num_spaces < 5:
        # Нельзя разместить 5 цифр – предложение слишком короткое
        return None

    # Индексы пробелов (от 0 до num_spaces-1)
    all_indices = list(range(num_spaces))
    correct_indices = [i for i in range(num_spaces) if comma_after[i]]

    if len(correct_indices) > 5:
        return None  # слишком много правильных ответов

    # Выбираем ровно 5 пробелов для размещения цифр
    selected = set(correct_indices)
    if len(selected) < 5:
        candidates = [i for i in all_indices if i not in selected]
        needed = 5 - len(selected)
        if len(candidates) >= needed:
            selected.update(random.sample(candidates, needed))
        else:
            # Не хватает кандидатов
            return None

    sorted_indices = sorted(selected)

    # Строим скрытое предложение
    hidden_parts = []
    for i, word in enumerate(words):
        hidden_parts.append(word)
        if i < len(words) - 1:  # не последнее слово
            if i in sorted_indices:
                num = sorted_indices.index(i) + 1
                hidden_parts.append(f" ({num}) ")
            else:
                hidden_parts.append(" ")
        # последнее слово – ничего не добавляем

    hidden_text = ''.join(hidden_parts)

    # Формируем правильный ответ (номера цифр, соответствующие запятым)
    answer_nums = [str(idx + 1) for idx, pos in enumerate(sorted_indices) if pos in correct_indices]
    answer_code = ''.join(sorted(answer_nums))  # уже по возрастанию

    return hidden_text, answer_code, full_sentence


def generate_punct_task(task_num, sentences):
    """Генерирует случайное задание из списка предложений"""
    if not sentences:
        return None, None, None

    attempts = 0
    while attempts < 20:
        # Было: sentence = random.choice(sentences)
        sentence = opt.fast_choice(sentences)  # новая строка
        res = generate_from_sentence(sentence)
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
        res = generate_from_sentence(full)
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
