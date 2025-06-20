@echo off
chcp 65001 >nul
title 🚀 EMPETRISHKA MP3 Downloader
color 0C

REM === Удаление битого окружения ===
if not exist venv\Scripts\activate.bat (
  echo [!] Ошибочное окружение — пересоздаю...
  rmdir /s /q venv
)

REM === Создание виртуального окружения ===
if not exist venv (
  echo [●] Создаю виртуальное окружение...
  python -m venv venv
)

REM === Проверка повторно ===
if not exist venv\Scripts\activate.bat (
  echo [X] Ошибка: файл активации не найден. Прервано.
  pause
  exit /b
)

REM === Активация окружения ===
call venv\Scripts\activate.bat

REM === Установка зависимостей ===
echo [●] Установка зависимостей...
venv\Scripts\pip.exe install --upgrade pip
venv\Scripts\pip.exe install -r requirements.txt

REM === Запуск Flask напрямую через Python ===
echo [✔] Сервер запущен на http://%COMPUTERNAME%:5000 (или по IP)
python app.py

pause
