@echo off
REM ====================================================================
REM INICIAR_POLLER.BAT - wrapper para o Agendador de Tarefas
REM
REM cd /d garante o diretorio de trabalho: sem ele os caminhos
REM relativos do config.py resolvem contra C:\Windows\System32.
REM
REM NAO redireciona a saida para arquivo, e isso e deliberado.
REM
REM A versao anterior fazia `>> poller.log`. O primeiro processo
REM mantinha o log aberto pela vida inteira, e qualquer lancamento
REM seguinte falhava NO PROPRIO REDIRECIONAMENTO — antes de chegar ao
REM python, antes da trava de instancia unica, com o .bat saindo em
REM erro e disparando RestartOnFailure em loop.
REM
REM Pior: o sintoma era invisivel. A trava parecia estar funcionando
REM porque so havia um python vivo, quando na verdade os outros
REM lancamentos morriam antes de existir. So apareceu ao contar as
REM linhas do log e encontrar uma "subida" onde deveria haver quatro.
REM
REM Agora o proprio coletor escreve no log, abrindo e fechando a cada
REM linha, igual a todo anexar() de CSV do projeto.
REM ====================================================================

cd /d C:\SniperV2
if errorlevel 1 exit /b 1

"C:\Users\User\AppData\Local\Programs\Python\Python314\python.exe" -u "C:\SniperV2\coletor_contexto.py"

exit /b %ERRORLEVEL%
