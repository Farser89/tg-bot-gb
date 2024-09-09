import logging
from typing import Dict
from datetime import datetime, timedelta
from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove, Update, constants
from db_utils import insert, sql_select, sql_query
from bot_utils import check_role, get_ready_text, get_admins, check_team, get_team_id, get_ready_text_own
from pytz import timezone
import pandas as pd
import asyncio
from toke import TOKEN
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
    CallbackContext
)

# ------------------------------------------------------------------------------------------------------------------

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)

logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

# Перечисление ветвей ConversationHandler
START, CHOICE, DATE, RESTART, \
    STATUS, VALIDATION, REGISTRATION, \
    TIME_SCHEDULE, TIME_CHOICE, SET_TIME, \
    GET_STATUS_DATE, DELETE_SCHEDULE, STATUS_TYPE_WRITE, \
    STATUS_TYPE_GET, ADMIN_ACTION, WEEKLY_STATUS, \
    ADMIN_CHOICE, ROLE_USER_PICK, ROLE_USER, \
    REGISTRATION_TEAM, ASSIGN_TEAM, ASSIGN_TEAM_ROLE, \
    USER_TEAM_RECORD, START_ACTION, SUPER_USER_CHOICE, LOWER_LIMIT, \
    UPPER_LIMIT, GET_STATUSES, USER_ID_GET_STATUS, ADD_TEAM, \
    TEAM_CONTROL, CHANGE_TEAM_NAME, TEAM_ID = range(33)


# ------------------------------------------------------------------------------------------------------------------


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Функция инициализирует начало общения с ботом.
    На первом этапе происходит проверка роли юзера

    Попадание в эту функцию(часть диалога): /start(команда), /restart(команда)

    :update - сообщение от юзера
    :context - внутренний словарь, куда можно передавать переменные в другие функции
        - context.user_data['user_role_dict'] - роли юзера в разных командах
        - context.user_data['user_team_pick'] - выбора команды юзера - id команды
        - context.user_data['user_team_role'] - роль юзера в выбранной команде
        - context.user_data['replay_keyboard'] - тип клавиатуры пользователя
    Развилки:

    Супер роль - роль в рамках бота, вне команды
        - Если супер роль = 1 - Обычный юзер
            – Если юзер в одной команде, то нет выбора команды - CHOICE
            - Если юзер больше, чем в одной команде, то выбор команды - START_ACTION
        - Если супер роль = 2 - суперюзер
            – Есть выбор команды и меню администрирование - SUPER_USER_CHOICE
        – Если супер роль = -1 - исключенный пользователь
        – Если супер роль = 0 - пользователь не подтвержден админом
        - Если у пользователя нет роли, то регистрация - REGISTRATION

    Роль в команде:
        - Если одна команда и роль в ней равна 1(обычный юзер) - CHOICE
            - context.user_data['replay_keyboard'] = ["Писать статус", "Настройка уведомления", 'Выгрузить свои статусы']
        - Если несколько команд - START_ACTION
        - Если одна команда и роль в ней равна 2(админ команды) - CHOICE
            - context.user_data['replay_keyboard'] = ["Писать статус", "Настройка уведомления",
                "Получить статусы"], ["Администрирование пользователей", 'Выгрузить свои статусы']
    """

    user_id = update.message.from_user.id
    super_role = check_role(user_id)
    if super_role == 1:
        dict_of_roles = check_team(user_id)
        context.user_data['user_role_dict'] = dict_of_roles
        teams = dict_of_roles.keys()
        if len(teams) == 0:
            await update.message.reply_text(
                f'Привет! Пожалуйста, подождите, у вас пока нет команды. Напишите администраторам {get_admins()}')
        elif len(teams) == 1:
            context.user_data['user_team_pick'] = get_team_id(teams[0])
            user_role = dict_of_roles[teams[0]]
            context.user_data['user_team_role'] = user_role
            if user_role == 2:
                context.user_data['replay_keyboard'] = [["Писать статус", "Настройка уведомления", "Получить статусы"],
                                                        ["Администрирование пользователей", 'Выгрузить свои статусы']]

                await update.message.reply_text(
                    "Привет! Если все сломалось напишите команду /restart",
                    reply_markup=ReplyKeyboardMarkup(
                        context.user_data.get('replay_keyboard'), one_time_keyboard=False, resize_keyboard=True))
                return CHOICE
            elif user_role == 1:
                context.user_data['replay_keyboard'] = [
                    ["Писать статус", "Настройка уведомления", 'Выгрузить свои статусы']]

                await update.message.reply_text(
                    "Привет! Если все сломалось напишите команду /restart",
                    reply_markup=ReplyKeyboardMarkup(
                        context.user_data.get('replay_keyboard'), one_time_keyboard=True, resize_keyboard=True))
                return CHOICE
        else:
            await update.message.reply_text(
                f"Привет! Выбери команду",
                reply_markup=ReplyKeyboardMarkup(
                    [list(dict_of_roles.keys())], one_time_keyboard=False, resize_keyboard=True))
            return START_ACTION
    elif super_role == 2:
        dict_of_roles = check_team(user_id)
        context.user_data['user_role_dict'] = dict_of_roles
        teams = dict_of_roles.keys()

        if len(teams) == 0:
            keyboard = [['Администрирование']]

            await update.message.reply_text(
                f'Привет!', reply_markup=ReplyKeyboardMarkup(
                    keyboard, one_time_keyboard=True, resize_keyboard=True))
            return SUPER_USER_CHOICE
        else:
            keyboard = [['Выбор команды', 'Администрирование']]

            await update.message.reply_text(
                f'Привет! Выбери следующее действие', reply_markup=ReplyKeyboardMarkup(
                    keyboard, one_time_keyboard=True, resize_keyboard=True))
            return SUPER_USER_CHOICE
    elif super_role == 0:
        await update.message.reply_text(
            f'Привет! Пожалуйста, подождите, вы пока не зарегистрированы. Напишите администраторам {get_admins()}')
    elif super_role == -1:
        await update.message.reply_text(
            f'Привет! Вы были исключены. Если это ошибка, то напишите администраторам {get_admins()}')
    else:
        await update.message.reply_text('Привет! Пожалуйста, напишите свое ФИО')
        return REGISTRATION


async def super_user_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Функция выбора действия суперадмином.

    Попадание в эту функцию(часть диалога): START -> SUPER_USER_CHOICE

    :update - сообщение от юзера
    :context - внутренний словарь, куда можно передавать переменные в другие функции
        - context.user_data['super_user_flag'] - флаг отличающий суперюзера от обычного админа(требуется в общей функции admin_choice)
        - context.user_data['super_keyboard'] - клавиатура суперадмина в функции admin_choice - разный вход супер юзера и обычного админа
        - context.user_data['user_role_dict'] - роли юзера в разных командах
    Развилка:
        – Администрирование, если выбор суперюзера было администрирование - ADMIN_CHOICE
        - Выбор команды, если суперюзер хочет войти в командный режим – START_ACTION
    """

    text = update.message.text
    if text == 'Администрирование':
        context.user_data['super_user_flag'] = 1
        context.user_data['super_keyboard'] = [
            ['Управление командами', 'Управление ролями в команде'],
            ['Подтверждение пользователей', 'Управление ролями'], ['Вернуться назад']]

        await update.message.reply_text(
            f"Выберите, что вы хотите?",
            reply_markup=ReplyKeyboardMarkup(
                context.user_data['super_keyboard'], one_time_keyboard=True, resize_keyboard=True))
        return ADMIN_CHOICE
    elif text == 'Выбор команды':
        dict_of_roles = check_team(update.message.from_user.id)
        context.user_data['user_role_dict'] = dict_of_roles

        await update.message.reply_text(
            f"Выбери команду",
            reply_markup=ReplyKeyboardMarkup(
                [list(dict_of_roles.keys())], one_time_keyboard=False, resize_keyboard=True))
        return START_ACTION


async def start_action(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Промежуточная функция для юзеров у которых больше одной команды - переход к функционалу после выбора команд
    Попадание в эту функцию(часть диалога): START -> START_ACTION, SUPER_USER_CHOICE -> START_ACTION

    :update - сообщение от юзера
    :context - внутренний словарь, куда можно передавать переменные в другие функции
        - context.user_data['user_team_pick'] - выбора команды юзера - id команды
        - context.user_data['user_team_role'] - роль юзера в выбранной команде
        - context.user_data['replay_keyboard'] - тип клавиатуры пользователя
    Развилка:
        - Вне зависимости от роли попадание в функцию CHOICE
            - Разные клавиатуры
    """

    text = update.message.text
    context.user_data['user_team_pick'] = get_team_id(text)
    dict_of_roles = context.user_data.get('user_role_dict')
    user_role = dict_of_roles[text]
    context.user_data['user_team_role'] = user_role
    if user_role == 2:
        context.user_data['replay_keyboard'] = [["Писать статус", "Настройка уведомления", "Получить статусы"],
                                                ["Администрирование пользователей", 'Выгрузить свои статусы']]

        await update.message.reply_text(
            "Если все сломалось напишите команду /restart",
            reply_markup=ReplyKeyboardMarkup(
                context.user_data.get('replay_keyboard'), one_time_keyboard=True, resize_keyboard=True))
        return CHOICE
    elif user_role == 1:
        context.user_data['replay_keyboard'] = [
            ["Писать статус", "Настройка уведомления"], ['Выгрузить свои статусы']]

        await update.message.reply_text(
            "Привет! Если все сломалось напишите команду /restart",
            reply_markup=ReplyKeyboardMarkup(
                context.user_data.get('replay_keyboard'), one_time_keyboard=True, resize_keyboard=True))
        return CHOICE
    elif user_role == 0:

        await update.message.reply_text(
            f'Привет! Пожалуйста, подождите, вы пока не зарегистрированы. Напишите администраторам {get_admins()}')
    elif user_role == -1:

        await update.message.reply_text(
            f'Привет! Вы были исключены. Если это ошибка, то напишите администраторам {get_admins()}')
    else:

        await update.message.reply_text('Привет! Пожалуйста, напишите свое ФИО')
        return REGISTRATION


async def choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Функция, которая позволяет переходить в разные ветки функционала бота
    Является функцией, которая выдается после завершения функционала других функций

    Попадание в эту функцию(часть диалога): Возвращение назад, ошибка при исполнении функции, начало работы с ботом(выбор команды))

    :update - сообщение от юзера
    :context - внутренний словарь, куда можно передавать переменные в другие функции
        - context.user_data['super_user_flag']
        - context.user_data['admin_action']

    Развилка:
    Если роль = Админ команды, то функции
        - Писать статус - STATUS_TYPE_WRITE
        - Получить статусы - GET_STATUSES
        - Настройка уведомления - TIME_CHOICE
        - Администрирование пользователей - ADMIN_CHOICE
        - Выгрузить свои статусы - LOWER_LIMIT(флаг админа = 0)
    Если роль = обычный юзер, то функции
        - Писать статус - STATUS_TYPE_WRITE
        - Настройка уведомления - TIME_CHOICE
        - Выгрузить свои статусы - LOWER_LIMIT(флаг админа = 0)
    """

    text = update.message.text
    user_role = context.user_data.get('user_team_role')
    if user_role == 2:
        if text == "Писать статус":
            ReplyKeyboardRemove()
            reply_keyboard = [
                ['Ежедневный', 'Двухнедельный', 'Вернуться назад']]
            await update.message.reply_text(
                f"Выберите тип статуса, который вы хотите отправить",
                reply_markup=ReplyKeyboardMarkup(
                    reply_keyboard, one_time_keyboard=False, resize_keyboard=True))
            return STATUS_TYPE_WRITE
        elif text == "Получить статусы":
            ReplyKeyboardRemove()
            reply_keyboard = [
                ['Получить статусы от всех', 'Получить статусы отдельного человека', 'Вернуться назад']]
            await update.message.reply_text(
                f"Выберите действие",
                reply_markup=ReplyKeyboardMarkup(
                    reply_keyboard, one_time_keyboard=False, resize_keyboard=True
                ),
            )
            return GET_STATUSES
        elif text == 'Настройка уведомления':
            ReplyKeyboardRemove()
            reply_keyboard = [
                ['Внести время', 'Посмотреть расписание уведомлений', 'Удалить расписание', 'Вернуться назад']]
            await update.message.reply_text(
                f"Выберите, что вы хотите?",
                reply_markup=ReplyKeyboardMarkup(
                    reply_keyboard, one_time_keyboard=False, resize_keyboard=True)
            )
            return TIME_CHOICE
        elif text == "Администрирование пользователей":
            context.user_data['super_user_flag'] = 0
            ReplyKeyboardRemove()
            reply_keyboard = [
                ['Управление ролями в команде'], ['Подтверждение пользователей', 'Вернуться назад']]
            await update.message.reply_text(
                f"Выберите, что вы хотите?",
                reply_markup=ReplyKeyboardMarkup(
                    reply_keyboard, one_time_keyboard=False, resize_keyboard=True)
            )
            return ADMIN_CHOICE
        elif text == 'Выгрузить свои статусы':
            ReplyKeyboardRemove()
            context.user_data['admin_action'] = 0
            reply_keyboard = [
                ['Вернуться назад']]
            await update.message.reply_text(
                f"Введите нижнюю границу в формате '%Y-%m-%d'",
                reply_markup=ReplyKeyboardMarkup(
                    reply_keyboard, one_time_keyboard=False, resize_keyboard=True
                ),
            )
            return LOWER_LIMIT
    elif user_role == 1:
        if text == "Писать статус":
            ReplyKeyboardRemove()
            reply_keyboard = [
                ['Ежедневный', 'Двухнедельный', 'Вернуться назад']]
            await update.message.reply_text(
                f"Выберите тип статуса, который вы хотите отправить",
                reply_markup=ReplyKeyboardMarkup(
                    reply_keyboard, one_time_keyboard=False, resize_keyboard=True
                ),
            )
            return STATUS_TYPE_WRITE
        elif text == 'Настройка уведомления':
            ReplyKeyboardRemove()
            reply_keyboard = [
                ['Внести время', 'Посмотреть расписание уведомлений', 'Удалить расписание', 'Вернуться назад']]
            await update.message.reply_text(
                f"Выберите, что вы хотите?",
                reply_markup=ReplyKeyboardMarkup(
                    reply_keyboard, one_time_keyboard=False, resize_keyboard=True)
            )
            return TIME_CHOICE
        elif text == 'Выгрузить свои статусы':
            ReplyKeyboardRemove()
            context.user_data['admin_action'] = 0
            reply_keyboard = [
                ['Вернуться назад']]
            await update.message.reply_text(
                f"Введите нижнюю границу в формате '%Y-%m-%d'",
                reply_markup=ReplyKeyboardMarkup(
                    reply_keyboard, one_time_keyboard=True, resize_keyboard=True
                ),
            )
            return LOWER_LIMIT
    else:
        await update.message.reply_text(f"Вы были исключены. Если это ошибка, то напишите администраторам {get_admins()}")
        return ConversationHandler.END


async def get_statuses(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Функция для разделения получения статусов от команды/отдельно взятого человека

    Попадание в эту функцию(часть диалога): CHOICE -> GET_STATUSES

    :update - сообщение от юзера
    :context - внутренний словарь, куда можно передавать переменные в другие функции
        - context.user_data['admin_action'] - Выгрузка статусов отдельного человека

    Развилка:
        - Если Получить статусы от всех, то переход в тип статуса - STATUS_TYPE_GET
        - Если Получить статусы отдельного человека, то переход в ввод айди юзера - USER_ID_GET_STATUS
        - Вернуться назад - CHOICE

    """
    text = update.message.text
    if text == 'Получить статусы от всех':
        ReplyKeyboardRemove()
        reply_keyboard = [
            ['Ежедневный', 'Двухнедельный', 'Вернуться назад']]
        await update.message.reply_text(
            f"Выберите тип статуса, который вы хотите получить",
            reply_markup=ReplyKeyboardMarkup(
                reply_keyboard, one_time_keyboard=False, resize_keyboard=True
            ),
        )
        return STATUS_TYPE_GET
    elif text == 'Получить статусы отдельного человека':
        context.user_data['admin_action'] = 1
        query = f'''select u.user_id, real_name, username  from tg_bot.users u
                left join tg_bot.role_team rt on u.user_id = rt.user_id
                where team_id = {context.user_data.get('user_team_pick')}'''
        message = sql_select(query)
        message.set_index('user_id', inplace=True)
        await update.message.reply_text(
            f"{message.to_markdown()}"
        )
        await update.message.reply_text(
            f"Введите id человека, для получения его статусов"
        )
        return USER_ID_GET_STATUS
    elif text == 'Вернуться назад':
        await update.message.reply_text(
            'Выберите далнейшие действия',
            reply_markup=ReplyKeyboardMarkup(
                context.user_data.get('replay_keyboard'), one_time_keyboard=True, resize_keyboard=True
            ))
        return CHOICE


async def user_id_get_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Функция для получения id человека по выгрузке статусов.

    Попадание в эту функцию(часть диалога): GET_STATUS -> USER_ID_GET_STATUS

    :update - сообщение от юзера
    :context - внутренний словарь, куда можно передавать переменные в другие функции
        - context.user_data['user_id_get_status'] - id юзера для выгрузки

    Функция линейна, и ведет к определению нижней границы выгрузки статусов

    """
    text = update.message.text
    context.user_data['user_id_get_status'] = text
    await update.message.reply_text(
        f"Введите нижнюю границу в формате '%Y-%m-%d'",
    )
    return LOWER_LIMIT


async def lower_limit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Функция для получения нижней границы статусов.

    Попадание в эту функцию(часть диалога): USER_ID_GET_STATUS -> LOWER_LIMIT

    :update - сообщение от юзера
    :context - внутренний словарь, куда можно передавать переменные в другие функции
        - context.user_data['lower_limit'] - нижняя граница статусов

    Развилка: 
        - Вернуться назад - CHOICE
        - Введение верхней границы получения статусов - UPPER_LIMIT
    """
    text = update.message.text
    if text == 'Вернуться назад':
        await update.message.reply_text(
            'Выберите далнейшие действия',
            reply_markup=ReplyKeyboardMarkup(
                context.user_data.get('replay_keyboard'), one_time_keyboard=True, resize_keyboard=True
            ))
        return CHOICE
    else:
        context.user_data['lower_limit'] = text
        await update.message.reply_text(
            f"Введите верхнюю границу в формате '%Y-%m-%d'",
        )
        return UPPER_LIMIT


async def upper_limit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Функция для получения верхней границы статусов.

    Попадание в эту функцию(часть диалога): USER_ID_GET_STATUS -> LOWER_LIMIT

    :update - сообщение от юзера
    :context - внутренний словарь, куда можно передавать переменные в другие функции

    Развилка: 
        - Ошибка
            - Возвращение в меню – CHOICE
        - Выгрузка статусов
            - Админ выгружает статус конкретного человека – CHOICE
            - Юзер выгужает свои статусы – CHOICE
    """
    text = update.message.text
    if context.user_data['admin_action'] == 0:
        query = f'''
                    with cte as (
                    select *, row_number() over (partition by s.user_id, date order by tech_load_ts desc) as rn from tg_bot.STATUS s
                    left join tg_bot.users u on s.user_id = u.user_id
                    where (date between '{context.user_data.get('lower_limit')}' and '{text}')  and s.user_id = {update.message.from_user.id}
                    )
                    select * from cte
                    where rn = 1'''
        USER_STATUS = sql_select(sql=query)
        result = get_ready_text_own(USER_STATUS)
        if type(result) == str:
            await update.message.reply_text(
                result,
                reply_markup=ReplyKeyboardMarkup(
                    context.user_data.get('replay_keyboard'), one_time_keyboard=True, resize_keyboard=True
                ),
                parse_mode=constants.ParseMode.HTML)
            return CHOICE
        else:
            for statuses in result:
                await update.message.reply_text(
                    str(statuses),
                    parse_mode=constants.ParseMode.HTML)
            await update.message.reply_text('Выгрузка закончена',
                                            reply_markup=ReplyKeyboardMarkup(
                                                context.user_data.get('replay_keyboard'), one_time_keyboard=True, resize_keyboard=True
                                            ))
            return CHOICE
    elif context.user_data['admin_action'] == 1:
        query = f'''
                    with cte as (
                    select *, row_number() over (partition by s.user_id, date order by tech_load_ts desc) as rn from tg_bot.STATUS s
                    left join tg_bot.users u on s.user_id = u.user_id
                    where (date between '{context.user_data.get('lower_limit')}' and '{text}')  and s.user_id = {context.user_data['user_id_get_status']}
                    )
                    select * from cte
                    where rn = 1'''
        USER_STATUS = sql_select(sql=query)
        result = get_ready_text_own(USER_STATUS)
        if type(result) == str:
            await update.message.reply_text(
                result,
                reply_markup=ReplyKeyboardMarkup(
                    context.user_data.get('replay_keyboard'), one_time_keyboard=True, resize_keyboard=True
                ),
                parse_mode=constants.ParseMode.HTML)
            return CHOICE
        else:
            for statuses in result:
                await update.message.reply_text(
                    str(statuses),
                    parse_mode=constants.ParseMode.HTML)
            await update.message.reply_text('Выгрузка закончена',
                                            reply_markup=ReplyKeyboardMarkup(
                                                context.user_data.get('replay_keyboard'), one_time_keyboard=True, resize_keyboard=True
                                            ))
            return CHOICE


async def admin_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Функция, которая позволяет переходить в разные ветки функционала суперюзера/админа команды бота
    Является функцией, которая выдается после завершения функционала других функций


    Попадание в эту функцию(часть диалога): SUPER_USER_CHOICE -> CHOICE, CHOICE -> ADMIN_CHOICE, 
    Возвращение назад

    :update - сообщение от юзера
    :context - внутренний словарь, куда можно передавать переменные в другие функции

    Развилка: 
        - Если суперюзер - вход со стороны начального меню суперюзера
            - Управление ролями в рамках бота - ROLE_USER_PICK
            - Управление командами - Добавить команду, Изменить нейминг команды, Удалить команду - TEAM_CONTROL
            - Подтверждение пользователей - ADMIN_ACTION, если есть такие пользователи, иначе - SUPER_USER_CHOICE
            - Управление ролями в команде - ASSIGN_TEAM
            - Вернуться назад - SUPER_USER_CHOICE
        - Если админ в рамках команды(может быть суперюзером)
            - Управление ролями в рамках бота - ROLE_USER_PICK
            - Подтверждение пользователей - ADMIN_ACTION, если есть такие пользователи, иначе - CHOICE
            - Управление ролями в команде - ASSIGN_TEAM
            - Возвращение назад - CHOICE
    """

    text = update.message.text
    if context.user_data.get('super_user_flag') == 0:
        if text == 'Подтверждение пользователей':
            query = f'''select * from tg_bot.users where is_user = 0'''
            USER_AWAITING = sql_select(sql=query)
            try:
                USER_AWAITING.iloc[0]
                await update.message.reply_text(
                    USER_AWAITING.to_markdown(),
                    reply_markup=ReplyKeyboardMarkup(
                        [['Подтвердить всех?', 'Вернуться назад']], one_time_keyboard=True, resize_keyboard=True
                    ))
                await update.message.reply_text(
                    'Введите id юзера, который хотите подтвердить или подтвердите всех')
                return ADMIN_ACTION
            except IndexError:
                await update.message.reply_text(
                    'Нет пользователей, которые запросили вход',
                    reply_markup=ReplyKeyboardMarkup(
                        context.user_data.get('replay_keyboard'), one_time_keyboard=True, resize_keyboard=True
                    ))
                return CHOICE
        elif text == 'Управление ролями в команде':
            query = f''' select u.user_id, username, real_name, is_user as "Роль в боте", rt.team_id, 
            team_name, team_role from tg_bot.users u
            left join tg_bot.role_team rt on rt.user_id = u.user_id
            left join tg_bot.teams t on t.team_id = rt.team_id '''
            USERS_WITHOUT_TEAM = sql_select(sql=query)
            USERS_WITHOUT_TEAM.set_index('user_id', inplace=True)
            await update.message.reply_text(
                f"{USERS_WITHOUT_TEAM.to_markdown()}")
            await update.message.reply_text(
                'Введите id юзера, над которым вы хотите произвести действие',
                reply_markup=ReplyKeyboardMarkup(
                    [['Вернуться назад']], resize_keyboard=True
                ))
            return ASSIGN_TEAM
        elif text == 'Вернуться назад':
            await update.message.reply_text(
                'Выберите далнейшие действия',
                reply_markup=ReplyKeyboardMarkup(
                    context.user_data.get('replay_keyboard'), one_time_keyboard=True, resize_keyboard=True
                ))
            return CHOICE
    else:
        if text == 'Управление ролями':
            query = '''select * from tg_bot.users s'''
            ALL_USERS = sql_select(sql=query)
            ALL_USERS.set_index('user_id', inplace=True)
            await update.message.reply_text(
                f"{ALL_USERS.to_markdown()}")
            await update.message.reply_text(
                'Введите id юзера, над которым вы хотите произвести действие',
                reply_markup=ReplyKeyboardMarkup(
                    [['Вернуться назад']], resize_keyboard=True
                ))
            return ROLE_USER_PICK
        elif text == 'Управление командами':
            await update.message.reply_text(
                'Выберите действие',
                reply_markup=ReplyKeyboardMarkup(
                    [['Добавить команду', 'Изменить нейминг команды', 'Удалить команду', 'Вернуться назад']], one_time_keyboard=True, resize_keyboard=True
                ))
            return TEAM_CONTROL
        elif text == 'Подтверждение пользователей':
            query = f'''select * from tg_bot.users where is_user = 0'''
            USER_AWAITING = sql_select(sql=query)
            try:
                USER_AWAITING.iloc[0]
                await update.message.reply_text(
                    USER_AWAITING.to_markdown(),
                    reply_markup=ReplyKeyboardMarkup(
                        [['Подтвердить всех?', 'Вернуться назад']], one_time_keyboard=True, resize_keyboard=True
                    ))
                await update.message.reply_text(
                    'Введите id юзера, который хотите подтвердить или подтвердите всех')
                return ADMIN_ACTION
            except IndexError:
                await update.message.reply_text(
                    'Нет пользователей, которые запросили вход',
                    reply_markup=ReplyKeyboardMarkup(
                        [['Выбор команды', 'Администирование']], one_time_keyboard=True, resize_keyboard=True
                    ))
                return SUPER_USER_CHOICE
        elif text == 'Управление ролями в команде':
            query = f'''select * from tg_bot.users'''
            USERS_WITHOUT_TEAM = sql_select(sql=query)
            USERS_WITHOUT_TEAM.set_index('user_id', inplace=True)
            await update.message.reply_text(
                f"{USERS_WITHOUT_TEAM.to_markdown()}")
            await update.message.reply_text(
                'Введите id юзера, над которым вы хотите произвести действие',
                reply_markup=ReplyKeyboardMarkup(
                    [['Вернуться назад']], resize_keyboard=True
                ))
            return ASSIGN_TEAM
        elif text == 'Вернуться назад':
            await update.message.reply_text(
                'Выберите далнейшие действия',
                reply_markup=ReplyKeyboardMarkup(
                    [['Выбор команды', 'Администрирование']], one_time_keyboard=True, resize_keyboard=True
                ))
            return SUPER_USER_CHOICE


async def team_control(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Функция выбора действия администрирования команд

    Роль: супер-юзер

    Попадание в эту функцию(часть диалога): ADMIN_CHOICE -> TEAM_CONTROL

    :update - сообщение от юзера
    :context - внутренний словарь, куда можно передавать переменные в другие функции
        - context.user_data['team_action'] - Категориальная переменная выбора функционала

    Развилка:
        - Добавление команды - ADD_TEAM
        - Изменить нейминг команды - TEAM_ID
        - Удалить команду - TEAM_ID
        - Вернуться назад - SUPER_USER_CHOICE

    """
    text = update.message.text
    if text == 'Вернуться назад':
        await update.message.reply_text(
            'Выберите далнейшие действия',
            reply_markup=ReplyKeyboardMarkup(
                [['Выбор команды', 'Администрирование']], one_time_keyboard=True, resize_keyboard=True
            ))
        return SUPER_USER_CHOICE
    elif text == 'Добавить команду':
        await update.message.reply_text(
            'Напишите название команды')
        return ADD_TEAM
    elif text == 'Изменить нейминг команды':
        context.user_data['team_action'] = 1
        query = f'''select * from tg_bot.teams'''
        TEAM = sql_select(sql=query)
        TEAM.set_index('team_id', inplace=True)
        await update.message.reply_text(
            f"{TEAM.to_markdown()}")
        await update.message.reply_text(
            'Введите id команды',
            reply_markup=ReplyKeyboardMarkup(
                [['Вернуться назад']], resize_keyboard=True
            ))
        return TEAM_ID
    elif text == 'Удалить команду':
        context.user_data['team_action'] = 2
        query = f'''select * from tg_bot.teams'''
        TEAM = sql_select(sql=query)
        TEAM.set_index('team_id', inplace=True)
        await update.message.reply_text(
            f"{TEAM.to_markdown()}")
        await update.message.reply_text(
            'Введите id команды',
            reply_markup=ReplyKeyboardMarkup(
                [['Вернуться назад']], resize_keyboard=True
            ))
        return TEAM_ID


async def team_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Функция удаления команды / изменения нейминга команды

    Роль: супер-юзер

    Попадание в эту функцию(часть диалога): TEAM_CONTROL -> TEAM_ID

    :update - сообщение от юзера
    :context - внутренний словарь, куда можно передавать переменные в другие функции
        - context.user_data['team_id_change'] - айди команды, требующей изменения

    Развилка:    
        - Вернуться назад - SUPER_USER_CHOICE
        - Если удаление, то на этом этапе удаляется и переход в меню - SUPER_USER_CHOICE
        - Если изменение, то сбор нового названия
    """

    text = update.message.text
    if text == 'Вернуться назад':
        await update.message.reply_text(
            'Выберите далнейшие действия',
            reply_markup=ReplyKeyboardMarkup(
                [['Выбор команды', 'Администрирование']], one_time_keyboard=True, resize_keyboard=True
            ))
        return SUPER_USER_CHOICE
    if context.user_data['team_action'] == 2:
        query = f'''DELETE FROM tg_bot.teams WHERE team_id = {text}'''
        try:
            sql_query(query)
            sql_query(
                f'''delete from tg_bot.role_team where team_id = {text} ''')
        except Exception as e:
            print(e)
            await update.message.reply_text(
                'Произошла ошибка',
                reply_markup=ReplyKeyboardMarkup(
                    [['Выбор команды', 'Администрирование']], one_time_keyboard=True, resize_keyboard=True
                ))
            return SUPER_USER_CHOICE
        await update.message.reply_text(
            'Все записано',
            reply_markup=ReplyKeyboardMarkup(
                [['Выбор команды', 'Администрирование']], one_time_keyboard=True, resize_keyboard=True
            ))
        return SUPER_USER_CHOICE
    elif context.user_data['team_action'] == 1:
        context.user_data['team_id_change'] = text
        await update.message.reply_text(
            'Напишите название команды',
            reply_markup=ReplyKeyboardMarkup(
                [['Вернуться назад']], resize_keyboard=True
            ))
        return CHANGE_TEAM_NAME


async def change_team_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Функция принимабщее от юзера новое имя для команды

    Роль: супер-юзер

    Попадание в эту функцию(часть диалога):  TEAM_ID -> CHANGE_TEAM_NAME

    :update - сообщение от юзера
    :context - внутренний словарь, куда можно передавать переменные в другие функции

    Развилка:
        - Вернуться назад - SUPER_USER_CHOICE
        - Конец функции и операции – SUPER_USER_CHOICE
    """
    text = update.message.text
    if text == 'Вернуться назад':
        await update.message.reply_text(
            'Выберите далнейшие действия',
            reply_markup=ReplyKeyboardMarkup(
                [['Выбор команды', 'Администрирование']], one_time_keyboard=True, resize_keyboard=True
            ))
        return SUPER_USER_CHOICE
    query = f'''UPDATE tg_bot.teams SET team_name = '{text}' WHERE team_id = {context.user_data['team_id_change']}'''
    try:
        sql_query(query)
    except Exception as e:
        print(e)
        await update.message.reply_text(
            'Произошла ошибка',
            reply_markup=ReplyKeyboardMarkup(
                [['Выбор команды', 'Администрирование']], one_time_keyboard=True, resize_keyboard=True
            ))
        return SUPER_USER_CHOICE
    await update.message.reply_text(
        'Все записано',
        reply_markup=ReplyKeyboardMarkup(
            [['Выбор команды', 'Администрирование']], one_time_keyboard=True, resize_keyboard=True
        ))
    return SUPER_USER_CHOICE


async def add_team(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Функция добавляющая в БД новую команду

    Роль: супер-юзер

    Попадание в эту функцию(часть диалога):  ADMIN_CHOICE -> ADD_TEAM

    :update - сообщение от юзера
    :context - внутренний словарь, куда можно передавать переменные в другие функции

    Функция линейна и ведет к SUPER_USER_CHOICE
    """
    text = update.message.text
    df_insert = {'team_name': text}
    df_insert = pd.DataFrame(df_insert, index=[0])
    insert(df=df_insert, database_name='main_db',
           table_name='teams', schema='tg_bot')
    keyboard = [['Выбор команды', 'Администрирование']]
    await update.message.reply_text(
        f'Привет! Выбери следующее действие', reply_markup=ReplyKeyboardMarkup(
            keyboard, one_time_keyboard=True, resize_keyboard=True
        ))
    return SUPER_USER_CHOICE


async def assign_team(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Функция назначения роли юзеру в команды(админ), а также выбора командля для присвоения(суперюзер)

    Роль: супер-юзер/админ команды

    Попадание в эту функцию(часть диалога):  ADMIN_CHOICE -> ASSIGN_TEAM

    :update - сообщение от юзера
    :context - внутренний словарь, куда можно передавать переменные в другие функции
        - context.user_data['user_id_team'] - айди команды назначения
        - context.user_data['user_id_ass'] - айди юзера для назначения команды

    Развилка:
        - Суперюзер
            - Выбор команды для назначения роли юзеру - ASSIGN_TEAM_ROLE
            - Вернутсья назад - SUPER_USER_CHOICE
        - Админ команды
            - Назначение роли участнику команды - USER_TEAM_RECORD
    """
    text = update.message.text
    if context.user_data.get('super_user_flag') == 1:
        if text == 'Вернуться назад':
            await update.message.reply_text(
                'Выберите далнейшие действия',
                reply_markup=ReplyKeyboardMarkup(
                    [['Выбор команды', 'Администрирование']], one_time_keyboard=True, resize_keyboard=True
                ))
            return SUPER_USER_CHOICE
        else:
            context.user_data['user_id_ass'] = text
            query = f'''select * from tg_bot.teams'''
            TEAM = sql_select(sql=query)
            TEAM.set_index('team_id', inplace=True)
            await update.message.reply_text(
                f"{TEAM.to_markdown()}")
            await update.message.reply_text(
                'Введите id команды',
                reply_markup=ReplyKeyboardMarkup(
                    [['Вернуться назад']], resize_keyboard=True
                ))
            return ASSIGN_TEAM_ROLE
    else:
        context.user_data['user_id_ass'] = text
        context.user_data['user_id_team'] = context.user_data['user_team_pick']
        reply_keyboard = [['-1', '1', '2']]
        await update.message.reply_text(
            f"Выберите, роль - -1(Удалить юзера), 1 - (Понизить до юзера), 2 - (Повысить до адмиистратора)",
            reply_markup=ReplyKeyboardMarkup(
                reply_keyboard, one_time_keyboard=False, resize_keyboard=True)
        )
        return USER_TEAM_RECORD


async def assign_team_role(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Функция назначения роли юзеру

    Роль: супер-юзер

    Попадание в эту функцию(часть диалога): ASSIGN_TEAM -> ASSIGN_TEAM_ROLE

    :update - сообщение от юзера
    :context - внутренний словарь, куда можно передавать переменные в другие функции
        - context.user_data['user_id_team'] - айди команды назначения

    Развилка:
        - Суперюзер
            - Завершение функции - USER_TEAM_RECORD
            - Вернутсья назад - SUPER_USER_CHOICE
    """
    text = update.message.text
    if text == 'Вернуться назад':
        await update.message.reply_text(
            'Выберите далнейшие действия',
            reply_markup=ReplyKeyboardMarkup(
                [['Выбор команды', 'Администрирование']], one_time_keyboard=True, resize_keyboard=True
            ))
        return SUPER_USER_CHOICE
    context.user_data['user_id_team'] = text
    reply_keyboard = [['-1', '1', '2'], ['Вернуться назад']]
    await update.message.reply_text(
        f"Выберите, роль - -1(Удалить юзера), 1 - (Понизить до юзера), 2 - (Повысить до адмиистратора)",
        reply_markup=ReplyKeyboardMarkup(
            reply_keyboard, one_time_keyboard=False, resize_keyboard=True)
    )
    return USER_TEAM_RECORD


async def user_team_record(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Функция завершающая процесс назначения команды и роли в команде
    Инсерт в БД

    Роль: супер-юзер/админ команды

    Попадание в эту функцию(часть диалога): ASSIGN_TEAM_ROLE -> USER_TEAM_RECORD

    :update - сообщение от юзера
    :context - внутренний словарь, куда можно передавать переменные в другие функции

    Функци линейна: 
        - Суперюзер
            - Ошибка - SUPER_USER_CHOICE
            - Завершение функции - SUPER_USER_CHOICE
        - Администратор команды
            - Ошибка - CHOICE
            - Завершение функции - CHOICE
    """
    text = update.message.text
    if context.user_data.get('super_user_flag') == 1:
        if text == 'Вернуться назад':
            await update.message.reply_text(
                'Выберите далнейшие действия',
                reply_markup=ReplyKeyboardMarkup(
                    [['Выбор команды', 'Администрирование']], one_time_keyboard=True, resize_keyboard=True
                ))
            return SUPER_USER_CHOICE
        query = f'''DELETE FROM tg_bot.role_team where user_id = {context.user_data["user_id_ass"]} and team_id = {context.user_data["user_id_team"]}'''
        sql_query(query)
        df_insert = {'user_id': [context.user_data["user_id_ass"]],
                     'team_id': [context.user_data["user_id_team"]],
                     'team_role': [text]}
        df_insert = pd.DataFrame(df_insert)
        try:
            insert(df=df_insert, database_name='main_db', schema='tg_bot',
                   table_name='role_team')
        except Exception as e:
            print(e)
            await update.message.reply_text(
                'Произошла ошибка',
                reply_markup=ReplyKeyboardMarkup(
                    [['Выбор команды', 'Администрирование']], one_time_keyboard=True, resize_keyboard=True
                ))
            return SUPER_USER_CHOICE
        sql_query(
            f'UPDATE tg_bot.users set in_team = 1 where user_id = {context.user_data["user_id_ass"]}')
        await update.message.reply_text(
            'Все записано',
            reply_markup=ReplyKeyboardMarkup(
                [['Выбор команды', 'Администрирование']], one_time_keyboard=True, resize_keyboard=True
            ))
        return SUPER_USER_CHOICE
    elif context.user_data.get('super_user_flag') == 0:
        query = f'''DELETE FROM tg_bot.role_team where user_id = {context.user_data["user_id_ass"]} and team_id = {context.user_data["user_id_team"]}'''
        sql_query(query)
        df_insert = {'user_id': [context.user_data["user_id_ass"]],
                     'team_id': [context.user_data["user_id_team"]],
                     'team_role': [text]}
        df_insert = pd.DataFrame(df_insert)
        try:
            insert(df=df_insert, database_name='main_db', schema='tg_bot',
                   table_name='role_team')
        except Exception as e:
            print(e)
            await update.message.reply_text(
                'Произошла ошибка',
                reply_markup=ReplyKeyboardMarkup(
                    context.user_data.get('replay_keyboard'), one_time_keyboard=True, resize_keyboard=True
                ))
            return CHOICE
        sql_query(
            f'UPDATE tg_bot.users set in_team = 1 where user_id = {context.user_data["user_id_ass"]}')
        await update.message.reply_text(
            'Записано',
            reply_markup=ReplyKeyboardMarkup(
                context.user_data.get('replay_keyboard'), one_time_keyboard=True, resize_keyboard=True
            ))
        return CHOICE


async def role_user_pick(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Функция выбора роли в рамках бота
    Инсерт в БД

    Роль: супер-юзер

    Попадание в эту функцию(часть диалога): ADMIN_CHOICE -> ROLE_USER_PICK

    :update - сообщение от юзера
    :context - внутренний словарь, куда можно передавать переменные в другие функции

    Развилка: 
        - Вернуться назад - SUPER_USER_CHOICE
        - Завершение функции - ROLE_USER
    """
    text = update.message.text
    if text == 'Вернуться назад':
        await update.message.reply_text(
            'Выберите далнейшие действия',
            reply_markup=ReplyKeyboardMarkup(
                context.user_data['super_keyboard'], one_time_keyboard=True, resize_keyboard=True
            ))
        return SUPER_USER_CHOICE
    else:
        context.user_data['role_user'] = text
        reply_keyboard = [['-1', '1', '2']]
        await update.message.reply_text(
            f"Выберите, роль - -1(Удалить юзера), 1 - (Забрать права суперюзера), 2 - (Повысить до суперюзера)",
            reply_markup=ReplyKeyboardMarkup(
                reply_keyboard, one_time_keyboard=False, resize_keyboard=True)
        )
        return ROLE_USER


async def role_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Функция записи в БД роли юзера

    Роль: супер-юзер

    Попадание в эту функцию(часть диалога): ROLE_USER_PICK -> ROLE_USER

    :update - сообщение от юзера
    :context - внутренний словарь, куда можно передавать переменные в другие функции

    Функция линейна:
        - Завершение - SUPER_USER_CHOICE
        - Ошибка - SUPER_USER_CHOICE
    """
    text = update.message.text
    query = f'''update tg_bot.users set is_user = {text}
        where user_id = {context.user_data.get('role_user')}'''
    try:
        sql_query(query)
        await update.message.reply_text(
            'Выберите далнейшие действия',
            reply_markup=ReplyKeyboardMarkup(
                [['Выбор команды', 'Администрирование']], one_time_keyboard=True, resize_keyboard=True
            ))
        return SUPER_USER_CHOICE
    except Exception as e:
        print(e)
        await update.message.reply_text(
            'Выберите далнейшие действия',
            reply_markup=ReplyKeyboardMarkup(
                [['Выбор команды', 'Администрирование']], one_time_keyboard=True, resize_keyboard=True
            ))
        return SUPER_USER_CHOICE


async def admin_action(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Функция принятия в бота юзеров с ролью 1

    Роль: супер-юзер/админ

    Попадание в эту функцию(часть диалога): SUPER_USER_CHOICE -> ADMIN_ACTION, CHOICE -> ADMIN_ACTION

    :update - сообщение от юзера
    :context - внутренний словарь, куда можно передавать переменные в другие функции

    Развилка:
        - Суперпользователь
            - Завершение - SUPER_USER_CHOICE
            - Ошибка - SUPER_USER_CHOICE
            - Вернуться назад - SUPER_USER_CHOICE
        - Пользователь
            - Завершение - CHOICE
            - Ошибка - CHOICE
            - Вернуться назад - CHOICE
    """
    text = update.message.text
    if context.user_data.get('super_user_flag') == 0:
        if text == 'Подтвердить всех?':
            query = '''update tg_bot.users set is_user = 1 where is_user = 0'''
            sql_query(query)
            await update.message.reply_text(
                'Пользователи/пользователь добавлен',
                reply_markup=ReplyKeyboardMarkup(
                    context.user_data.get('replay_keyboard'), one_time_keyboard=True, resize_keyboard=True
                ))
            return CHOICE
        elif text == 'Вернуться назад':
            await update.message.reply_text(
                'Выберите далнейшие действия',
                reply_markup=ReplyKeyboardMarkup(
                    context.user_data.get('replay_keyboard'), one_time_keyboard=True, resize_keyboard=True
                ))
            return CHOICE
        else:
            query = f'''update tg_bot.users set is_user = 1 where user_id = {text}'''
            sql_query(query)
            await update.message.reply_text(
                'Пользователь добавлен',
                reply_markup=ReplyKeyboardMarkup(
                    context.user_data.get('replay_keyboard'), one_time_keyboard=True, resize_keyboard=True
                ))
            return CHOICE
    else:
        if text == 'Подтвердить всех?':
            query = '''update tg_bot.users set is_user = 1 where is_user = 0'''
            sql_query(query)
            await update.message.reply_text(
                'Пользователи/пользователь добавлен',
                reply_markup=ReplyKeyboardMarkup(
                    [['Выбор команды', 'Администрирование']], one_time_keyboard=True, resize_keyboard=True
                ))
            return SUPER_USER_CHOICE
        elif text == 'Вернуться назад':
            await update.message.reply_text(
                'Выберите далнейшие действия',
                reply_markup=ReplyKeyboardMarkup(
                    [['Выбор команды', 'Администрирование']], one_time_keyboard=True, resize_keyboard=True
                ))
            return SUPER_USER_CHOICE
        else:
            query = f'''update tg_bot.users set is_user = 1 where user_id = {text}'''
            sql_query(query)
            await update.message.reply_text(
                'Пользователь добавлен',
                reply_markup=ReplyKeyboardMarkup(
                    [['Выбор команды', 'Администрирование']], one_time_keyboard=True, resize_keyboard=True
                ))
            return SUPER_USER_CHOICE


async def status_type_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Функция получения типа статусов для отправки

    Роль: админ

    Попадание в эту функцию(часть диалога): CHOICE -> STATUS_TYPE_CHOICE

    :update - сообщение от юзера
    :context - внутренний словарь, куда можно передавать переменные в другие функции
        - context.user_data['status_type'] - тип статуса

    Развилка:
        - Вернуться назад - CHOICE
        - Введение даты - DATE
        - Введение даты двухнедельный статус - WEEKLY_STATUS
    """
    text = update.message.text
    if text == 'Ежедневный':
        context.user_data['status_type'] = 1
        ReplyKeyboardRemove()
        reply_keyboard = [['Дата сегодня', 'Дата вчера', 'Вернуться назад']]
        await update.message.reply_text(
            f"Выберите сегодняшний день - Дата сегодня или напишите свой день - формат - '%Y-%m-%d', если вы не будете использовать нужный формат, то оне не пустит дальше",
            reply_markup=ReplyKeyboardMarkup(
                reply_keyboard, one_time_keyboard=False, resize_keyboard=True,
                input_field_placeholder="Напиши дату, или выбери пункт - Дата сегодня"
            ),
        )
        return DATE
    elif text == 'Вернуться назад':
        await update.message.reply_text(
            'Выберите далнейшие действия',
            reply_markup=ReplyKeyboardMarkup(
                context.user_data.get('replay_keyboard'), one_time_keyboard=True, resize_keyboard=True
            ))
        return CHOICE
    else:
        context.user_data['status_type'] = 0
        ReplyKeyboardRemove()
        reply_keyboard = [['Дата сегодня', 'Дата завтра', 'Вернуться назад']]
        await update.message.reply_text(
            f"Введите дату двухнедельного статуса - формат - '%Y-%m-%d'. Двухнедельный статус подается на дату обзора доски",
            reply_markup=ReplyKeyboardMarkup(
                reply_keyboard, one_time_keyboard=False, resize_keyboard=True,
                input_field_placeholder="Напиши дату, или выбери пункт - Дата сегодня"
            ),
        )
        return WEEKLY_STATUS


async def weekly_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Функция выбора даты двухнедельного статуса и переход к введению

    Роль: любая

    Попадание в эту функцию(часть диалога): STATUS_TYPE_CHOICE -> WEEKLY_STATUS

    :update - сообщение от юзера
    :context - внутренний словарь, куда можно передавать переменные в другие функции
        - context.user_data["user_date"] - дата пользователя для статуса

    Развилка:
        - Вернуться назад - CHOICE
        - Переход к введениб статусов - STATUS
    """
    text = update.message.text
    if text == "Дата сегодня":
        context.user_data["user_date"] = datetime.now(
            timezone('Europe/Moscow')).strftime('%Y-%m-%d')
        await update.message.reply_text(
            "Теперь, пожалуйста, напиши свой статус",
            reply_markup=ReplyKeyboardRemove(),)
        return STATUS
    elif text == "Дата завтра":
        context.user_data["user_date"] = (
            datetime.now(timezone('Europe/Moscow')) + timedelta(days=1)).strftime('%Y-%m-%d')
        await update.message.reply_text(
            "Теперь, пожалуйста, напиши свой статус",
            reply_markup=ReplyKeyboardRemove(),)
        return STATUS
    elif text == 'Вернуться назад':
        await update.message.reply_text(
            'Выберите далнейшие действия',
            reply_markup=ReplyKeyboardMarkup(
                context.user_data.get('replay_keyboard'), one_time_keyboard=True, resize_keyboard=True
            ))
        return CHOICE
    else:
        context.user_data["user_date"] = text
        logger.info(update.message.text)
        await update.message.reply_text(
            "Теперь, пожалуйста, напиши свой статус", reply_markup=ReplyKeyboardRemove())
        return STATUS


async def status_type_get(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Функция получения типа статусов для выгрузки

    Роль: админ

    Попадание в эту функцию(часть диалога): CHOICE -> STATUS_TYPE_GET

    :update - сообщение от юзера
    :context - внутренний словарь, куда можно передавать переменные в другие функции

    Развилка:
        - Вернуться назад - CHOICE
        - Введение даты - GET_STATUS_DATE
    """
    text = update.message.text
    if text == 'Ежедневный':
        context.user_data['status_get_type'] = 1
    elif text == 'Вернуться назад':
        await update.message.reply_text(
            'Выберите далнейшие действия',
            reply_markup=ReplyKeyboardMarkup(
                context.user_data.get('replay_keyboard'), one_time_keyboard=True, resize_keyboard=True
            ))
        return CHOICE
    else:
        context.user_data['status_get_type'] = 0
    ReplyKeyboardRemove()
    reply_keyboard = [['Дата вчера', 'Дата сегодня', 'Вернуться назад']]
    await update.message.reply_text(
        f"Выберите сегодняшний день - Дата вчера или напишите свой день - формат - '%Y-%m-%d', если вы не будете использовать нужный формат, то оне не пустит дальше",
        reply_markup=ReplyKeyboardMarkup(
            reply_keyboard, one_time_keyboard=False,
            input_field_placeholder="Напиши дату, или выбери пункт - Дата вчера", resize_keyboard=True
        ),
    )
    return GET_STATUS_DATE


async def time_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Функция развилка в меню управления уведомлениями

    Роль: любая

    Попадание в эту функцию(часть диалога): CHOICE -> TIME_CHOICE

    :update - сообщение от юзера
    :context - внутренний словарь, куда можно передавать переменные в другие функции

    Развилка: 
        - Вернутсья назад - CHOICE
        - Получение расписания уведомлений - в рамках функции
        - Удалить расписание - DELETE_SCHEDULE
        - Заполнение расписания - SET_TIME
    """
    text = update.message.text
    if text == 'Посмотреть расписание уведомлений':
        query = f'''select id,time,days from tg_bot.chat_schedule where user_id = '{update.message.from_user.id}' '''
        message = sql_select(sql=query)
        message.set_index('id', inplace=True)

        await update.message.reply_text(
            f"{message.to_markdown()}"
        )
    elif text == 'Вернуться назад':
        await update.message.reply_text(
            'Выберите далнейшие действия',
            reply_markup=ReplyKeyboardMarkup(
                context.user_data.get('replay_keyboard'), one_time_keyboard=True, resize_keyboard=True
            ))
        return CHOICE
    elif text == 'Удалить расписание':
        await update.message.reply_text(
            'Введите id расписания, которое вы бы хотели удалить',
            reply_markup=ReplyKeyboardMarkup(
                [['Вернуться назад']], one_time_keyboard=True, resize_keyboard=True
            ))
        return DELETE_SCHEDULE
    else:
        await update.message.reply_text(
            "Заполните словарь"
        )
        await update.message.reply_text(
            "{'time':['07:00:00+03:00'], 'days':[(0,1,2,3,4,5,6)]}",
            reply_markup=ReplyKeyboardMarkup(
                [['Вернуться назад']], resize_keyboard=True)
        )
        return SET_TIME


async def delete_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Функция удаление одного из расписаний уведомлений

    Роль: любая

    Попадание в эту функцию(часть диалога): TIME_CHOICE -> SET_TIME

    :update - сообщение от юзера
    :context - добавление расписания в JOB_QUEUE

    Развилка: 
    - Вернутсья назад - TIME_CHOICE
    - Отрабатывание функции - CHOICE
    """
    text = update.message.text
    try:
        deleted_jobs = sql_select(
            sql=f'''select * from tg_bot.chat_schedule where id = {text}''')
        if deleted_jobs['user_id'].iloc[0] == update.message.from_user.id:
            query = f"DELETE FROM tg_bot.chat_s`chedule where id = {text}"
            for index, row in deleted_jobs.iterrows():
                name = 'task_' + "time_" + \
                    str(row['time']) + "days_" + row['days'] + \
                    'user_id_' + str(row['user_id'])
                current_jobs = context.job_queue.get_jobs_by_name(name)
                for job in current_jobs:
                    job.schedule_removal()
            sql_query(query)
            await update.message.reply_text(
                'Успешно удалено. Выберите пункт в меню',
                reply_markup=ReplyKeyboardMarkup(
                    [
                        ['Внести время', 'Посмотреть расписание уведомлений', 'Удалить расписание', 'Вернуться назад']], one_time_keyboard=True, resize_keyboard=True))
            return TIME_CHOICE
        else:
            await update.message.reply_text(
                'Вы ввели неправильное id расписания, скорее всего оно принадлежит другому человеку',
                reply_markup=ReplyKeyboardMarkup(
                    [
                        ['Внести время', 'Посмотреть расписание уведомлений', 'Удалить расписание', 'Вернуться назад']], one_time_keyboard=True, resize_keyboard=True
                ))
        return TIME_CHOICE
    except IndexError:
        await update.message.reply_text(
            'Нет такого расписания. Выберите пункт в меню',
            reply_markup=ReplyKeyboardMarkup(
                [
                    ['Внести время', 'Посмотреть расписание уведомлений', 'Удалить расписание', 'Вернуться назад']], one_time_keyboard=True, resize_keyboard=True
            ))
        return TIME_CHOICE


async def set_time(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Функция приема словаря уведомления от юзера

    Роль: любая

    Попадание в эту функцию(часть диалога): TIME_CHOICE -> SET_TIME

    :update - сообщение от юзера
    :context - добавление расписания в JOB_QUEUE

    Развилка: 
    - Вернутсья назад - TIME_CHOICE
    - Отрабатывание функции - CHOICE
    """
    if update.message.text == 'Вернуться назад':
        await update.message.reply_text(
            'Выберите пункт в меню',
            reply_markup=ReplyKeyboardMarkup(
                [
                    ['Внести время', 'Посмотреть расписание уведомлений', 'Удалить расписание', 'Вернуться назад']], one_time_keyboard=True, resize_keyboard=True
            ))
        return TIME_CHOICE
    else:
        df = eval(update.message.text)
        df['user_id'] = update.message.from_user.id
        df['chat_id'] = update.effective_message.chat_id
        df_timetable = pd.DataFrame(df)
        print(df_timetable)
        for index, row in df_timetable.iterrows():
            name = 'task_' + "time_" + \
                str(row['time']) + "days_" + str(row['days']) + \
                'user_id_' + str(row['user_id'])
            if context.job_queue.get_jobs_by_name(name):
                pass
            else:
                context.job_queue.run_daily(name=name,
                                            callback=callback, time=pd.to_datetime(row['time']), days=row['days'], user_id=row['user_id'], chat_id=row['chat_id'])
                insert(df=df_timetable, database_name='main_db',
                       table_name='chat_schedule', schema='tg_bot')
                await update.message.reply_text(
                    'Ваше расписание сохранено',
                    reply_markup=ReplyKeyboardMarkup(
                        context.user_data.get('replay_keyboard'), one_time_keyboard=True, resize_keyboard=True
                    ))
                return CHOICE


async def reg(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Функция приема ФИО от не юзера при регистрации

    Роль: не юзер бота

    Попадание в эту функцию(часть диалога): START -> REG

    :update - сообщение от юзера
    :context - внутренний словарь, куда можно передавать переменные в другие функции
        - context.user_data["real_name"] - ФИО юзера для инсерта
        - context.user_data["user_id"] - АЙДИ юзера для инсерта
        - context.user_data["username"] - Юзернейм юзера для инсерта 

    Функция линейна - REG -> REGISTRATION_TEAM
    """
    text = update.message.text
    context.user_data["real_name"] = text
    context.user_data["user_id"] = update.message.from_user.id
    context.user_data["username"] = update.message.from_user.username
    await update.message.reply_text(f"Напишите вашу команду")
    return REGISTRATION_TEAM


async def reg_team(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Функция приема команды от юзера при регистрации

    Роль: не юзер бота

    Попадание в эту функцию(часть диалога): REG -> REG_TEAM

    :update - сообщение от юзера
    :context - внутренний словарь, куда можно передавать переменные в другие функции
        - context.user_data['team'] - название команды

    Функция линейна - конец диалога, пока нового юзера не подтвердят
    """
    text = update.message.text
    context.user_data['team'] = text
    df_user_data = {'user_id': [context.user_data["user_id"]], 'username': [context.user_data["username"]],
                    'real_name': [context.user_data["real_name"]], 'is_user': [0],
                    'in_team': [0]}
    df_user_data = pd.DataFrame(df_user_data)
    insert(df=df_user_data, database_name='main_db',
           table_name='users', schema='tg_bot')
    ADMIN = sql_select('SELECT * FROM tg_bot.users WHERE is_user = 2')
    text = ""
    for i, row in ADMIN.iterrows():
        text += "@" + row['username']
        text += ', '
    await update.message.reply_text(f"Ваши данные записаны. Напишите администраторам {text[:-2]}. После подтверждения напишите /start")
    for index, row in ADMIN.iterrows():
        context.job_queue.run_once(
            callback=callback_admin, when=1, user_id=row['user_id'], chat_id=row['user_id'])
    return ConversationHandler.END


async def get_status_date(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Функция получении даты и выгрузки командных статусов от пользователей

    Роль: админ команды

    Попадание в эту функцию(часть диалога): STATUS_TYPE_GET -> GET_STATUS_DATE

    :update - сообщение от юзера
    :context - внутренний словарь, куда можно передавать переменные в другие функции

    Развилка:
        - Вернуться назад - CHOICE
        - Функция линейна и вне зависимости от даты или ошибки при введении даты - CHOICE
    """
    text = update.message.text
    if text == "Дата вчера":
        date = (
            datetime.now(timezone('Europe/Moscow')) - timedelta(days=1)).strftime('%Y-%m-%d')
        query = f'''
                with cte as (
                select *, row_number() over (partition by s.user_id order by tech_load_ts desc) as rn from tg_bot.STATUS s
                left join tg_bot.users u on s.user_id = u.user_id
                where date = '{date}' and is_daily = {context.user_data['status_get_type']}
                and team_id = {context.user_data.get('user_team_pick')}
                )
                select * from cte
                where rn = 1 '''
        USER_STATUS = sql_select(sql=query)
        result = get_ready_text(USER_STATUS)
        if type(result) == str:
            await update.message.reply_text(
                result,
                reply_markup=ReplyKeyboardMarkup(
                    context.user_data.get('replay_keyboard'), one_time_keyboard=True, resize_keyboard=True
                ),
                parse_mode=constants.ParseMode.HTML)
            return CHOICE
        else:
            for statuses in result:
                await update.message.reply_text(
                    str(statuses),
                    parse_mode=constants.ParseMode.HTML)
            await update.message.reply_text('Выгрузка закончена',
                                            reply_markup=ReplyKeyboardMarkup(
                                                context.user_data.get('replay_keyboard'), one_time_keyboard=True, resize_keyboard=True
                                            ))
            return CHOICE
    elif text == 'Вернуться назад':
        await update.message.reply_text(
            'Выберите дальнейшие действия:',
            reply_markup=ReplyKeyboardMarkup(
                context.user_data.get('replay_keyboard'), one_time_keyboard=True, resize_keyboard=True
            ))
        return CHOICE
    elif text == 'Дата сегодня':
        date = (datetime.now(timezone('Europe/Moscow'))).strftime('%Y-%m-%d')
        query = f'''
                with cte as (
                select *, row_number() over (partition by s.user_id order by tech_load_ts desc) as rn from tg_bot.STATUS s
                left join tg_bot.users u on s.user_id = u.user_id
                where date = '{date}' and is_daily = {context.user_data['status_get_type']}
                and team_id = {context.user_data.get('user_team_pick')}
                )
                select * from cte
                where rn = 1 '''
        USER_STATUS = sql_select(sql=query)
        result = get_ready_text(USER_STATUS)
        if type(result) == str:
            await update.message.reply_text(
                result,
                reply_markup=ReplyKeyboardMarkup(
                    context.user_data.get('replay_keyboard'), one_time_keyboard=True, resize_keyboard=True
                ),
                parse_mode=constants.ParseMode.HTML)
            return CHOICE
        else:
            for statuses in result:
                await update.message.reply_text(
                    str(statuses),
                    parse_mode=constants.ParseMode.HTML)
            await update.message.reply_text('Выгрузка закончена',
                                            reply_markup=ReplyKeyboardMarkup(
                                                context.user_data.get('replay_keyboard'), one_time_keyboard=True, resize_keyboard=True
                                            ))
            return CHOICE
    else:
        date = text
        query = f'''
                with cte as (
                select *, row_number() over (partition by s.user_id order by tech_load_ts desc) as rn from tg_bot.STATUS s
                left join tg_bot.users u on s.user_id = u.user_id
                where date = '{date}' and is_daily = {context.user_data['status_get_type']}
                and team_id = {context.user_data.get('user_team_pick')}
                )
                select * from cte
                where rn = 1 '''
        USER_STATUS = sql_select(sql=query)
        result = get_ready_text(USER_STATUS)
        if type(result) == str:
            await update.message.reply_text(
                result,
                reply_markup=ReplyKeyboardMarkup(
                    context.user_data.get('replay_keyboard'), one_time_keyboard=True, resize_keyboard=True
                ),
                parse_mode=constants.ParseMode.HTML)
            return CHOICE
        else:
            for statuses in result:
                await update.message.reply_text(
                    str(statuses),
                    parse_mode=constants.ParseMode.HTML)
            await update.message.reply_text('Выгрузка закончена',
                                            reply_markup=ReplyKeyboardMarkup(
                                                context.user_data.get('replay_keyboard'), one_time_keyboard=True, resize_keyboard=True
                                            ))
            return CHOICE


async def date(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Функция получении даты для статуса от пользователя

    Роль: любая

    Попадание в эту функцию(часть диалога): STATUS_TYPE_CHOICE -> DATE

    :update - сообщение от юзера
    :context - внутренний словарь, куда можно передавать переменные в другие функции
        - context.user_data["user_date"] - получение даты пользователя

    Развилка:
        - Вернуться назад - CHOICE
        - Продолжение отправки статусов - STATUS
    """
    text = update.message.text
    if text == "Дата сегодня":
        context.user_data["user_date"] = datetime.now(
            timezone('Europe/Moscow')).strftime('%Y-%m-%d')
        await update.message.reply_text(
            "Теперь, пожалуйста, напиши свой статус",
            reply_markup=ReplyKeyboardRemove(),)
        return STATUS
    elif text == "Дата вчера":
        context.user_data["user_date"] = (
            datetime.now(timezone('Europe/Moscow')) - timedelta(days=1)).strftime('%Y-%m-%d')
        await update.message.reply_text(
            "Теперь, пожалуйста, напиши свой статус",
            reply_markup=ReplyKeyboardRemove(),)
        return STATUS
    elif text == 'Вернуться назад':
        await update.message.reply_text(
            'Выберите далнейшие действия',
            reply_markup=ReplyKeyboardMarkup(
                context.user_data.get('replay_keyboard'), one_time_keyboard=True, resize_keyboard=True
            ))
        return CHOICE
    else:
        if text > datetime.now(timezone('Europe/Moscow')).strftime('%Y-%m-%d'):
            reply_keyboard = [['Дата сегодня', 'Вернуться назад']]
            await update.message.reply_text(
                f"Вы ввели дату, которая еще не наступила выберите - Дата сегодня или напишите свой день - формат - '%Y-%m-%d', если вы не будете использовать нужный формат, то оне не пустит дальше",
                reply_markup=ReplyKeyboardMarkup(
                    reply_keyboard, one_time_keyboard=False, resize_keyboard=True,
                    input_field_placeholder="Напиши дату, или выбери пункт - Дата сегодня"
                ),
            )
            return DATE
        else:
            context.user_data["user_date"] = text
            logger.info(update.message.text)
            await update.message.reply_text(
                "Теперь, пожалуйста, напиши свой статус", reply_markup=ReplyKeyboardRemove())
            return STATUS


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Функция записи текста статуса от пользователя и переход к валидации

    Роль: любая

    Попадание в эту функцию(часть диалога): DATE -> STATUS

    :update - сообщение от юзера
    :context - внутренний словарь, куда можно передавать переменные в другие функции
        - context.user_data["user_id"] - айди пользователя
        - context.user_data["username"] - получение юзернейма пользователя
        - context.user_data["user_status"] - получение текста пользователя

    Функция линейна и ведет к валидации статуса пользователем. STATUS -> VALIDATION
    """
    context.user_data["user_id"] = update.message.from_user.id
    context.user_data["username"] = update.message.from_user.username
    context.user_data["user_status"] = update.message.text_html
    reply_keyboard = [["Да", "Нет"]]
    if context.user_data['status_type'] == 1:
        type_of_status = 'ежедневный'
    else:
        type_of_status = 'двухнедельный'
    await update.message.reply_text(
        text=f'''Дата: {context.user_data.get('user_date')}\nТип статуса: {type_of_status}\nСтатус: {context.user_data.get('user_status')}\nПодтвердить?''',
        reply_markup=ReplyKeyboardMarkup(
            reply_keyboard, one_time_keyboard=True, resize_keyboard=True
        ),
        parse_mode=constants.ParseMode.HTML)
    return VALIDATION


async def valid(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Функция отправки статусов в БД со стороны юзера

    Роль: любая

    Попадание в эту функцию(часть диалога): STATUS -> VALID

    :update - сообщение от юзера
    :context - внутренний словарь, куда можно передавать переменные в другие функции

    Функция линейна, но если пользователь напишет "Да", то запись появится в БД и пользователь попадает в CHOICE, 
    если нет, то пользователь попадает в CHOICE без записи в БД
    """
    if update.message.text == "Да":
        df = {'user_id': [context.user_data["user_id"]], 'username': [context.user_data["username"]],
              'status': [context.user_data["user_status"]], 'date': [context.user_data["user_date"]],
              'is_daily': [context.user_data['status_type']],
              'team_id': [context.user_data['user_team_pick']]}
        df = pd.DataFrame(df)
        insert(df=df, database_name='main_db',
               table_name='status', schema='tg_bot')
        await update.message.reply_text(
            'Все ходы записаны',
            reply_markup=ReplyKeyboardMarkup(
                context.user_data.get('replay_keyboard'), one_time_keyboard=True, resize_keyboard=True
            ))
        return CHOICE
    else:
        await update.message.reply_text(
            'Начинай заново',
            reply_markup=ReplyKeyboardMarkup(
                context.user_data.get('replay_keyboard'), one_time_keyboard=True, resize_keyboard=True
            ))
        return CHOICE


async def cancel(update: Update) -> int:
    """
    Функция, которая завершает беседу с Ботом

    Попадание в функцию(часть диалога) - /cancel команда из любой части диалога

    :update - сообщение от юзера
    """
    user = update.message.from_user
    logger.info("User %s canceled the conversation.", user.first_name)
    await update.message.reply_text(
        "Bye! I hope we can talk again some day.", reply_markup=ReplyKeyboardRemove()
    )
    return ConversationHandler.END


async def callback(context: CallbackContext):
    """
    Функция отправки сообщения пользователям, что о необходимости отправки статуса

    :context - передается через джобу в Jobqueue
    """
    job = context.job
    await context.bot.send_message(job.chat_id, text=f"Отправьте статус (ежедневный или двухнедельный). Двухнедельный статус подается на дату обзора доски")


async def callback_admin(context: CallbackContext):
    """
    Функция отправки сообщения администраторам, что появились заявки на подтверждение

    :context - передается через джобу в Jobqueue
    """
    job = context.job
    await context.bot.send_message(job.chat_id, text=f"Появились заявки на подтверждение")


async def check_schedule(application: Application) -> None:
    """
    Функция инициализации расписания при запуске бота. 
    Все записи с уведомлениями передаются в JobQueue

    :application - приложение передается, для запуска в рамках бота
    """
    SCHEDULE = sql_select('SELECT * FROM tg_bot.chat_schedule')
    for index, row in SCHEDULE.iterrows():
        name = 'task_' + "time_" + \
            str(row['time']) + "days_" + row['days'] + \
            'user_id_' + str(row['user_id'])
        if application.job_queue.get_jobs_by_name(name):
            pass
        else:
            application.job_queue.run_daily(name=name,
                                            callback=callback, time=row['time'], days=eval(row['days']), user_id=row['user_id'], chat_id=row['chat_id'])


async def restart(update: Update) -> int:
    """
    Функция для рестарта бота любым человеком

    Попадание в функцию: /restart - из любого места

    :update - сообщение от юзера

    Роль: любая

    Развилка: 
        - Попадание в начало - START
    """
    await update.message.reply_text(
        'Нажми на кнопку – получишь результат',
        reply_markup=ReplyKeyboardMarkup(
            [['Нажми для рестарта']], one_time_keyboard=True, resize_keyboard=True
        ))
    return START

# ------------------------------------------------------------------------------------------------------------------


def main() -> None:
    """
    Функция запуска ТГ бота

    :ConversationHandler - функция контролирующая переход между этапами диалога
    """
    application = Application.builder().token(
        TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            START: [MessageHandler(filters.TEXT & ~filters.COMMAND, start)],
            START_ACTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, start_action)],
            SUPER_USER_CHOICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, super_user_choice)],
            REGISTRATION: [MessageHandler(
                filters.TEXT & ~filters.COMMAND, reg)],
            REGISTRATION_TEAM: [MessageHandler(filters.TEXT & ~filters.COMMAND, reg_team)],
            CHOICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, choice)],
            TIME_CHOICE: [MessageHandler(
                filters.TEXT & ~filters.COMMAND, time_choice)],
            GET_STATUSES: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_statuses)],
            CHANGE_TEAM_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, change_team_name)],
            TEAM_CONTROL: [MessageHandler(filters.TEXT & ~filters.COMMAND, team_control)],
            TEAM_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, team_id)],
            ADD_TEAM: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_team)],
            USER_ID_GET_STATUS: [MessageHandler(filters.TEXT & ~filters.COMMAND, user_id_get_status)],
            STATUS_TYPE_WRITE: [MessageHandler(filters.Regex(r'Ежедневный|Двухнедельный|Вернуться назад'), status_type_choice)],
            STATUS_TYPE_GET: [MessageHandler(filters.Regex(r'Ежедневный|Двухнедельный|Вернуться назад'), status_type_get)],
            LOWER_LIMIT: [MessageHandler(filters.Regex(r'\d{4}-\d{2}-\d{2}|Дата сегодня|Вернуться назад'), lower_limit)],
            UPPER_LIMIT: [MessageHandler(filters.Regex(r'\d{4}-\d{2}-\d{2}'), upper_limit)],
            ASSIGN_TEAM: [MessageHandler(filters.TEXT & ~filters.COMMAND, assign_team)],
            ASSIGN_TEAM_ROLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, assign_team_role)],
            USER_TEAM_RECORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, user_team_record)],
            ADMIN_ACTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_action)],
            ADMIN_CHOICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_choice)],
            ROLE_USER_PICK: [MessageHandler(filters.TEXT & ~filters.COMMAND, role_user_pick)],
            ROLE_USER: [MessageHandler(filters.TEXT & ~filters.COMMAND, role_user)],
            WEEKLY_STATUS: [MessageHandler(filters.Regex(r'\d{4}-\d{2}-\d{2}|Дата сегодня|Дата завтра|Вернуться назад'), weekly_status)],
            SET_TIME: [MessageHandler(
                filters.Regex(r"\{'time':\['\d{2}:\d{2}:\d{2}\+\d{2}:\d{2}'\],\s*'days':\[\((\d,?)*\)\]\}|Вернуться назад"), set_time)],
            GET_STATUS_DATE: [MessageHandler(filters.Regex('\d{4}-\d{2}-\d{2}|Дата вчера|Вернуться назад|Дата сегодня|'), get_status_date)],
            DATE: [MessageHandler(filters.Regex(r'\d{4}-\d{2}-\d{2}|Дата сегодня|Дата вчера|Вернуться назад'), date)],
            DELETE_SCHEDULE: [MessageHandler(filters.TEXT & ~filters.COMMAND, delete_schedule)],
            STATUS: [MessageHandler(filters.TEXT & ~filters.COMMAND, status)],
            VALIDATION: [MessageHandler(filters.Regex('Да|Нет'), valid)]
        },
        fallbacks=[CommandHandler("cancel", cancel),
                   CommandHandler("restart", restart)]
    )

    application.add_handler(conv_handler)

    loop = asyncio.get_event_loop()
    loop.create_task(check_schedule(application))

    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
