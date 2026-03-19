import telebot
import random
import os
from telebot import types
from apscheduler.schedulers.background import BackgroundScheduler
from dotenv import load_dotenv
import punct
from optimization import get_optimization

load_dotenv()

# ==========================================
# НАСТРОЙКИ
# ==========================================
bot = telebot.TeleBot(os.getenv("BOT_TOKEN"))
SHARED_DIR = os.environ.get('SHARED_DIR', '/app/shared')
STATS_FILE = os.path.join(SHARED_DIR, 'stats.json')

opt = get_optimization(STATS_FILE)

# Настройки для задания 10 (Группы правил)
GROUP_ZS = ['з', 'с']
GROUP_EI = ['е', 'и']
GROUP_YI = ['ы', 'и']
GROUPS_11 = [['е', 'и'], ['о', 'а'], ['о', 'е']]
GROUPS_12 = [['е', 'и'], ['у', 'а'], ['ю', 'я']]

scheduler = BackgroundScheduler()
scheduler.start()

# ==========================================
# СИСТЕМА ДАННЫХ (ЗАГРУЗКА И СОХРАНЕНИЕ)
# ==========================================
def load_data():
    """Загружает данные с использованием кеша"""
    return opt.load_stats()  # Вместо загрузки из файла каждый раз


def save_data(data):
    """Сохраняет данные с обновлением кеша"""
    opt.save_stats(data)  # Вместо прямой записи в файл


# ==========================================
# ЛОГИКА СЛОВАРЕЙ И ГЕНЕРАЦИИ
# ==========================================
def load_words(task_num):
    """Загружает слова с использованием кеша"""
    filename = f'words{task_num}.txt'

    # Используем кешированную загрузку
    lines = opt.load_words_file(filename)

    if not lines:
        return None, None

    words_dict = {}
    plain_words = []

    for line in lines:
        word = line.strip()
        if not word: continue
        char = next((c.lower() for c in word if c.isupper()), None)
        if char:
            hidden = word.replace(char.upper(), "..")
            full = word.replace(char.upper(), char.lower())
            obj = {"hidden": hidden, "full": full, "letter": char.lower()}

            if char.lower() not in words_dict:
                words_dict[char.lower()] = []
            words_dict[char.lower()].append(obj)
            plain_words.append(obj)

    return words_dict, plain_words

def generate_task(task_num):
    db, _ = load_words(task_num)
    if not db: return f"Ошибка! Файл words{task_num}.txt не найден или пуст.", "", ""

    # Проверка, хватит ли слов вообще
    total_words = sum(len(v) for v in db.values())
    if total_words < 15: return "Слишком мало слов в файле (нужно минимум 15 уникальных).", "", ""

    num_correct = random.randint(2, 4)
    correct_indices = random.sample(range(1, 6), num_correct)

    rows = []
    rows_with_answers = []
    task_used = set()

    for i in range(1, 6):
        # === ЛОГИКА ГРУППИРОВКИ БУКВ ===
        if str(task_num) == "10":
            # Используем твои существующие константы для 10 задания
            rule_group = random.choice([GROUP_ZS, GROUP_EI, GROUP_YI])
        elif str(task_num) == "11":
            # Логика для 11 задания: Е/И, О/А или О/Е
            rule_group = random.choice(GROUPS_11)
        elif str(task_num) == "12":
            # Логика для 12 задания:
            rule_group = random.choice(GROUPS_12)
        else:
            # Новая логика для 9 задания: А-О, Е-И, Е-Я
            rule_group = random.choice([['а', 'о'], ['е', 'и'], ['е', 'я']])

        # Фильтруем ключи словаря по выбранной группе
        current_pool_keys = [k for k in rule_group if k in db]

        if not current_pool_keys:
            # Фолбэк: если в файле нет слов из выбранной группы, берем все ключи
            current_pool_keys = list(db.keys())

        if i in correct_indices:
            # --- ПРАВИЛЬНЫЙ РЯД (Все буквы одинаковые) ---
            valid_letters = [l for l in current_pool_keys if
                             len([w for w in db[l] if w['hidden'] not in task_used]) >= 3]

            if not valid_letters:
                valid_letters = [l for l in db.keys() if len(db[l]) >= 3]

            if not valid_letters: return "Критическая нехватка слов для генерации!", "", ""

            target_letter = random.choice(valid_letters)
            pool = [w for w in db[target_letter] if w['hidden'] not in task_used]
            if len(pool) < 3: pool = db[target_letter]

            selected = random.sample(pool, 3)
        else:
            # --- НЕПРАВИЛЬНЫЙ РЯД (Ловушка внутри одной группы) ---
            pool = []
            for letter in current_pool_keys:
                pool.extend([w for w in db[letter] if w['hidden'] not in task_used])

            if len(pool) < 3:
                pool = []
                for k in db: pool.extend([w for w in db[k] if w['hidden'] not in task_used])

            if len(pool) < 3: return "Мало слов для ловушек!", "", ""

            selected = random.sample(pool, 3)

            # Проверка на одинаковые буквы (чтобы ловушка была ловушкой)
            attempts = 0
            # Условие перегенерации: если все буквы одинаковые И в группе больше одной доступной буквы
            while len(set(w['letter'] for w in selected)) == 1 and attempts < 10 and len(current_pool_keys) > 1:
                selected = random.sample(pool, 3)
                attempts += 1

        # Формируем строки
        row_str = f"{i}) " + ", ".join([w['hidden'] for w in selected])
        ans_str = f"{i}) " + ", ".join([w['full'] for w in selected])

        rows.append(row_str)
        rows_with_answers.append(ans_str)
        task_used.update([w['hidden'] for w in selected])

    ans_code = "".join(sorted([str(x) for x in correct_indices]))
    full_explanation = "\n".join(rows_with_answers)

    return "\n".join(rows), ans_code, full_explanation


# ==========================================
# ИНТЕРФЕЙС И СОСТОЯНИЯ
# ==========================================
user_state = {}


# Структура user_state:
# { chat_id: { 'task_num': '9', 'mode': 'train'/'word_game', 'remaining': 5, ... } }

def main_kb():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("Орфография", "Пунктуация") # Наша главная категория
    markup.row("📅 Планы")
    return markup

def ortho_kb():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("Задание 9", "Задание 10", "Задание 11", "Задание 12", "🏠 В меню")
    return markup

def punct_choice_kb():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("Задание 17", "Задание 18", "Задание 19", "Задание 20", "🏠 В меню")
    return markup


def task_kb():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("Тренировка", "Слова", "Статистика", "⬅️ Назад к заданиям")
    return markup


def words_kb():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("Играть", "Работа над ошибками", "Назад")
    return markup

@bot.message_handler(func=lambda m: m.text == "Орфография")
def ortho_main(m):
    bot.send_message(m.chat.id, "📂 Раздел ОРФОГРАФИЯ. Выбери задание:", reply_markup=ortho_kb())

@bot.message_handler(func=lambda m: m.text == "🏠 В меню")
def to_main(m):
    user_state.pop(m.chat.id, None)
    bot.send_message(m.chat.id, "Главное меню:", reply_markup=main_kb())

@bot.message_handler(func=lambda m: m.text.startswith("Задание "))
def sel_t(m):
    num = m.text.split()[1]
    user_state[m.chat.id] = {'task_num': num}
    bot.send_message(m.chat.id, f"🎯 Выбрано задание {num}", reply_markup=task_kb())

@bot.message_handler(func=lambda m: m.text == "⬅️ Назад к заданиям")
def back_to_ortho(m):
    # Проверяем, из какого раздела пришёл пользователь
    if m.chat.id in user_state and user_state[m.chat.id].get('task_num') in ['17','18','19','20']:
        # Возвращаемся в пунктуацию
        bot.send_message(m.chat.id, "Выбери задание:", reply_markup=punct_choice_kb())
    else:
        # Возвращаемся в орфографию
        bot.send_message(m.chat.id, "Выбери задание:", reply_markup=ortho_kb())


# --- ВЫБОР ЗАДАНИЯ ---
@bot.message_handler(func=lambda m: m.text in ["Задание 9", "Задание 10", "Задание 11", "Задание 12"])
def menu_task_select(m):
    task_num = m.text.split()[1]  # "9" или "10"
    user_state[m.chat.id] = {'task_num': task_num}
    bot.send_message(m.chat.id, f"✅ Выбрано задание {task_num}.\nЧто будем делать?", reply_markup=task_kb())


@bot.message_handler(func=lambda m: m.text == "Назад")
def back_handler(m):
    # Если мы в подменю (слова), возвращаемся в меню задания
    if m.chat.id in user_state and 'mode' in user_state[m.chat.id]:
        # Сбрасываем режим, но оставляем номер задания
        del user_state[m.chat.id]['mode']
        bot.send_message(m.chat.id, "Меню задания:", reply_markup=task_kb())
    else:
        # Иначе в главное меню
        if m.chat.id in user_state: del user_state[m.chat.id]
        bot.send_message(m.chat.id, "Главное меню:", reply_markup=main_kb())



# ==========================================
# СТАТИСТИКА
# ==========================================
@bot.message_handler(func=lambda m: m.text == "Статистика")
def stats_handler(m):
    if m.chat.id not in user_state:
        return bot.send_message(m.chat.id, "Сначала выберите задание!", reply_markup=main_kb())

    num = user_state[m.chat.id]['task_num']
    data = load_data()

    # Проверяем наличие задания в данных
    if num not in data["tasks"]:
        # Создаём структуру с ВСЕМИ ключами
        data["tasks"][num] = {
            "stats": {
                "total": 0,
                "correct": 0,
                "streak": 0,
                "best_streak": 0
            },
            "wrong_words": [],
            "completed_words": []
        }
        save_data(data)

    t_data = data["tasks"][num]

    # Дополнительная проверка структуры stats
    if "best_streak" not in t_data["stats"]:
        t_data["stats"]["best_streak"] = 0

    total = t_data["stats"]["total"]
    correct = t_data["stats"]["correct"]
    perc = int(correct / total * 100) if total > 0 else 0
    words_done = len(t_data.get("completed_words", []))

    text = (f"📊 СТАТИСТИКА (Задание {num})\n"
            f"──────────────────\n"
            f"🎯 Тренировка (неделя):\n"
            f"   • Решено: {total}\n"
            f"   • Верно: {correct} ({perc}%)\n\n"
            f"🧠 Режим «Слова»:\n"
            f"   • Выучено: {words_done}\n"
            f"   • Серия: {t_data['stats']['streak']} (Лучшая: {t_data['stats']['best_streak']})")

    bot.send_message(m.chat.id, text)
# ==========================================
# РЕЖИМ: ТРЕНИРОВКА
# ==========================================
@bot.message_handler(func=lambda m: m.text == "Тренировка")
def train_init(m):
    if m.chat.id not in user_state:
        return bot.send_message(m.chat.id, "Сначала выберите задание!", reply_markup=main_kb())

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("1", "3", "5", "10", "Назад")
    bot.send_message(m.chat.id, "Количество заданий?", reply_markup=markup)


@bot.message_handler(func=lambda m: m.text in ["1", "3", "5", "10"])
def train_start(m):
    if m.chat.id not in user_state: return

    count = int(m.text)
    user_state[m.chat.id].update({
        'mode': 'train',
        'remaining': count,
        'session_score': 0
    })
    send_train_question(m.chat.id)


def send_train_question(chat_id):
    state = user_state.get(chat_id)
    if not state:
        return
    
    num = state['task_num']
    text, ans, full = generate_task(num)
    
    # Сохраняем правильный ответ и объяснение
    state['correct_ans'] = ans
    state['explanation'] = full
    
    # Сохраняем начальное количество для статистики
    if 'initial_remaining' not in state:
        state['initial_remaining'] = state.get('remaining', 0)
    
    bot.send_message(chat_id,
                     f"📝 Задание №{num} (Осталось: {state['remaining']})\n\n{text}",
                     reply_markup=types.ReplyKeyboardRemove())

# ==========================================
# РЕЖИМ: СЛОВА (ИГРА И ОШИБКИ)
# ==========================================
@bot.message_handler(func=lambda m: m.text == "Слова")
def words_init(m):
    if m.chat.id not in user_state: return bot.send_message(m.chat.id, "Выберите задание!")
    bot.send_message(m.chat.id, "Режим запоминания слов.", reply_markup=words_kb())


@bot.message_handler(func=lambda m: m.text == "Играть")
def game_start(m):
    if m.chat.id not in user_state: return

    num = user_state[m.chat.id]['task_num']
    data = load_data()

    # Загружаем слова
    _, plain_list = load_words(num)
    if not plain_list: return bot.send_message(m.chat.id, f"Файл words{num}.txt пуст!")

    # Фильтруем уже выученные
    completed = data["tasks"][num]["completed_words"]
    available = [w for w in plain_list if w['hidden'] not in completed]

    if not available:
        # Сброс, если все выучил
        data["tasks"][num]["completed_words"] = []
        save_data(data)
        bot.send_message(m.chat.id, "🏆 Ты прошел весь словарь! Начинаем заново.")
        available = plain_list

    target = random.choice(available)
    user_state[m.chat.id].update({
        'mode': 'word_game',
        'word_obj': target
    })

    bot.send_message(m.chat.id, f"Вставь пропущенную букву:\n\n{target['hidden']}",
                     reply_markup=types.ReplyKeyboardRemove())


@bot.message_handler(func=lambda m: m.text == "Работа над ошибками")
def correction_start(m):
    if m.chat.id not in user_state: return
    num = user_state[m.chat.id]['task_num']
    data = load_data()

    wrong_list = data["tasks"][num]["wrong_words"]
    if not wrong_list:
        return bot.send_message(m.chat.id, "✅ Список ошибок пуст! Молодец.", reply_markup=words_kb())

    target = random.choice(wrong_list)
    user_state[m.chat.id].update({
        'mode': 'correction',
        'word_obj': target
    })
    bot.send_message(m.chat.id, f"Исправь ошибку:\n\n{target['hidden']}", reply_markup=types.ReplyKeyboardRemove())


# ==========================================
# ПЛАНЫ (С ПОЛНОЙ ЛОГИКОЙ)
# ==========================================
@bot.message_handler(func=lambda m: m.text == "📅 Планы")
def plans_main(m):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("Создать план", "Удалить план", "Назад")
    bot.send_message(m.chat.id, "Настройка ежедневных заданий:", reply_markup=markup)


# Сначала определяем функцию p4_finish (самую глубокую)
def p4_finish(m, task_num, count):
    """Обрабатывает ввод времени и сохраняет план"""
    try:
        time_str = m.text.strip().replace(' ', '')

        if ':' not in time_str:
            raise ValueError("Отсутствует двоеточие")

        parts = time_str.split(':')
        if len(parts) != 2:
            raise ValueError("Неверный формат")

        h = parts[0].strip()
        mn = parts[1].strip()

        if not h.isdigit() or not mn.isdigit():
            raise ValueError("Часы и минуты должны быть числами")

        hour = int(h)
        minute = int(mn)

        if hour < 0 or hour > 23:
            raise ValueError("Часы должны быть от 0 до 23")
        if minute < 0 or minute > 59:
            raise ValueError("Минуты должны быть от 0 до 59")

        time_formatted = f"{hour:02d}:{minute:02d}"

        # Сохранение в базу
        data = load_data()
        data["plans"][str(m.chat.id)] = {
            "time": time_formatted,
            "count": count,
            "task": task_num
        }
        save_data(data)

        # Настройка планировщика
        job_id = f"job_{m.chat.id}"
        if scheduler.get_job(job_id):
            scheduler.remove_job(job_id)

        scheduler.add_job(execute_plan, 'cron', hour=hour, minute=minute,
                          args=[m.chat.id, count, task_num], id=job_id)

        task_type = "пунктуация" if task_num in ['17', '18', '19', '20'] else "орфография"

        bot.send_message(m.chat.id,
                         f"✅ План успешно сохранён!\n"
                         f"📚 Задание: {task_num} ({task_type})\n"
                         f"📊 Количество: {count}\n"
                         f"⏰ Время: {time_formatted}\n\n"
                         f"Я буду присылать напоминания каждый день в это время.",
                         reply_markup=main_kb())

    except ValueError as e:
        error_text = str(e) if str(e) else "Неверный формат времени"
        bot.send_message(m.chat.id,
                         f"❌ Ошибка: {error_text}\n\n"
                         f"Пожалуйста, введите время в формате ЧЧ:ММ\n"
                         f"Например: 09:00, 15:30, 20:45",
                         reply_markup=main_kb())
    except Exception as e:
        bot.send_message(m.chat.id,
                         f"❌ Непредвиденная ошибка. Попробуйте ещё раз.\n"
                         f"Формат: ЧЧ:ММ (например, 14:30)",
                         reply_markup=main_kb())
        print(f"Ошибка в p4_finish: {e}")


# Потом определяем p3_time, которая использует p4_finish
def p3_time(m, task_num):
    """Обрабатывает ввод количества заданий"""
    if not m.text.isdigit():
        bot.send_message(m.chat.id, "❌ Нужно ввести число! Попробуйте снова.",
                         reply_markup=main_kb())
        return

    count = int(m.text)
    if count < 1 or count > 10:
        bot.send_message(m.chat.id, "❌ Число должно быть от 1 до 10. Попробуйте снова.",
                         reply_markup=main_kb())
        return

    msg = bot.send_message(m.chat.id,
                           "🕐 В какое время присылать напоминание?\n"
                           "Введите время в формате **ЧЧ:ММ**, например:\n"
                           "• 09:00 - утром\n"
                           "• 15:30 - днём\n"
                           "• 20:45 - вечером")
    # Здесь используем p4_finish, которая уже определена выше
    bot.register_next_step_handler(msg, p4_finish, task_num, count)


# Затем определяем p2_count, которая использует p3_time
def p2_count(m):
    """Обрабатывает выбор задания"""
    if m.text not in ["Задание 9", "Задание 10", "Задание 11", "Задание 12",
                      "Задание 17", "Задание 18", "Задание 19", "Задание 20"]:
        bot.send_message(m.chat.id, "❌ Нужно выбрать задание из меню.", reply_markup=main_kb())
        return

    task_num = m.text.split()[1]
    msg = bot.send_message(m.chat.id,
                           f"Сколько заданий №{task_num} присылать? (Введите число от 1 до 10)",
                           reply_markup=types.ReplyKeyboardRemove())
    # Здесь используем p3_time, которая уже определена выше
    bot.register_next_step_handler(msg, p3_time, task_num)


# И только потом определяем обработчик, который запускает всю цепочку
@bot.message_handler(func=lambda m: m.text == "Создать план")
def p1_task(m):
    """Начинает создание плана"""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("Задание 9", "Задание 10", "Задание 11", "Задание 12",
               "Задание 17", "Задание 18", "Задание 19", "Задание 20")
    msg = bot.send_message(m.chat.id, "Для какого задания создать план?", reply_markup=markup)
    # Здесь используем p2_count, которая уже определена выше
    bot.register_next_step_handler(msg, p2_count)


# Функция execute_plan (должна быть определена где-то выше или ниже, но до использования)
def execute_plan(chat_id, count, task_num):
    """Выполняет запланированную тренировку"""
    try:
        if task_num in ['17', '18', '19', '20']:
            # Для пунктуации
            user_state[chat_id] = {
                'task_num': task_num,
                'mode': 'punct_train',
                'remaining': count,
                'session_score': 0,
                'section': 'punct'
            }
            bot.send_message(chat_id, f"⏰ Время тренировки по ПУНКТУАЦИИ! Задание {task_num}.")

            # Импортируем функцию для отправки вопроса
            try:
                from punct import send_punct_question
                send_punct_question(chat_id)
            except ImportError as e:
                bot.send_message(chat_id, "❌ Ошибка: модуль пунктуации не загружен.")
                print(f"Ошибка импорта punct.send_punct_question: {e}")
            except Exception as e:
                bot.send_message(chat_id, "❌ Ошибка при отправке задания.")
                print(f"Ошибка в send_punct_question: {e}")

        else:
            # Для орфографии
            user_state[chat_id] = {
                'task_num': task_num,
                'mode': 'train',
                'remaining': count,
                'session_score': 0,
                'section': 'ortho'
            }
            bot.send_message(chat_id, f"⏰ Время тренировки по ОРФОГРАФИИ! Задание {task_num}.")
            send_train_question(chat_id)

    except Exception as e:
        print(f"❌ Ошибка выполнения плана для {chat_id}: {e}")
        import traceback
        traceback.print_exc()


@bot.message_handler(func=lambda m: m.text == "Удалить план")
def del_plan(m):
    """Удаляет план пользователя"""
    data = load_data()
    cid = str(m.chat.id)

    if cid in data["plans"]:
        plan = data["plans"][cid]
        task_type = "пунктуация" if plan['task'] in ['17', '18', '19', '20'] else "орфография"

        del data["plans"][cid]
        save_data(data)

        job_id = f"job_{cid}"
        if scheduler.get_job(job_id):
            scheduler.remove_job(job_id)

        bot.send_message(m.chat.id,
                         f"✅ План успешно удалён.\n"
                         f"Было настроено: задание {plan['task']} ({task_type}) в {plan['time']}",
                         reply_markup=main_kb())
    else:
        bot.send_message(m.chat.id,
                         "❌ У вас нет активных планов.\n"
                         "Чтобы создать план, нажмите 'Создать план'.",
                         reply_markup=main_kb())


# ==========================================
# ОБРАБОТЧИК ОТВЕТОВ (СЕРДЦЕ БОТА)
# ==========================================
@bot.message_handler(func=lambda m: True)
def global_answer_handler(m):
    cid = m.chat.id
    
    # 1. ПРОВЕРКА СОСТОЯНИЯ
    if cid not in user_state:
        bot.send_message(cid, "Используйте меню:", reply_markup=main_kb())
        return
    
    # 2. ПРОВЕРКА ПУНКТУАЦИИ (пропускаем)
    if user_state[cid].get('task_num') in ['17','18','19','20']:
        return
    
    state = user_state[cid]
    mode = state.get('mode')
    
    # 3. ЕСЛИ РЕЖИМА НЕТ - ИГНОРИРУЕМ
    if not mode:
        return
    
    # 4. ЗАГРУЗКА ДАННЫХ
    data = load_data()
    task_num = state['task_num']
    t_data = data["tasks"][task_num]
    
    # 5. ОБРАБОТКА ТРЕНИРОВКИ
    if mode == 'train':
        # Получаем ответ пользователя (только цифры)
        user_digits = ''.join([c for c in m.text if c.isdigit()])
        user_answer = ''.join(sorted(set(user_digits)))
        
        correct_answer = state.get('correct_ans', '')
        
        # Обновляем статистику
        t_data["stats"]["total"] += 1
        
        if user_answer == correct_answer:
            t_data["stats"]["correct"] += 1
            state['session_score'] = state.get('session_score', 0) + 1
            bot.send_message(cid, "✅ Правильно!")
        else:
            bot.send_message(cid, f"❌ Ошибка! Правильный ответ: {correct_answer}")
        
        # Сохраняем
        save_data(data)
        
        # Следующий вопрос или конец
        state['remaining'] = state.get('remaining', 1) - 1
        
        if state['remaining'] > 0:
            # Отправляем следующий вопрос
            text, ans, full = generate_task(task_num)
            state['correct_ans'] = ans
            state['explanation'] = full
            bot.send_message(cid, f"📝 Задание №{task_num} (Осталось: {state['remaining']})\n\n{text}")
        else:
            bot.send_message(cid, f"🏁 Тренировка окончена. Результат: {state.get('session_score', 0)}", reply_markup=task_kb())
            del state['mode']
            if 'session_score' in state: del state['session_score']
            if 'remaining' in state: del state['remaining']
            if 'correct_ans' in state: del state['correct_ans']
    
    # 6. ОБРАБОТКА ИГРЫ СО СЛОВАМИ
    elif mode == 'word_game':
        word_obj = state.get('word_obj')
        if not word_obj:
            bot.send_message(cid, "Ошибка. Начните игру заново.")
            del state['mode']
            return
        
        user_letter = m.text.strip().lower()
        
        if user_letter == word_obj['letter']:
            bot.send_message(cid, "✅ Верно!")
            
            # Обновляем статистику
            t_data["stats"]["streak"] = t_data["stats"].get("streak", 0) + 1
            if t_data["stats"]["streak"] > t_data["stats"].get("best_streak", 0):
                t_data["stats"]["best_streak"] = t_data["stats"]["streak"]
            
            # Добавляем в выученные
            if 'completed_words' not in t_data:
                t_data['completed_words'] = []
            if word_obj['hidden'] not in t_data['completed_words']:
                t_data['completed_words'].append(word_obj['hidden'])
            
            save_data(data)
            
            # Следующее слово
            game_start(m)
        else:
            bot.send_message(cid, f"❌ Ошибка! Правильно: {word_obj['full']}")
            
            # Сбрасываем серию
            t_data["stats"]["streak"] = 0
            
            # Добавляем в список ошибок
            if 'wrong_words' not in t_data:
                t_data['wrong_words'] = []
            
            exists = False
            for w in t_data['wrong_words']:
                if w.get('hidden') == word_obj['hidden']:
                    exists = True
                    break
            
            if not exists:
                t_data['wrong_words'].append(word_obj)
            
            save_data(data)
            bot.send_message(cid, "Слово ушло в «Работу над ошибками».", reply_markup=words_kb())
            del state['mode']
    
    # 7. ОБРАБОТКА РАБОТЫ НАД ОШИБКАМИ
    elif mode == 'correction':
        word_obj = state.get('word_obj')
        if not word_obj:
            bot.send_message(cid, "Ошибка. Начните заново.")
            del state['mode']
            return
        
        user_letter = m.text.strip().lower()
        
        if user_letter == word_obj['letter']:
            bot.send_message(cid, "✅ Верно! Слово исправлено.")
            
            # Удаляем из списка ошибок
            if 'wrong_words' in t_data:
                new_wrong = []
                for w in t_data['wrong_words']:
                    if w.get('hidden') != word_obj['hidden']:
                        new_wrong.append(w)
                t_data['wrong_words'] = new_wrong
            
            save_data(data)
            bot.send_message(cid, "Возвращаюсь в меню...", reply_markup=words_kb())
            del state['mode']
        else:
            bot.send_message(cid, f"❌ Ошибка! Правильно: {word_obj['full']}. Попробуйте позже.")
            del state['mode']


# ==========================================
# ЗАПУСК
# ==========================================
import time

if __name__ == '__main__':
    try:
        d = load_data()
        for uid, p in d["plans"].items():
            try:
                h, mn = p["time"].split(":")
                scheduler.add_job(execute_plan, 'cron', hour=h, minute=mn,
                                  args=[int(uid), p['count'], p['task']],
                                  id=f"job_{uid}")
            except: continue
    except Exception as e:
        print(f"Ошибка планов: {e}")

    # 2. Бесконечный цикл с защитой от разрыва соединения
    print("Бот запущен и следит за соединением...")
    while True:
        try:
            # Устанавливаем таймауты, чтобы соединение не висело вечно
            bot.infinity_polling(timeout=20, long_polling_timeout=10)
        except Exception as e:
            print(f"Произошел обрыв сети: {e}")
            print("Перезапуск через 5 секунд...")
            time.sleep(5)
