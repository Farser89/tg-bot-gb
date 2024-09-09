from db_utils import sql_select
import pandas as pd


def check_role(id):
    USERS = sql_select('SELECT * FROM tg_bot.users WHERE is_user = 1')
    USERS_WHO_WAIT = sql_select('SELECT * FROM tg_bot.users WHERE is_user = 0')
    ADMIN = sql_select('SELECT * FROM tg_bot.users WHERE is_user = 2')
    USERS_WHO_BLOCKED = sql_select(
        'SELECT * FROM tg_bot.users WHERE is_user = -1')
    if int(id) in list(USERS['user_id']):
        return 1
    elif int(id) in list(USERS_WHO_WAIT['user_id']):
        return 0
    elif int(id) in list(ADMIN['user_id']):
        return 2
    elif int(id) in list(USERS_WHO_BLOCKED['user_id']):
        return -1


def get_admins():
    ADMIN = sql_select('SELECT * FROM tg_bot.users WHERE is_user = 2')
    text = ""
    for i, row in ADMIN.iterrows():
        text += "@" + row['username']
        text += ', '
    return text[:-2]


def get_ready_text(df) -> str:
    try:
        list_of_texts = []
        text = '<b>' + str(df['date'].iloc[0]) + '</b>'
        text += "\n\n"
        for index, row in df.iterrows():
            user_text = '<b>' + row["real_name"] + '.' + '</b>'
            user_text += "\n\n"
            user_text += row['status']
            user_text += "\n\n"
            if len(text) + len(user_text) > 3000:
                list_of_texts.append(text)
                text = user_text
            else:
                text += user_text

        if text:
            list_of_texts.append(text)
        return list_of_texts
    except IndexError:
        return 'Нет данных по этому дню: либо вы выбираете дату в будущем, либо никто статусы за это число не прислал'


def check_team(user_id):
    query = f'''select user_id, t.team_id, t.team_name, rt.team_role from tg_bot.role_team as rt
    right join tg_bot.teams t on rt.team_id = t.team_id
    where user_id = {user_id} and rt.team_role > 0'''
    DF = sql_select(query)
    dict_of_roles = {}
    for index, row in DF.iterrows():
        dict_of_roles[row['team_name']] = row['team_role']
    return dict_of_roles


def get_team_id(team):
    query = f'''select * from tg_bot.teams'''
    DF = sql_select(query)
    dict_of_team_id = {}
    for index, row in DF.iterrows():
        dict_of_team_id[row['team_name']] = row['team_id']
    return dict_of_team_id[team]


def get_ready_text_own(df) -> str:
    try:
        list_of_texts = []
        text = ''
        for index, row in df.iterrows():
            user_text = '<b>' + str(row['date']) + '</b>'
            user_text += "\n\n"
            user_text += row['status']
            user_text += "\n\n"
            if len(text) + len(user_text) > 3000:
                list_of_texts.append(text)
                text = user_text
            else:
                text += user_text

        if text:
            list_of_texts.append(text)
        return list_of_texts
    except IndexError:
        return 'Нет данных по этому дню: либо вы выбираете дату в будущем, либо никто статусы за это число не прислал'
