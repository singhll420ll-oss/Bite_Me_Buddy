# database.py - PURE psycopg2 VERSION (NO SQLAlchemy)
import psycopg2
from psycopg2.extras import RealDictCursor
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://bite_me_buddy_user:6Mb7axQ89EkOQTQnqw6shT5CaO2lFY1Z@dpg-d536f8khg0os738kuhm0-a/bite_me_buddy")

def get_db_connection():
    """Create database connection"""
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)

def get_all_tables():
    """Get all table names from database"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
            ORDER BY table_name
        """)
        
        tables = [row['table_name'] for row in cur.fetchall()]
        cur.close()
        conn.close()
        
        return {"success": True, "tables": tables}
    except Exception as e:
        return {"success": False, "error": str(e)}

def get_table_data(table_name, limit=100):
    """Get data from specific table"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Get column names
        cur.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = %s 
            ORDER BY ordinal_position
        """, (table_name,))
        
        columns = [row['column_name'] for row in cur.fetchall()]
        
        # Get data with limit
        cur.execute(f"SELECT * FROM {table_name} LIMIT %s", (limit,))
        data = cur.fetchall()
        
        cur.close()
        conn.close()
        
        return {
            "success": True,
            "table_name": table_name,
            "columns": columns,
            "data": data,
            "count": len(data)
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

def get_table_info(table_name):
    """Get detailed information about a table"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Get column details
        cur.execute("""
            SELECT 
                column_name,
                data_type,
                is_nullable,
                column_default
            FROM information_schema.columns
            WHERE table_name = %s
            ORDER BY ordinal_position
        """, (table_name,))
        
        columns_info = cur.fetchall()
        
        # Get row count
        cur.execute(f"SELECT COUNT(*) FROM {table_name}")
        row_count = cur.fetchone()['count']
        
        cur.close()
        conn.close()
        
        return {
            "success": True,
            "table_name": table_name,
            "columns_info": [
                {
                    "name": col['column_name'],
                    "type": col['data_type'],
                    "nullable": col['is_nullable'],
                    "default": col['column_default']
                }
                for col in columns_info
            ],
            "row_count": row_count
        }
    except Exception as e:
        return {"success": False, "error": str(e)}