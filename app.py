import os
import shutil
import tempfile
from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import uuid
import cv_interface
import pandas as pd   # добавим, чтобы читать статистику из CSV

app = FastAPI(title="Lenta Tech Price Tag Recognition Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

TEMP_VIDEO_DIR = tempfile.gettempdir()

# Хранилище информации о задачах (в памяти, для демо)
tasks = {}  # task_id -> {"csv_path": ..., "status": ..., "progress": ..., "stage": ...}

@app.post("/upload")
async def upload_video(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    task_id = str(uuid.uuid4())
    video_path = os.path.join(TEMP_VIDEO_DIR, f"{task_id}_{file.filename}")
    with open(video_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    # Инициализируем задачу
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
        
        # Прочитаем статистику из CSV (первые строки и количество)
        df = pd.read_csv(csv_path)
        stats = {
            "detected_count": len(df),
            "rows_count": len(df),
            "barcode_count": df['barcode'].astype(str).str.len().gt(0).sum(),
            "qr_count": df['qr_code_barcode'].astype(str).str.len().gt(0).sum()
        }
        tasks[task_id]["stats"] = stats
        # Сохраним preview (первые 5 строк)
        tasks[task_id]["rows_preview"] = df.head(5).to_dict(orient="records")
        
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