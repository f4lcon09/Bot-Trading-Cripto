#!/usr/bin/env python3
"""
RELOGIO.PY - grava em UTC, reporta nos dois.

--------------------------------------------------------------------
POR QUE OS DOIS
--------------------------------------------------------------------
O ARQUIVO e UTC puro, com offset explicito. Isso e a invariante 9, e
nao se negocia:

  - o join com as velas da Binance quebra se o carimbo mudar de fuso
  - o horario de verao cria uma hora duplicada e outra inexistente por
    ano, e nenhuma das duas existe em UTC
  - o museu da Hyperliquid fica incomparavel com o resto

A CONVERSA e no fuso de quem le, com o UTC entre parenteses. Isso
nasceu em 23/09/2026: o relatorio disse "o poller morreu as 17:28" a
alguem cujo relogio marcava 23h. O numero nao batia com nada que a
pessoa tinha vivido, e a hipotese mais economica de quem le e que o
numero foi inventado.

Um relatorio que exige conversao mental antes de fazer sentido e um
relatorio que gera desconfianca — e desconfianca custa mais caro que
verbosidade.

A invariante 9 dizia de onde vem o relogio. Nao dizia como o numero
chega ate quem le. Este modulo e a segunda metade.
--------------------------------------------------------------------
"""
from datetime import datetime, timezone


def iso_utc(ms):
    """
    Carimbo para ARQUIVO. UTC, ISO 8601, com offset explicito.
    Nunca use isto em mensagem de terminal sem acompanhamento local.
    """
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).isoformat(
        timespec="seconds")


def dia_utc(ms):
    """Data UTC, para nome de arquivo. O dia do arquivo e o dia UTC."""
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).strftime(
        "%Y-%m-%d")


def humano(ms, com_data=True):
    """
    Carimbo para CONVERSA: local primeiro, UTC entre parenteses.

        22/09 23:15 (23/09 02:15 UTC)

    O local vem primeiro porque e o que a pessoa consegue conferir
    contra o proprio relogio sem fazer conta.
    """
    utc = datetime.fromtimestamp(ms / 1000, tz=timezone.utc)
    loc = utc.astimezone()
    fmt = "%d/%m %H:%M" if com_data else "%H:%M"
    return f"{loc.strftime(fmt)} ({utc.strftime(fmt)} UTC)"


def duracao(segundos):
    """Duracao legivel: 517 min vira '8h37'."""
    s = int(abs(segundos))
    h, m = divmod(s // 60, 60)
    if h:
        return f"{h}h{m:02d}"
    if m:
        return f"{m} min"
    return f"{s} s"


def offset_local():
    """String do fuso local, para o banner. Ex.: 'UTC-03:00'."""
    off = datetime.now().astimezone().utcoffset()
    if off is None:
        return "UTC"
    total = int(off.total_seconds())
    sinal = "+" if total >= 0 else "-"
    h, m = divmod(abs(total) // 60, 60)
    return f"UTC{sinal}{h:02d}:{m:02d}"


if __name__ == "__main__":
    import time
    agora = int(time.time() * 1000)
    print(f"fuso local detectado: {offset_local()}")
    print()
    print(f"  arquivo (iso_utc): {iso_utc(agora)}")
    print(f"  conversa (humano): {humano(agora)}")
    print()
    print("carimbos reais do projeto:")
    for rot, ms in [("1a subida do poller", 1790096940000),
                    ("morte com a sessao", 1790098080000),
                    ("volta, 14 colunas", 1790129700000)]:
        print(f"  {rot:<22} {humano(ms)}")
    print()
    for s in [0, 45, 600, 31020]:
        print(f"  duracao({s:>6}s) = {duracao(s)}")
