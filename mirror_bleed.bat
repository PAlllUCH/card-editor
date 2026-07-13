@echo off
setlocal enabledelayedexpansion

echo [BAT] Starting mirror_bleed processing...
if not exist "output" mkdir "output"

set "count=0"
for %%f in (*.png *.jpg *.jpeg *.webp *.bmp) do (
    echo [BAT] Processing: %%f
    magick "%%f" -virtual-pixel Mirror -set option:distort:viewport "%%[fx:w+48]x%%[fx:h+48]-24-24" -distort SRT 0 "output\%%~nxf"
    
    if !errorlevel! neq 0 (
        echo [BAT ERROR] ImageMagick failed on %%f >&2
        exit /b !errorlevel!
    )
    set /a count+=1
)

echo [BAT] Done! Processed !count! images.
exit /b 0