import time
import sqlite3
from lutris.util.log import logger

# Number of attempts to retry failed queries
DB_RETRIES = 5


class db_cursor(object):
    def __init__(self, db_path):
        self.db_path = db_path

    def __enter__(self):
        self.db_conn = sqlite3.connect(self.db_path)
        cursor = self.db_conn.cursor()
        return cursor

    def __exit__(self, type, value, traceback):
        self.db_conn.commit()
        self.db_conn.close()


def cursor_execute(cursor, query, params=None):
    """Function used to retry queries in case an error occurs"""
    i = 0
    if params is None:
        params = ()
    while True:
        try:
            return cursor.execute(query, params)
        except sqlite3.OperationalError as ex:
            i += 1
            if i == DB_RETRIES:
                raise
            else:
                logger.error("SQL query '%s' failed. %d retries remaining",
                             query,
                             DB_RETRIES - i)
                logger.error(ex)
                time.sleep(1)


def db_insert(db_path, table, fields):
    columns = ", ".join(list(fields.keys()))
    placeholders = ("?, " * len(fields))[:-2]
    field_values = _decode_utf8_values(list(fields.values()))
    with db_cursor(db_path) as cursor:
        try:
            cursor_execute(
                cursor,
                "insert into {0}({1}) values ({2})".format(
                    table, columns, placeholders
                ),
                field_values
            )
        except sqlite3.IntegrityError:
            print(columns)
            print(field_values)
            raise
        inserted_id = cursor.lastrowid
    return inserted_id


def db_update(db_path, table, updated_fields, row):
    """Update `table` with the values given in the dict `values` on the
       condition given with the `row` tuple.
    """
    columns = "=?, ".join(list(updated_fields.keys())) + "=?"
    field_values = _decode_utf8_values(list(updated_fields.values()))
    condition_field = "{0}=?".format(row[0])
    condition_value = (row[1], )
    with db_cursor(db_path) as cursor:
        query = "UPDATE {0} SET {1} WHERE {2}".format(table, columns,
                                                      condition_field)
        cursor_execute(cursor, query, field_values + condition_value)


def db_delete(db_path, table, field, value):
    with db_cursor(db_path) as cursor:
        cursor_execute(cursor,
                       "delete from {0} where {1}=?".format(table, field),
                       (value,))


def db_select(db_path, table, fields=None, condition=None):
    if fields:
        columns = ", ".join(fields)
    else:
        columns = "*"
    with db_cursor(db_path) as cursor:
        if condition:
            assert len(condition) == 2
            query = "SELECT {0} FROM {1} where {2}=?".format(columns,
                                                             table,
                                                             condition[0])
            params = (condition[1], )
        else:
            query = "SELECT {0} FROM {1}".format(columns, table)
            params = ()
        cursor_execute(cursor, query, params)
        rows = cursor.fetchall()
        column_names = [column[0] for column in cursor.description]
    results = []
    for row in rows:
        row_data = {}
        for index, column in enumerate(column_names):
            row_data[column] = row[index]
        results.append(row_data)
    return results


def db_query(db_path, query, params=()):
    with db_cursor(db_path) as cursor:
        cursor_execute(cursor, query, params)
        rows = cursor.fetchall()
        column_names = [column[0] for column in cursor.description]
    results = []
    for row in rows:
        row_data = {}
        for index, column in enumerate(column_names):
            row_data[column] = row[index]
        results.append(row_data)
    return results


def _decode_utf8_values(values_list):
    """Return a tuple of values with UTF-8 string values being decoded.
    XXX Might be obsolete in Python3 (Removed the decoding part)
    """
    i = 0
    for v in values_list:
        if type(v) is str:
            values_list[i] = v
        i += 1
    return tuple(values_list)


def add_field(db_path, tablename, field):
    query = "ALTER TABLE %s ADD COLUMN %s %s" % (
        tablename, field['name'], field['type']
    )
    with db_cursor(db_path) as cursor:
        cursor.execute(query)
