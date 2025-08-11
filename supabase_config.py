
# supabase_config.py
import { createClient } from '@supabase/supabase-js'
from supabase import create_client, Client
import os

# --- Load from environment variables for security ---
SUPABASE_URL = os.getenv("SUPABASE_URL", 'https://egnsaojhqkxlnlcbllhq.supabase.co')
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "process.env.SUPABASE_KEY")  # Keep safe!

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- Example: Insert a record ---
def insert_post(title, content, author):
    try:
        response = supabase.table("posts").insert({
            "title": title,
            "content": content,
            "author": author
        }).execute()
        return response.data
    except Exception as e:
        print("Error inserting:", e)
        return None

# --- Example: Get all posts ---
def get_all_posts():
    try:
        response = supabase.table("posts").select("*").order("created_at", desc=True).execute()
        return response.data
    except Exception as e:
        print("Error fetching:", e)
        return []
