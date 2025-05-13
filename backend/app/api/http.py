from fastapi import APIRouter
from fastapi.responses import FileResponse

router = APIRouter()

@router.get("/")
async def read_root():
    return FileResponse("static/index.html")

@router.get("/about")
async def about_page():
    return FileResponse("static/about.html")