# My-eBookStore Backend

Run in the planned conda environment:

```powershell
conda activate pytorch3.9
pip install -r backend/requirements.txt
copy backend\.env.sample backend\.env
python backend\scripts\check_sql_server.py
python backend\scripts\init_db.py
uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
```

The frontend uses `/api`; serve the static `frontend/` folder from the same
origin or proxy `/api` to this FastAPI app.
