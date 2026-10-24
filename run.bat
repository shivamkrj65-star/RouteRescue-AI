@echo off
title RouteRescue AI - Multi-Agent System
echo ========================================================
echo         Starting RouteRescue AI System Ecosystem
echo ========================================================
echo.

if exist .venv\Scripts\python.exe (
    .venv\Scripts\python.exe scripts\start_all.py
) else (
    python scripts\start_all.py
)

pause
