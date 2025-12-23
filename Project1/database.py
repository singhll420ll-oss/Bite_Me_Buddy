# database.py
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
import os
from dotenv import load_dotenv

load_dotenv()

# Your database URL
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://bite_me_buddy_user:6Mb7axQ89EkOQTQnqw6shT5CaO2lFY1Z@dpg-d536f8khg0os738kuhm0-a/bite_me_buddy")

# Create engine
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    """Database session dependency"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_all_tables():
    """Get all table names from database"""
    try:
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        return {"success": True, "tables": tables}
    except Exception as e:
        return {"success": False, "error": str(e)}

def get_table_data(table_name, limit=100):
    """Get data from specific table"""
    db = SessionLocal()
    try:
        # First, get column names
        columns_query = text(f"""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = :table_name 
            ORDER BY ordinal_position
        """)
        columns_result = db.execute(columns_query, {"table_name": table_name})
        columns = [row[0] for row in columns_result]
        
        # Then get data
        data_query = text(f"SELECT * FROM {table_name} LIMIT {limit}")
        data_result = db.execute(data_query)
        data = data_result.fetchall()
        
        # Convert to list of dictionaries
        data_list = []
        for row in data:
            row_dict = {}
            for i, col in enumerate(columns):
                row_dict[col] = row[i]
            data_list.append(row_dict)
        
        return {
            "success": True,
            "table_name": table_name,
            "columns": columns,
            "data": data_list,
            "count": len(data_list)
        }
    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        db.close()

def get_table_info(table_name):
    """Get detailed information about a table"""
    db = SessionLocal()
    try:
        # Get column details
        query = text("""
            SELECT 
                column_name,
                data_type,
                is_nullable,
                column_default
            FROM information_schema.columns
            WHERE table_name = :table_name
            ORDER BY ordinal_position
        """)
        
        result = db.execute(query, {"table_name": table_name})
        columns_info = result.fetchall()
        
        # Get row count
        count_query = text(f"SELECT COUNT(*) FROM {table_name}")
        count_result = db.execute(count_query)
        row_count = count_result.scalar()
        
        return {
            "success": True,
            "table_name": table_name,
            "columns_info": [
                {
                    "name": col[0],
                    "type": col[1],
                    "nullable": col[2],
                    "default": col[3]
                }
                for col in columns_info
            ],
            "row_count": row_count
        }
    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        db.close()
