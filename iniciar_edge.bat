@echo off
rem Abre o Edge com um perfil proprio do Achadoteca e a porta 9222 para a rotina automatica.
rem Na primeira vez, entre voce mesmo no Mercado Livre (afiliados) nesse perfil. A rotina nunca digita senha.
start "" "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe" --remote-debugging-port=9222 --user-data-dir="%USERPROFILE%\achadoteca-edge" https://www.mercadolivre.com.br/afiliados/hub
