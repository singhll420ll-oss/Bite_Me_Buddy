from flask import Flask, render_template
import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()  # .env फाइल से variables load करने के लिए

app = Flask(__name__)

# PostgreSQL connection function
def get_db_connection():
    # आपका database URL (सुरक्षित तरीके से)
    DATABASE_URL = "postgresql://bite_me_buddy_user:6Mb7axQ89EkOQTQnqw6shT5CaO2lFY1Z@dpg-d536f8khg0os738kuhm0-a/bite_me_buddy"
    
    conn = psycopg2.connect(DATABASE_URL)
    return conn

# Home route - सभी डेटा दिखाएगा
@app.route('/')
def show_all_data():
    conn = None
    cursor = None
    try:
        # Database से कनेक्ट करें
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # पहले यह देखें कि कौनसी tables हैं
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
            ORDER BY table_name;
        """)
        
        tables = cursor.fetchall()
        
        all_data = {}
        
        # हर table का डेटा fetch करें
        for table in tables:
            table_name = table[0]
            cursor.execute(f"SELECT * FROM {table_name} LIMIT 100;")  # सुरक्षा के लिए LIMIT
            columns = [desc[0] for desc in cursor.description]
            data = cursor.fetchall()
            
            all_data[table_name] = {
                'columns': columns,
                'data': data,
                'row_count': len(data)
            }
        
        cursor.close()
        conn.close()
        
        # HTML template render करें
        return render_template('data.html', tables=tables, all_data=all_data)
        
    except Exception as e:
        return f"Error: {str(e)}"

# Specific table का डेटा दिखाने के लिए
@app.route('/table/<table_name>')
def show_table(table_name):
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Table का सारा डेटा fetch करें
        cursor.execute(f"SELECT * FROM {table_name};")
        columns = [desc[0] for desc in cursor.description]
        data = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        return render_template('table_detail.html', 
                             table_name=table_name,
                             columns=columns,
                             data=data,
                             row_count=len(data))
        
    except Exception as e:
        return f"Error: {str(e)}"

if __name__ == '__main__':
    app.run(debug=True, port=5000)
