@echo off
setlocal
cd /d "%~dp0.."
:menu
echo.
echo CrowdPulse host
echo 1. Start hosting and show the link
echo 2. Stop hosting (responses are kept)
echo 3. Exit
choice /c 123 /n /m "Choose 1, 2 or 3: "
if errorlevel 3 goto done
if errorlevel 2 goto stop
:start
docker compose up --build -d
if errorlevel 1 goto failed
echo Local link: http://localhost:3000/host
powershell -NoProfile -Command "$until=(Get-Date).AddSeconds(45); do {$log=docker compose logs --tail 30 tunnel 2>$null; $m=[regex]::Match(($log -join ' '),'https://[a-z0-9-]+\.trycloudflare\.com'); if($m.Success){Write-Host ('Public link: ' + $m.Value); exit 0}; Start-Sleep 2} while((Get-Date) -lt $until); exit 1"
if errorlevel 1 echo Tunnel link not ready yet. Choose Start again to check.
goto menu
:stop
docker compose down
if errorlevel 1 goto failed
echo Hosting stopped. Saved responses are kept.
goto menu
:failed
echo CrowdPulse could not complete that action. Check Docker Desktop and try again.
goto menu
:done
endlocal
