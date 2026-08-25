@echo off
setlocal
cd /d "C:\Users\pepab\Documents\Bloomberg\bloomberg-data-fabric"
"C:\Users\pepab\Documents\Bloomberg\bloomberg-data-fabric\.venv\Scripts\python.exe" -u scripts\run_backfill_loop.py >> ".run_logs\backfill_task.log" 2>> ".run_logs\backfill_task.err.log"
exit /b %errorlevel%
