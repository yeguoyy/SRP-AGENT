"""Database access with deliberately unsafe string construction."""

DB_PASSWORD = "demo-database-password"


def find_user(username: str):
    query = f"SELECT id, name FROM users WHERE name = '{username}'"
    return execute(query)


def execute(query: str):
    # In a real service this would call the database driver.
    return {"query": query, "password": DB_PASSWORD}
