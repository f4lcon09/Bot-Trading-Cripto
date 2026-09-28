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

REM ====================================================================
REM DESTINO DO BACKUP - definido AQUI, nao no ambiente do usuario.
REM
REM A tarefa do Agendador nao herda variaveis do shell interativo. Sem
REM esta linha a copia diaria do poller falharia todo dia - ruidosamente,
REM o que e melhor que em silencio, mas ainda sem copiar nada.
REM
REM Fica no .bat em vez de `setx` porque e configuracao DESTE projeto
REM nesta maquina, e o .bat e o unico lugar que o Agendador executa.
REM Mover para o ambiente do usuario tornaria invisivel de onde vem.
REM
REM G: e a letra do cliente do Google Drive em modo streaming. A escolha
REM e deliberada: se o cliente estiver fechado, deslogado ou travado, a
REM letra SOME e o backup quebra na hora. Uma pasta sincronizada dentro
REM de C: continuaria existindo como pasta comum, a copia "funcionaria",
REM o status diria ok, e nada replicaria. O destino que quebra alto e o
REM que satisfaz a invariante 11 por construcao.
REM ====================================================================
REM NAO define SNIPER_BACKUP_DIR aqui. O destino mora em
REM destino_backup.txt, lido tanto pelo poller quanto pela execucao
REM manual. Definir nos dois lugares foi o defeito de 28/09/2026:
REM o poller enxergava e um shell limpo nao, entao o procedimento
REM documentado no README falhava para qualquer um que o seguisse.

"C:\Users\User\AppData\Local\Programs\Python\Python314\python.exe" -u "C:\SniperV2\coletor_contexto.py"

exit /b %ERRORLEVEL%
