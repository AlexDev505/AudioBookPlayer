@echo off
call deactivate
call ..\venv\scripts\python setup.py %1 %2 %3
call ..\venv32\scripts\python setup.py --mark-as-latest %1 %2 %3
call ..\venv\scripts\activate
FOR /F "tokens=*" %%i in ('type .env') do SET "%%i"
call python upload_update.py %1
call python setup.py %1 --dev
call tar -c -a -C ABPlayer.DEV -f "installers\ABPlayer.DEV.%1.zip" ABPlayer.DEV.exe _internal
