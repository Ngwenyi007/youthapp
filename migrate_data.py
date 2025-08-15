import json
import logging
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from supabase import create_client
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('migration.log')
    ]
)
logger = logging.getLogger(__name__)

class DatabaseMigrator:
    def __init__(self):
        self._load_environment()
        self.supabase = self._init_supabase_client()
        
    def _load_environment(self):
        """Load environment variables securely"""
        env_path = Path(__file__).parent / '.env'
        load_dotenv(env_path)
        
        self.supabase_url = os.getenv('SUPABASE_URL')
        self.service_key = os.getenv('SUPABASE_SERVICE_KEY')
        
        if not all([self.supabase_url, self.service_key]):
            raise ValueError("Missing required environment variables")

    def _init_supabase_client(self):
        """Initialize Supabase client with error handling"""
        try:
            client = create_client(self.supabase_url, self.service_key)
            logger.info("Supabase client initialized successfully")
            return client
        except Exception as e:
            logger.error("Failed to initialize Supabase client")
            raise

    def ensure_tables_exist(self):
        """Create tables with proper schema if they don't exist"""
        schema_commands = [
            """
            CREATE TABLE IF NOT EXISTS users (
                code TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                email TEXT,
                rank TEXT,
                local_church TEXT,
                parish TEXT,
                denary TEXT,
                diocese TEXT,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW()
            )
            """,
            "ALTER TABLE users DISABLE ROW LEVEL SECURITY",
            """
            CREATE TABLE IF NOT EXISTS posts (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                author_code TEXT REFERENCES users(code),
                content TEXT NOT NULL,
                type TEXT DEFAULT 'general',
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW(),
                pinned BOOLEAN DEFAULT false,
                target_level TEXT,
                local_church TEXT,
                parish TEXT,
                denary TEXT,
                diocese TEXT
            )
            """,
            "ALTER TABLE posts DISABLE ROW LEVEL SECURITY",
            """
            CREATE TABLE IF NOT EXISTS comments (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                post_id UUID REFERENCES posts(id) ON DELETE CASCADE,
                author_code TEXT,
                content TEXT,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW()
            )
            """,
            "ALTER TABLE comments DISABLE ROW LEVEL SECURITY"
        ]

        for cmd in schema_commands:
            try:
                self.supabase.rpc('execute', {'query': cmd}).execute()
                logger.debug(f"Executed SQL: {cmd[:50]}...")
            except Exception as e:
                logger.error(f"Error executing command: {e}")
                raise

    def _sanitize_data(self, data: Dict) -> Dict:
        """Remove None values and empty strings from data"""
        return {k: v for k, v in data.items() if v not in [None, ""]}

    def _migrate_users(self, post: Dict) -> str:
        """Handle user migration and return author_code"""
        author_code = post.get('author_code') or f"user_{uuid.uuid4().hex[:8]}"
        
        user_data = self._sanitize_data({
            'code': author_code,
            'name': post.get('author'),
            'rank': post.get('rank'),
            'local_church': post.get('local_church'),
            'parish': post.get('parish'),
            'denary': post.get('denary'),
            'diocese': post.get('diocese')
        })

        try:
            self.supabase.table('users').upsert(user_data).execute()
            return author_code
        except Exception as e:
            logger.error(f"Failed to migrate user {author_code}: {e}")
            raise

    def _migrate_post(self, post: Dict, author_code: str) -> str:
        """Handle post migration and return post_id"""
        post_id = post.get('id') or str(uuid.uuid4())
        
        post_data = self._sanitize_data({
            'id': post_id,
            'author_code': author_code,
            'content': post.get('content'),
            'type': post.get('type', 'general'),
            'created_at': post.get('timestamp') or datetime.now().isoformat(),
            'pinned': post.get('pinned', False),
            'target_level': post.get('target_level'),
            'local_church': post.get('local_church'),
            'parish': post.get('parish'),
            'denary': post.get('denary'),
            'diocese': post.get('diocese')
        })

        try:
            self.supabase.table('posts').upsert(post_data).execute()
            return post_id
        except Exception as e:
            logger.error(f"Failed to migrate post {post_id}: {e}")
            raise

    def _migrate_comments(self, comments: List[Dict], post_id: str):
        """Handle comment migration"""
        for comment in comments:
            comment_author_code = f"commenter_{uuid.uuid4().hex[:8]}"
            
            if comment.get('author'):
                user_data = self._sanitize_data({
                    'code': comment_author_code,
                    'name': comment.get('author'),
                    'rank': comment.get('rank')
                })
                self.supabase.table('users').upsert(user_data).execute()

            comment_data = self._sanitize_data({
                'post_id': post_id,
                'author_code': comment_author_code,
                'content': comment.get('content'),
                'created_at': comment.get('timestamp') or datetime.now().isoformat()
            })
            
            try:
                self.supabase.table('comments').upsert(comment_data).execute()
            except Exception as e:
                logger.error(f"Failed to migrate comment: {e}")
                continue

    def migrate(self, json_file_path: str):
        """Main migration method"""
        try:
            # 1. Setup database schema
            self.ensure_tables_exist()
            
            # 2. Load and process data
            with open(json_file_path) as f:
                posts = json.load(f)
            
            logger.info(f"Starting migration of {len(posts)} posts")
            
            for i, post in enumerate(posts, 1):
                try:
                    # Process each post
                    author_code = self._migrate_users(post)
                    post_id = self._migrate_post(post, author_code)
                    self._migrate_comments(post.get('comments', []), post_id)
                    
                    # Log progress
                    if i % 10 == 0:
                        logger.info(f"Processed {i}/{len(posts)} posts")
                        
                except Exception as e:
                    logger.error(f"Skipping post due to error: {e}")
                    continue
            
            logger.info("Migration completed successfully")
            return True
            
        except Exception as e:
            logger.error(f"Migration failed: {e}")
            return False

if __name__ == '__main__':
    migrator = DatabaseMigrator()
    migrator.migrate('posts.json')
