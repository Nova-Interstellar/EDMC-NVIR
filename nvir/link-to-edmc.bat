@echo off
setlocal

echo.
echo  NVIR Uplink  -  link this checkout into EDMC
echo  ===========================================
echo.

rem This script lives in nvir\, so the plugin root is one level up: that is the
rem folder EDMC must see, not the package folder holding this file.
set "HERE=%~dp0"
if "%HERE:~-1%"=="\" set "HERE=%HERE:~0,-1%"
for %%I in ("%HERE%") do set "SOURCE=%%~dpI"
if "%SOURCE:~-1%"=="\" set "SOURCE=%SOURCE:~0,-1%"
for %%I in ("%SOURCE%") do set "NAME=%%~nxI"

if not exist "%SOURCE%\load.py" (
    echo  ERROR  load.py is not in the parent folder:
    echo         %SOURCE%
    echo         Keep this script in the plugin's nvir\ folder.
    goto :done
)

set "PLUGINS=%LOCALAPPDATA%\EDMarketConnector\plugins"
if not exist "%PLUGINS%\" (
    echo  ERROR  EDMC's plugin folder does not exist:
    echo         %PLUGINS%
    echo         Install EDMC and run it once, then try again.
    goto :done
)

set "LINK=%PLUGINS%\%NAME%"

if exist "%LINK%" (
    rem rmdir without /s removes a junction or an empty folder and nothing
    rem else - it will not follow a link or delete any file.
    rmdir "%LINK%" 2>nul
    if exist "%LINK%" (
        echo  ERROR  A real folder is already there:
        echo         %LINK%
        echo         Move or delete it, then run this again.
        goto :done
    )
    echo  Removed the previous link.
)

rem A junction needs no administrator rights, unlike a symbolic link.
mklink /J "%LINK%" "%SOURCE%" >nul
if errorlevel 1 (
    echo  ERROR  Could not create the junction at:
    echo         %LINK%
    goto :done
)

echo  Linked   %LINK%
echo        -^> %SOURCE%
echo.
echo  Restart EDMC to pick it up.
echo.
echo  To unlink later, delete the folder above from EDMC's plugin directory.
echo  It is a link, so deleting it leaves this checkout untouched.

:done
echo.
pause
endlocal
