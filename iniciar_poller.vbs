' ====================================================================
' INICIAR_POLLER.VBS - lancador silencioso para o Agendador de Tarefas
'
' Existe porque <Hidden>true</Hidden> no XML da tarefa esconde a JANELA
' DA TAREFA, nao o console que o cmd.exe cria ao rodar o .bat. Na
' pratica um terminal preto pisca, ou fica aberto, a cada disparo do
' gatilho de 10 minutos.
'
' WScript.Shell.Run com intWindowStyle = 0 nao cria console nenhum.
'
' Os tres argumentos:
'   comando            o .bat, com o caminho entre aspas duplicadas
'   0                  janela oculta, sem console
'   False              nao espera o termino
'
' O False tem uma consequencia que precisa estar registrada: o wscript
' retorna na hora, a tarefa do Agendador TERMINA com sucesso, e o
' python fica orfao dela. Isso desliga o MultipleInstancesPolicy, que
' observa a tarefa e nao o processo.
'
' A protecao contra instancia dupla NAO esta aqui — esta no proprio
' coletor_contexto.py, que trava um arquivo com msvcrt e sai em
' silencio se ja houver outro de pe. O sistema operacional solta a
' trava quando o processo morre, de qualquer jeito que morra.
'
' Sem essa trava, o gatilho de 10 minutos empilharia um poller novo a
' cada disparo, todos escrevendo no mesmo CSV, e o resultado seria
' timestamp duplicado por simbolo — o criterio exato que o validador
' usa para rebaixar uma serie.
' ====================================================================

Option Explicit

Dim sh, comando
Set sh = CreateObject("WScript.Shell")

comando = """C:\SniperV2\iniciar_poller.bat"""

sh.Run comando, 0, False

Set sh = Nothing
