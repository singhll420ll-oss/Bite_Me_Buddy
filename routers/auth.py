# In routers/auth.py - Add these functions

# Register page
@router.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    return templates.TemplateResponse(
        "register.html",
        {"request": request, "title": "Register - Bite Me Buddy"}
    )

# Login page
@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse(
        "login.html",
        {"request": request, "title": "Login - Bite Me Buddy"}
    )

# Team login page
@router.get("/team-login", response_class=HTMLResponse)
async def team_login_page(request: Request):
    return templates.TemplateResponse(
        "team_login.html",
        {"request": request, "title": "Team Member Login"}
    )

# Admin login page (from secret clock)
@router.get("/admin-login", response_class=HTMLResponse)
async def admin_login_page(request: Request):
    return templates.TemplateResponse(
        "admin_login.html",
        {"request": request, "title": "Admin Login"}
    )