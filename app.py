import os
import shutil
import tempfile
import csv
import uuid
from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import cv_interface

app = FastAPI(title="Lenta Tech Price Tag Recognition Backend")

# CORS: разрешаем всем (без credentials)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

TEMP_VIDEO_DIR = tempfile.gettempdir()
tasks = {}

def get_csv_info(csv_path: str):
    """Читает CSV и возвращает stats и preview-строки (без pandas)."""
    with open(csv_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    total = len(rows)
    barcode_count = sum(1 for r in rows if r.get('barcode', '').strip())
    qr_count = sum(1 for r in rows if r.get('qr_code_barcode', '').strip())
    stats = {
        'detected_count': total,
        'rows_count': total,
        'barcode_count': barcode_count,
        'qr_count': qr_count
    }
    preview = rows[:5]
    return stats, preview

@app.post("/upload")
async def upload_video(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    task_id = str(uuid.uuid4())
    video_path = os.path.join(TEMP_VIDEO_DIR, f"{task_id}_{file.filename}")
    with open(video_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    tasks[task_id] = {
        "status": "queued",
        "progress": 0,
        "stage": "Видео загружено, ожидает обработки",
        "csv_path": None
    }
    background_tasks.add_task(process_video_task, task_id, video_path)
    return {"task_id": task_id, "status": "queued"}

def process_video_task(task_id: str, video_path: str):
    try:
        tasks[task_id]["status"] = "processing"
        tasks[task_id]["progress"] = 30
        tasks[task_id]["stage"] = "Распознавание ценников..."
        csv_path = cv_interface.process_video(video_path)
        tasks[task_id]["csv_path"] = csv_path
        tasks[task_id]["status"] = "done"
        tasks[task_id]["progress"] = 100
        tasks[task_id]["stage"] = "Готово"
        stats, preview = get_csv_info(csv_path)
        tasks[task_id]["stats"] = stats
        tasks[task_id]["rows_preview"] = preview
    except Exception as e:
        tasks[task_id]["status"] = "error"
        tasks[task_id]["stage"] = f"Ошибка: {str(e)}"
        tasks[task_id]["progress"] = 0
    finally:
        if os.path.exists(video_path):
            os.remove(video_path)

@app.get("/result/{task_id}")
async def get_result(task_id: str):
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    info = tasks[task_id]
    response = {
        "task_id": task_id,
        "status": info["status"],
        "progress": info.get("progress", 0),
        "stage": info.get("stage", "")
    }
    if info["status"] == "done":
        response["csv_url"] = f"/result/{task_id}/csv"
        response["stats"] = info.get("stats", {})
        response["rows_preview"] = info.get("rows_preview", [])
    elif info["status"] == "error":
        response["error"] = info.get("stage", "Unknown error")
    return JSONResponse(content=response)

@app.get("/result/{task_id}/csv")
async def get_csv(task_id: str):
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    info = tasks[task_id]
    if info["status"] != "done" or not info.get("csv_path"):
        raise HTTPException(status_code=404, detail="CSV not ready")
    if not os.path.exists(info["csv_path"]):
        raise HTTPException(status_code=404, detail="CSV file missing")
    return FileResponse(info["csv_path"], media_type="text/csv", filename="result.csv")

@app.get("/health")
async def health():
    return {"status": "ok"}