@echo off
chcp 65001 >nul
title Rotina Achadoteca
cd /d "%~dp0"

rem 1) Edge da automacao (porta 9222): abre se ainda nao estiver aberto
netstat -ano | findstr ":9222" | findstr "LISTENING" >nul
if errorlevel 1 (
  echo Abrindo o Edge da automacao...
  start "" "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe" --remote-debugging-port=9222 --user-data-dir="%USERPROFILE%\achadoteca-edge" https://www.mercadolivre.com.br/afiliados/hub
  echo.
  echo Na janela do Edge: confira se voce esta logado na Central de afiliados.
  echo Se pedir login ou verificacao, faca voce mesmo.
  echo Quando aparecer o campo "Busque produtos", volte aqui.
  pause
)

rem 2) Atualiza o projeto e roda a rotina
echo.
echo Atualizando o projeto...
git fetch origin
git reset --hard origin/main
echo.
echo Rodando a rotina (precos e reposicao). Nao feche o Edge da automacao.
python scripts\rotina_local.py
echo.
echo Fim. Pode fechar esta janela.
pause
