import os
import shutil
import tempfile
from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
import uuid
import cv_interface 

app = FastAPI(title="Lenta Tech Price Tag Recognition Backend")


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Директория для временного хранения загруженных видео
TEMP_VIDEO_DIR = tempfile.gettempdir()

@app.post("/upload/")
async def upload_video(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    task_id = str(uuid.uuid4())
    video_path = os.path.join(TEMP_VIDEO_DIR, f"{task_id}_{file.filename}")
    with open(video_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    background_tasks.add_task(process_video_task, task_id, video_path)
    
    return {"task_id": task_id, "status": "processing"}

def process_video_task(task_id: str, video_path: str):
    """Фоновая обработка видео вызовом CV-модели."""
    try:
        csv_path = cv_interface.process_video(video_path)
        with open(os.path.join(TEMP_VIDEO_DIR, f"{task_id}_result.txt"), "w") as f:
            f.write(csv_path)
    except Exception as e:
        with open(os.path.join(TEMP_VIDEO_DIR, f"{task_id}_error.txt"), "w") as f:
            f.write(str(e))
    finally:
        os.remove(video_path)
        pass

@app.get("/result/{task_id}")
async def get_result(task_id: str):
    """Проверяет статус задачи и возвращает CSV, если готов."""
    result_file = os.path.join(TEMP_VIDEO_DIR, f"{task_id}_result.txt")
    error_file = os.path.join(TEMP_VIDEO_DIR, f"{task_id}_error.txt")
    
    if os.path.exists(error_file):
        with open(error_file, "r") as f:
            error_msg = f.read()
        raise HTTPException(status_code=500, detail=f"Ошибка обработки: {error_msg}")
    
    if not os.path.exists(result_file):
        return {"status": "pending"}
    
    with open(result_file, "r") as f:
        csv_path = f.read().strip()
    
    if not os.path.exists(csv_path):
        raise HTTPException(status_code=404, detail="CSV файл не найден")
    
    return FileResponse(csv_path, media_type="text/csv", filename="result.csv")

@app.get("/health")
async def health():
    return {"status": "ok"}