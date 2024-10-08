import psycopg
from psycopg import sql
import logging

# Async connection creation for psycopg3
async def get_db_connection():
    conn = await psycopg.AsyncConnection.connect(
        user="postgres",
        password="Th1nkeRLDMUsmonov",
        host="localhost",
        port="5432",
        dbname="postgres"
    )
    
    # Set client encoding to UTF-8
    async with conn.cursor() as cursor:
        await cursor.execute("SET client_encoding TO 'UTF8'")
    
    return conn

async def insert_user_if_not_exists(user_id: int, user_name: str):
    conn = await get_db_connection()
    try:
        async with conn.cursor() as cur:
            # Insert the user, or update the user_name if the user_id already exists
            await cur.execute(
                """
                INSERT INTO users (user_id, user_name)
                VALUES (%s, %s)
                ON CONFLICT (user_id) DO UPDATE
                SET user_name = EXCLUDED.user_name;
                """,
                (user_id, user_name)
            )
            # Commit the transaction to make sure the insertion or update is saved
            await conn.commit()
            logging.info(f"User with ID {user_id} inserted or updated.")
    except Exception as e:
        logging.error(f"Error inserting or updating user: {e}")
    finally:
        # Ensure the connection is closed
        await conn.close()



async def check_file_exists(file_id: str) -> bool:
    conn = await get_db_connection()
    try:
        async with conn.cursor() as cur:
            # Execute a query to check if the file_id exists in the input_file table
            await cur.execute(
                """
                SELECT EXISTS (
                    SELECT 1
                    FROM input_file
                    WHERE file_id = %s
                );
                """,
                (file_id,)
            )
            # Fetch the result
            result = await cur.fetchone()
            # Extract the boolean value from the result
            file_exists = result[0]
            return file_exists
    except Exception as e:
        logging.error(f"Error checking file existence: {e}")
        return False
    finally:
        # Ensure the connection is closed
        await conn.close()


async def get_message_id_by_id(record_id: int):
    conn = await get_db_connection()  # Assuming you have get_db_connection() defined
    try:
        async with conn.cursor() as cur:
            # Query to get the message_id by id
            await cur.execute(
                """
                SELECT message_id
                FROM output_file
                WHERE id = %s;
                """,
                (record_id,)
            )
            
            result = await cur.fetchone()  # Fetch one result
            if result:
                message_id = result[0]  # Extract message_id from the result tuple
                return message_id
            else:
                logging.info(f"No entry found for id: {record_id}")
                return None
    except Exception as e:
        logging.error(f"Error retrieving message_id: {e}")
        return None
    finally:
        # Ensure the connection is closed
        await conn.close()


async def insert_into_input_file(file_id: str, file_name: str):
    conn = await get_db_connection()  # Assuming you have get_db_connection() defined
    try:
        async with conn.cursor() as cur:
            # Insert into the input_file table
            await cur.execute(
                """
                INSERT INTO input_file (file_id, file_name)
                VALUES (%s, %s);
                """,
                (file_id, file_name)
            )
            await conn.commit()  # Commit the transaction to save the data
            logging.info(f"Inserted into input_file: file_id={file_id}")
    except Exception as e:
        logging.error(f"Error inserting into input_file: {e}")
    finally:
        await conn.close()  # Ensure the connection is closed


async def check_file_exists_with_percentage(file_id: str, percent: int) -> bool:

    conn = await get_db_connection()
    try:
        # Dynamically create the column name based on the percentage
        column_name = f"out_{percent}_id"

        async with conn.cursor() as cur:
            # Execute a query to check if the file_id exists and the column out_{percent}_id is not 0
            query = f"""
                SELECT EXISTS (
                    SELECT 1
                    FROM input_file
                    WHERE file_id = %s AND {column_name} != 0
                );
            """
            await cur.execute(query, (file_id,))
            
            # Fetch the result
            result = await cur.fetchone()

            # Extract the boolean value from the result
            file_exists = result[0]
            return file_exists
    except Exception as e:
        logging.error(f"Error checking file existence with {percent}%: {e}")
        return False
    finally:
        # Ensure the connection is closed
        await conn.close()

async def get_output_id_for_percentage(file_id: str, percent: int) -> int:
    conn = await get_db_connection()
    try:
        # Dynamically create the column name based on the percentage
        column_name = f"out_{percent}_id"

        async with conn.cursor() as cur:
            # Execute a query to fetch the value of out_{percent}_id for the given file_id
            query = f"""
                SELECT {column_name}
                FROM input_file
                WHERE file_id = %s;
            """
            await cur.execute(query, (file_id,))
            
            # Fetch the result
            result = await cur.fetchone()

            # Extract and return the value from the result, or return 0 if the column is null
            return result[0] if result else 0
    except Exception as e:
        logging.error(f"Error fetching output ID for {percent}%: {e}")
        return 0  # Return 0 in case of any error
    finally:
        # Ensure the connection is closed
        await conn.close()


async def get_chat_and_message_id_by_id(id: int, percentage: int):
    table_name = f"out_{percentage}"  # Dynamic table name based on percentage
    conn = await get_db_connection()  # Assuming you have an async function to get DB connection
    try:
        async with conn.cursor() as cur:
            # Query to retrieve chat_id and message_id based on the given id
            query = f"""
                SELECT chat_id, message_id
                FROM {table_name}
                WHERE id = %s;
            """
            await cur.execute(query, (id,))
            result = await cur.fetchone()

            if result:
                chat_id, message_id = result
                return chat_id, message_id
            else:
                logging.info(f"No record found in {table_name} with id {id}.")
                return None, None
    except Exception as e:
        logging.error(f"Error retrieving chat_id and message_id from {table_name}: {e}")
        return None, None
    finally:
        await conn.close()

import logging

async def get_name_by_id(file_id: str) -> str:
    conn = await get_db_connection()
    try:
        async with conn.cursor() as cur:
            # Execute a query to fetch the file_name for the given file_id
            query = """
                SELECT file_name
                FROM input_file
                WHERE file_id = %s;
            """
            await cur.execute(query, (file_id,))
            
            # Fetch the result
            result = await cur.fetchone()

            # Return the file_name if found, or None if not found
            return result[0] if result else None
    except Exception as e:
        logging.error(f"Error fetching file_name for file_id {file_id}: {e}")
        return None  # Return None in case of any error
    finally:
        # Ensure the connection is closed
        await conn.close()

async def insert_chat_and_message_id(chat_id: int, message_id: int, percentage: int):
    """
    Inserts chat_id and message_id into the dynamically selected table based on percentage 
    and returns the id of the newly inserted row.
    """
    table_name = f"out_{percentage}"  # Dynamic table name based on percentage
    conn = await get_db_connection()  # Assuming you have an async function to get DB connection
    try:
        async with conn.cursor() as cur:
            # Query to insert chat_id and message_id and return the id of the inserted row
            query = f"""
                INSERT INTO {table_name} (chat_id, message_id)
                VALUES (%s, %s)
                RETURNING id;
            """
            await cur.execute(query, (chat_id, message_id))
            result = await cur.fetchone()  # Fetch the returning id
            inserted_id = result[0] if result else None
            await conn.commit()  # Commit the transaction
            logging.info(f"Successfully inserted into {table_name} with chat_id {chat_id} and message_id {message_id}.")
            return inserted_id
    except Exception as e:
        logging.error(f"Error inserting into {table_name}: {e}")
        return None
    finally:
        await conn.close()

async def update_out_id_by_percent(file_id: str, out_id: int, percent: int):
    # Determine the column name dynamically based on the percent (0 or 15)
    out_column = f"out_{percent}_id"

    # SQL query to update the specific out_id column based on file_id
    query = f"""
        UPDATE input_file
        SET {out_column} = %s
        WHERE file_id = %s;
    """

    conn = await get_db_connection()
    try:
        async with conn.cursor() as cur:
            # Execute the query, passing out_id and file_id
            await cur.execute(query, (out_id, file_id))
            await conn.commit()
            logging.info(f"Successfully updated {out_column} for file_id {file_id}.")
    except Exception as e:
        logging.error(f"Error updating {out_column} for file_id {file_id}: {e}")
    finally:
        await conn.close()


async def get_id_by_file_id(file_id: str):
    """
    Retrieves the id from the table based on the given file_id.

    :param file_id: The file identifier to search for.
    :return: The id associated with the given file_id, or None if not found.
    """
    query = """
        SELECT id
        FROM input_file
        WHERE file_id = %s;
    """
    
    conn = await get_db_connection()  # Assuming you have an async function to get DB connection
    try:
        async with conn.cursor() as cur:
            await cur.execute(query, (file_id,))
            result = await cur.fetchone()  # Fetch the first matching result
            
            if result:
                return result[0]  # Return the id
            else:
                logging.info(f"No record found for file_id: {file_id}.")
                return None
    except Exception as e:
        logging.error(f"Error retrieving id for file_id {file_id}: {e}")
        return None
    finally:
        await conn.close()

async def get_file_id_by_id(id: int):
    """
    Retrieves the file_id from the table based on the given id.

    :param id: The identifier to search for.
    :return: The file_id associated with the given id, or None if not found.
    """
    query = """
        SELECT file_id
        FROM input_file
        WHERE id = %s;
    """
    
    conn = await get_db_connection()  # Assuming you have an async function to get DB connection
    try:
        async with conn.cursor() as cur:
            await cur.execute(query, (id,))
            result = await cur.fetchone()  # Fetch the first matching result
            
            if result:
                return result[0]  # Return the file_id
            else:
                logging.info(f"No record found for id: {id}.")
                return None
    except Exception as e:
        logging.error(f"Error retrieving file_id for id {id}: {e}")
        return None
    finally:
        await conn.close()


async def get_user_ids():
    """
    Retrieves the full list of user_ids from the 'users' table.

    :return: A list of all user_ids or an empty list if no users are found.
    """
    query = """
        SELECT user_id
        FROM users;
    """
    
    conn = await get_db_connection()  # Assuming you have an async function to get DB connection
    try:
        async with conn.cursor() as cur:
            await cur.execute(query)
            result = await cur.fetchall()  # Fetch all matching results
            
            if result:
                # Extract user_id from each row and return as a list
                user_ids = [row[0] for row in result]
                return user_ids
            else:
                logging.info("No users found in the table.")
                return []
    except Exception as e:
        logging.error(f"Error retrieving user_ids: {e}")
        return []
    finally:
        await conn.close()