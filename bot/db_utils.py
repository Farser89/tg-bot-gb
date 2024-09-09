from sqlalchemy import create_engine, text
import sqlalchemy
import pandas as pd
import re

DATABASE_URL = "postgresql+psycopg2://user:qwerty12345@localhost/main_db"
engine = create_engine(DATABASE_URL)


def sql_select(sql):
    return pd.read_sql_query(sql, engine)


def sql_query(query):
    with engine.connect() as conn:
        with conn.begin():
            conn.execute(text(query))
            return 1


def insert(df, database_name, table_name, schema):
    df.to_sql(
        name=table_name,
        con=engine,
        schema=f"{schema}",
        if_exists="append",  # fail // append // replace
        index=False
    )

    return True


def list_to_snakecase(input_list: str):
    new_names = []
    for column_name in input_list:
        new_name = column_name.replace(
            " ", "_").replace(".", "").replace("%", "")
        new_name = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", new_name)
        new_name = re.sub("([a-z0-9])([A-Z])", r"\1_\2", new_name).lower()
        new_names.append(new_name)
    return new_names


def df_column_names_to_snakecase(df: pd.DataFrame):
    new_names = list_to_snakecase(df.columns)
    df.columns = new_names
    return df
