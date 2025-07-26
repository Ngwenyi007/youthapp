# models.py
# This is a placeholder example. Your actual User class and database interaction
# will depend on your chosen database (e.g., SQLite, PostgreSQL) and ORM (e.g., SQLAlchemy, Peewee).

# Example if using a simple dictionary for users (NOT recommended for production)
users_db = {
    "john_doe": {"username": "john_doe", "full_name": "John Doe", "rank": "member", "age": 30, "local_church": "St. Paul's", "parish": "Central Parish", "denary": "North Denary", "diocese": "Diocese A"},
    "jane_chairman": {"username": "jane_chairman", "full_name": "Jane Chairman", "rank": "chairman", "age": 45, "local_church": "St. Mary's", "parish": "South Parish", "denary": "South Denary", "diocese": "Diocese A"},
    # ... more users
}

class User:
    def __init__(self, data):
        self.username = data.get('username')
        self.full_name = data.get('full_name')
        self.rank = data.get('rank')
        self.age = data.get('age')
        self.local_church = data.get('local_church')
        self.parish = data.get('parish')
        self.denary = data.get('denary')
        self.diocese = data.get('diocese')
        # Add other attributes as needed

    # A static method or class method to retrieve user
    @staticmethod
    def get_user_by_username(username):
        user_data = users_db.get(username)
        if user_data:
            return User(user_data)
        return None

    @staticmethod
    def get_user_by_id(user_id): # If you use user IDs
        # This example assumes username is the ID. Adjust if your IDs are different.
        return User.get_user_by_username(user_id)
