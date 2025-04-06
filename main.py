import sqlite3
import pandas as pd
import os
import traceback
from datetime import datetime

import openai

# Replace with your OpenAI API key securely
openai.api_key = "your-api-key-here"

def generate_sql_with_llm(schema_description, user_query):
    prompt = f"""
You are an AI assistant tasked with converting user queries into SQL statements.
The database uses SQLite and contains the following tables:
{schema_description}

User Query: "{user_query}"

Your task is to:
1. Generate a SQL query that accurately answers the user's question.
2. Ensure the SQL is compatible with SQLite syntax.
3. Provide a short comment explaining what the query does.

Output Format:
- SQL Query
- Explanation
"""
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",  # or gpt-4
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2
    )

    return response['choices'][0]['message']['content']

def format_schema_for_llm(cursor):
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    schema_lines = []
    for (table,) in tables:
        cursor.execute(f"PRAGMA table_info('{table}')")
        columns = cursor.fetchall()
        col_list = ', '.join([col[1] for col in columns])
        schema_lines.append(f"- {table} ({col_list})")
    return "\n".join(schema_lines)

# Log errors to a file
def log_error(error_msg):
    with open("error_log.txt", "a") as f:
        f.write(f"{datetime.now()} - {error_msg}\n")

# Get existing schema using PRAGMA
def get_existing_schema(cursor, table_name):
    cursor.execute(f"PRAGMA table_info('{table_name}')")
    return cursor.fetchall()

# Create table from DataFrame
def create_table_from_df(df, table_name, conn):
    dtype_map = {
        'object': 'TEXT',
        'int64': 'INTEGER',
        'float64': 'REAL',
        'bool': 'INTEGER',
        'datetime64[ns]': 'TEXT'
    }
    cols = []
    for col in df.columns:
        dtype = str(df[col].dtype)
        sql_type = dtype_map.get(dtype, 'TEXT')
        cols.append(f'"{col}" {sql_type}')
    col_str = ", ".join(cols)
    conn.execute(f'CREATE TABLE "{table_name}" ({col_str});')
    conn.commit()

# List tables
def list_tables(conn):
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    return [t[0] for t in tables]

# Main interaction loop
def interactive_sqlite_bot(db_path='example.db'):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    print("📦 Welcome to SQLite Assistant!")
    
    while True:
        try:
            print("\nChoose an option:")
            print("[1] Load CSV")
            print("[2] Run SQL query")
            print("[3] Ask a question (AI-generated SQL)")
            print("[4] List tables")
            print("[5] Exit")
            choice = input("👉 Enter choice: ").strip()

            if choice == '1':
                file_path = input("📁 Enter CSV file path: ").strip()
                if not os.path.exists(file_path):
                    print("❌ File does not exist.")
                    continue
                df = pd.read_csv(file_path)
                table_name = input("🧱 Enter table name to create in DB: ").strip()
                
                existing_schema = get_existing_schema(cursor, table_name)
                if existing_schema:
                    print(f"⚠️ Table '{table_name}' already exists.")
                    action = input("Type 'overwrite', 'rename', or 'skip': ").strip().lower()
                    if action == 'overwrite':
                        cursor.execute(f'DROP TABLE IF EXISTS "{table_name}"')
                        create_table_from_df(df, table_name, conn)
                        df.to_sql(table_name, conn, if_exists='append', index=False)
                        print(f"✅ Table '{table_name}' overwritten and loaded.")
                    elif action == 'rename':
                        new_table = input("Enter new table name: ").strip()
                        create_table_from_df(df, new_table, conn)
                        df.to_sql(new_table, conn, if_exists='append', index=False)
                        print(f"✅ Table '{new_table}' created and loaded.")
                    else:
                        print("⏭️ Skipped loading.")
                else:
                    create_table_from_df(df, table_name, conn)
                    df.to_sql(table_name, conn, if_exists='append', index=False)
                    print(f"✅ Table '{table_name}' created and loaded.")

            elif choice == '2':
                sql = input("💬 Enter SQL query: ")
                result = pd.read_sql(sql, conn)
                print(result)

            elif choice == '3':
                schema_description = format_schema_for_llm(cursor)
                print("💡 Ask your question (e.g., 'Top 5 products this month'):")
                user_prompt = input("🧠> ")

                print("🤖 Generating SQL via LLM...")
                try:
                    llm_output = generate_sql_with_llm(schema_description, user_prompt)
                    print("\n🧾 LLM Output:")
                    print(llm_output)

                    # Extract and execute SQL from response (basic version)
                    sql_lines = [line for line in llm_output.splitlines() if line.strip() and not line.strip().startswith("-")]
                    sql_code = []
                    in_sql = False
                    for line in sql_lines:
                        if line.lower().startswith("select") or in_sql:
                            sql_code.append(line)
                            in_sql = True
                            if ";" in line:
                                break
                    final_sql = "\n".join(sql_code)
                    print("\n📊 Executing SQL:")
                    print(final_sql)
                    result = pd.read_sql(final_sql, conn)
                    print(result)

                except Exception as e:
                    error_msg = traceback.format_exc()
                    log_error(error_msg)
                    print("❌ Failed to generate or execute SQL.")

            elif choice == '4':
                tables = list_tables(conn)
                print("📋 Tables in database:")
                for t in tables:
                    print(" -", t)

            elif choice == '5':
                print("👋 Exiting. Goodbye!")
                break

            else:
                print("❓ Invalid choice.")

        except Exception as e:
            error_msg = traceback.format_exc()
            log_error(error_msg)
            print("❌ An error occurred. Check error_log.txt for details.")

    conn.close()

if __name__ == '__main__':
    interactive_sqlite_bot()