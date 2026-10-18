@echo off
rem Roda a rotina do Achadoteca. Agende no Agendador de Tarefas do Windows (todo dia, ex.: 7h30).
cd /d "%~dp0"
python scripts\rotina_local.py >> rotina_local.out 2>&1
