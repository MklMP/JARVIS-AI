@echo off
title Jarvis - Asistente Personal Inteligente
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
python "%~dp0gui.py"
pause
