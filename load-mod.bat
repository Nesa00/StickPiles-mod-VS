@echo off
setlocal
cd /d "%~dp0"

for /f "usebackq delims=" %%A in (`powershell -NoProfile -Command "(Get-Content modinfo.json -Raw | ConvertFrom-Json).version"`) do set "VERSION=%%A"
for /f "usebackq delims=" %%A in (`powershell -NoProfile -Command "(Get-Content modinfo.json -Raw | ConvertFrom-Json).name"`) do set "NAME=%%A"

set "NAME=%NAME: =-%"
set "ZIPNAME=%NAME%-%VERSION%.zip"

if exist "%ZIPNAME%" del "%ZIPNAME%"
powershell -NoProfile -Command "Compress-Archive -Path 'modinfo.json','modicon.png','assets' -DestinationPath '%ZIPNAME%' -Force"

del /Q "%AppData%\VintagestoryData\Mods\%NAME%-*.zip" 2>nul
copy /Y "%ZIPNAME%" "%AppData%\VintagestoryData\Mods\"