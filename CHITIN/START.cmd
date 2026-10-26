@echo off
setlocal
chcp 65001 >nul
set "CHITIN_PY="
set "CHITIN_PY_ARGS="
if exist "%~dp0python\python.exe" (
  "%~dp0python\python.exe" -c "import sys,tkinter; assert sys.version_info >= (3,10)" >nul 2>&1
  if not errorlevel 1 (
    set "CHITIN_PY=%~dp0python\python.exe"
    goto launch
  )
)
py -3 -c "import sys,tkinter; assert sys.version_info >= (3,10)" >nul 2>&1
if not errorlevel 1 (
  set "CHITIN_PY=py"
  set "CHITIN_PY_ARGS=-3"
  goto launch
)
python -c "import sys,tkinter; assert sys.version_info >= (3,10)" >nul 2>&1
if not errorlevel 1 (
  set "CHITIN_PY=python"
  goto launch
)
echo Python 3.10+ with Tkinter was not found.
echo Use the same Python installation as the other Algorithmic Arts files.
echo Nothing was installed or changed. See README_BG.txt.
pause
exit /b 1
:launch
"%CHITIN_PY%" %CHITIN_PY_ARGS% "%~dp0battle_evolution.py" --max-agents 60
if errorlevel 1 (
  echo CHITIN stopped with an error. The message above is the diagnostic.
  pause
  exit /b 1
)
endlocal
