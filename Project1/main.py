# main.py
from fastapi import FastAPI, Request, HTTPException
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
import database

app = FastAPI(title="Bite Me Buddy Database Viewer")

# Setup templates
templates = Jinja2Templates(directory="templates")

# Home page
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

# List all tables
@app.get("/tables", response_class=HTMLResponse)
async def list_tables(request: Request):
    tables_data = database.get_all_tables()
    
    if not tables_data["success"]:
        raise HTTPException(status_code=500, detail=tables_data["error"])
    
    # Get additional info for each table
    tables_with_info = []
    for table_name in tables_data["tables"]:
        table_info = database.get_table_info(table_name)
        if table_info["success"]:
            tables_with_info.append({
                "name": table_name,
                "row_count": table_info["row_count"],
                "columns_count": len(table_info["columns_info"])
            })
        else:
            tables_with_info.append({
                "name": table_name,
                "row_count": "Error",
                "columns_count": "Error"
            })
    
    return templates.TemplateResponse(
        "tables.html", 
        {
            "request": request,
            "tables": tables_with_info
        }
    )

# View specific table data
@app.get("/table/{table_name}", response_class=HTMLResponse)
async def view_table(request: Request, table_name: str, limit: int = 100):
    table_data = database.get_table_data(table_name, limit)
    
    if not table_data["success"]:
        raise HTTPException(status_code=500, detail=table_data["error"])
    
    table_info = database.get_table_info(table_name)
    
    return templates.TemplateResponse(
        "table_detail.html",
        {
            "request": request,
            "table_name": table_name,
            "columns": table_data["columns"],
            "data": table_data["data"],
            "count": table_data["count"],
            "table_info": table_info if table_info["success"] else None
        }
    )

# API endpoints (optional, for raw data)
@app.get("/api/tables")
async def api_get_tables():
    return database.get_all_tables()

@app.get("/api/table/{table_name}")
async def api_get_table(table_name: str, limit: int = 100):
    return database.get_table_data(table_name, limit)

# Health check
@app.get("/health")
async def health_check():
    try:
        result = database.get_all_tables()
        return {
            "status": "healthy",
            "database": "connected" if result["success"] else "disconnected",
            "tables_count": len(result["tables"]) if result["success"] else 0
        }
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}
