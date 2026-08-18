@echo off
echo ========================================
echo  Building win_toolkit.exe with Docker
echo ========================================

docker build -t win_toolkit-builder .

echo.
echo Copying .exe from container...

for /f %%i in ('docker create win_toolkit-builder') do set CID=%%i
docker cp %CID%:C:\src\dist\win_toolkit.exe dist\win_toolkit.exe
docker rm %CID%

echo.
echo ========================================
echo  Build complete! Check dist\win_toolkit.exe
echo ========================================
pause
