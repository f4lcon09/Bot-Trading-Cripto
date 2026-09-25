#!/usr/bin/env python3
"""
TESTE_DETECTORES.PY - Gate 1b.

  python teste_detectores.py

--------------------------------------------------------------------
O QUE ESTE ARQUIVO PROVA, E POR QUE ELE EXISTE
--------------------------------------------------------------------
Todo detector deste projeto compartilha a mesma assinatura de falha:
ele devolve EXATAMENTE o mesmo resultado quando esta funcionando e
quando esta cego.

  "sem lacuna"        e o que o detector diz quando nao ha lacuna, e
                      tambem quando ele nao consegue ler o arquivo
  "nenhum evento"     e o que o coletor diz num dia calmo, e tambem
                      num dia em que estava morto
  "nada a relatar"    e o que a validacao diz numa serie limpa, e
                      tambem numa serie que ela nao sabe checar

Em dois dias isso aconteceu quatro vezes:

  1. o poller morreu e perdeu 517 minutos sem escrever uma linha de
     falha — morte abrupta nao passa por finally
  2. o coletor de execucao, com dois eventos por dia, nao deixava
     marca nenhuma de estar vivo
  3. mudar o cabecalho de 12 para 14 colunas cegou o detector de
     lacuna para todos os arquivos anteriores
  4. o .bat com `>> log` fazia todo lancamento seguinte morrer ANTES
     da trava; o teste contou "1 processo vivo" e leu como sucesso,
     quando os outros nunca tinham nascido

Nos quatro casos o instrumento parecia bem.

Por isso este arquivo nao testa que os detectores ficam quietos.
Testa que cada um CONSEGUE DISPARAR: injeta o defeito sinteticamente
e exige o alarme. Um detector que nunca disparou em teste nenhum e
indistinguivel de um detector quebrado.
--------------------------------------------------------------------
"""
import csv
import os
import shutil
import sys
import tempfile

FALHAS = []


def checar(nome, condicao, detalhe=""):
    marca = "ok  " if condicao else "FALHA"
    print(f"  {marca} {nome}")
    if detalhe:
        print(f"       {detalhe}")
    if not condicao:
        FALHAS.append(nome)
    return condicao


def esperar_excecao(nome, fn, tipo=Exception):
    try:
        fn()
    except tipo as e:
        return checar(nome, True, f"-> {str(e)[:64]}...")
    return checar(nome, False, "nao levantou excecao")


# ====================================================================
def teste_duplicata():
    """O detector que faltava em 23/09: (ts, symbol) repetido."""
    print("\n1. DUPLICATA NA SERIE  (invariante 11, direcao inversa)")
    from invariante10 import SerieDuplicada, exigir_serie_integra

    limpa = [("t1", "BTC"), ("t1", "ETH"), ("t2", "BTC"), ("t2", "ETH")]
    n = exigir_serie_integra(limpa, "serie limpa")
    checar("serie limpa passa", n == 4)

    suja = limpa + [("t1", "BTC")]   # o caso real: duas leituras do mesmo minuto
    esperar_excecao("duplicata sintetica DISPARA",
                    lambda: exigir_serie_integra(suja, "serie suja"),
                    SerieDuplicada)


def teste_validador_contexto():
    """O validador inteiro, com um CSV sintetico contaminado."""
    print("\n2. VALIDADOR DE CONTEXTO")
    import config
    import validacao_contexto as vc

    d = tempfile.mkdtemp(prefix="gate1b_")
    original = config.DIR_EXECUCAO
    vc.DIR_EXECUCAO = d
    try:
        cab = vc.CABECALHO_14
        def linha(ts, sym, oi="100"):
            return [ts, sym, oi, "0.00001", "1.0", "1.0", "1.0",
                    "0.0001", "1.0", "1.0", "5000", "1.0", "0", "10"]

        # --- caso limpo ---
        p = os.path.join(d, "contexto_2026-01-01.csv")
        with open(p, "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f, lineterminator="\n")
            w.writerow(cab)
            for m in range(3):
                for s in config.MAJORS:
                    w.writerow(linha(f"2026-01-01T00:0{m}:00+00:00", s))
        r = vc.validar(p)
        checar("CSV limpo e APROVADO", r["aprovado"],
               f"{r['n_linhas']} linhas, {r['minutos']} minutos")

        # --- duplicata injetada ---
        with open(p, "a", encoding="utf-8", newline="") as f:
            csv.writer(f, lineterminator="\n").writerow(
                linha("2026-01-01T00:01:00+00:00", "BTC", "999"))
        r = vc.validar(p)
        checar("duplicata injetada REPROVA", not r["aprovado"],
               r["motivos"][0][:70] + "..." if r["motivos"] else "")

        # --- minuto com simbolo faltando ---
        p2 = os.path.join(d, "contexto_2026-01-02.csv")
        with open(p2, "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f, lineterminator="\n")
            w.writerow(cab)
            for s in config.MAJORS:
                w.writerow(linha("2026-01-02T00:00:00+00:00", s))
            for s in config.MAJORS[:-3]:      # tres a menos
                w.writerow(linha("2026-01-02T00:01:00+00:00", s))
        r = vc.validar(p2)
        checar("minuto incompleto REPROVA", not r["aprovado"],
               r["motivos"][0][:70] + "..." if r["motivos"] else "")

        # --- buraco NAO declarado ---
        p3 = os.path.join(d, "contexto_2026-01-03.csv")
        with open(p3, "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f, lineterminator="\n")
            w.writerow(cab)
            for m in ("00", "05"):            # pula 01 a 04
                for s in config.MAJORS:
                    w.writerow(linha(f"2026-01-03T00:{m}:00+00:00", s))
        r = vc.validar(p3)
        checar("buraco NAO declarado REPROVA", not r["aprovado"],
               f"{r.get('buracos_nao_declarados')} minutos sem linha de falha")

        # --- mesmo buraco, agora DECLARADO ---
        with open(os.path.join(d, "contexto_falhas_2026-01-03.csv"), "w",
                  encoding="utf-8", newline="") as f:
            w = csv.writer(f, lineterminator="\n")
            w.writerow(["ts_inicio", "ts_fim", "minutos_perdidos", "motivo"])
            w.writerow(["2026-01-03T00:01:00+00:00",
                        "2026-01-03T00:04:00+00:00", 4, "teste"])
        r = vc.validar(p3)
        checar("mesmo buraco, DECLARADO, e APROVADO", r["aprovado"],
               "buraco honesto nao e defeito")
    finally:
        vc.DIR_EXECUCAO = original
        shutil.rmtree(d, ignore_errors=True)


def teste_lacuna_contexto():
    """O detector que ficou cego ao mudar o esquema."""
    print("\n3. DETECTOR DE LACUNA DO POLLER")
    import coletor_contexto as cc

    d = tempfile.mkdtemp(prefix="gate1b_")
    original = cc.DIR_EXECUCAO
    cc.DIR_EXECUCAO = d
    try:
        antigo = cc.agora_ms() - 3 * 3600 * 1000     # 3 horas atras
        p = os.path.join(d, "contexto_2026-01-01.csv")
        with open(p, "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f, lineterminator="\n")
            w.writerow(cc.COLUNAS)
            w.writerow([cc.iso(antigo), "BTC"] + [""] * 12)
        u = cc.ultimo_registrado_ms()
        checar("le o ultimo registro em disco", u is not None and abs(u - antigo) < 60000)

        # esquema ANTIGO de 12 colunas: o caso que o cegou
        p12 = os.path.join(d, "contexto_2026-01-02.csv")
        with open(p12, "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f, lineterminator="\n")
            w.writerow(cc.COLUNAS[:12])
            w.writerow([cc.iso(antigo + 60000), "BTC"] + [""] * 10)
        u2 = cc.ultimo_registrado_ms()
        checar("le TAMBEM o esquema anterior de 12 colunas",
               u2 is not None and u2 > u,
               "exigir cabecalho identico cegaria o detector a cada mudanca")

        # o alarme em si
        col = cc.Coletor.__new__(cc.Coletor)
        col.ultimo_ok_ms = None
        col.falha_desde = None
        col._registrar_lacuna_de_subida()
        falhas = [f for f in os.listdir(d) if f.startswith("contexto_falhas_")]
        checar("lacuna de 3h DISPARA e grava linha", bool(falhas),
               falhas[0] if falhas else "nenhum arquivo de falhas gerado")
    finally:
        cc.DIR_EXECUCAO = original
        shutil.rmtree(d, ignore_errors=True)


def teste_pulso_execucao():
    """Sem pulso, uma semana morto e igual a uma semana sem gatilho."""
    print("\n4. PULSO DO COLETOR DE EXECUCAO")
    import coletor_execucao as ce

    d = tempfile.mkdtemp(prefix="gate1b_")
    original = ce.DIR_EXECUCAO
    ce.DIR_EXECUCAO = d
    try:
        col = ce.Coletor.__new__(ce.Coletor)
        col.caminho_pulso = os.path.join(d, "pulso.txt")

        col._registrar_lacuna_de_subida()          # sem pulso anterior
        checar("primeira subida NAO inventa lacuna",
               not [f for f in os.listdir(d) if f.startswith("desconexoes_")])

        with open(col.caminho_pulso, "w") as f:    # pulso de 40 min atras
            f.write(str(ce.agora_ms() - 40 * 60000))
        col._registrar_lacuna_de_subida()
        desc = [f for f in os.listdir(d) if f.startswith("desconexoes_")]
        checar("pulso velho DISPARA", bool(desc))

        antes = len(open(os.path.join(d, desc[0]), encoding="utf-8").readlines())
        with open(col.caminho_pulso, "w") as f:    # pulso de 10 s atras
            f.write(str(ce.agora_ms() - 10000))
        col._registrar_lacuna_de_subida()
        depois = len(open(os.path.join(d, desc[0]), encoding="utf-8").readlines())
        checar("reinicio imediato NAO gera linha falsa", antes == depois)
    finally:
        ce.DIR_EXECUCAO = original
        shutil.rmtree(d, ignore_errors=True)


def teste_mercado_invalido():
    """Ausencia de mercado nunca e medicao de zero."""
    print("\n5. MERCADO INVALIDO  (invariante 11)")
    from coletor_contexto import mercado_invalido

    vivo = {"openInterest": "100", "midPx": "1.5", "dayNtlVlm": "5000"}
    checar("mercado vivo passa", not mercado_invalido(vivo, {"isDelisted": False})[0])

    inval, motivo = mercado_invalido(vivo, {"isDelisted": True})
    checar("isDelisted e SOBERANO mesmo com OI valido",
           inval and motivo == "isDelisted",
           "criterio declarado vence os inferidos")

    ton = {"openInterest": "0.0", "midPx": None, "dayNtlVlm": "0.0"}
    checar("o caso TON real DISPARA", mercado_invalido(ton, {"isDelisted": True})[0])

    for campo, ctx in [("OI zero", {"openInterest": "0", "midPx": "1", "dayNtlVlm": "1"}),
                       ("mid vazio", {"openInterest": "1", "midPx": None, "dayNtlVlm": "1"}),
                       ("volume zero", {"openInterest": "1", "midPx": "1", "dayNtlVlm": "0"})]:
        checar(f"segunda linha: {campo} DISPARA sem a flag",
               mercado_invalido(ctx, {"isDelisted": False})[0])


def teste_invariante10():
    """Os guardas estatisticos."""
    print("\n6. INVARIANTE 10")
    import invariante10 as i10

    esperar_excecao("Medida sem unidade de agrupamento",
                    lambda: i10.Medida([0.1, 0.2], ""), i10.ViolacaoInvariante10)
    esperar_excecao("reportar alpha de lista crua",
                    lambda: i10.exigir_medida([0.1, 0.2]), i10.ViolacaoInvariante10)
    esperar_excecao("julgar gate sem familia selada",
                    lambda: i10.exigir_familia(None), i10.ViolacaoInvariante10)

    fam = i10.FamiliaDeBusca("t").declarar("a", "b").fechar()
    esperar_excecao("acrescentar celula a familia selada (fusao pos-hoc)",
                    lambda: fam.declarar("c"), i10.ViolacaoInvariante10)
    esperar_excecao("amplitude com uma estrategia so",
                    lambda: i10.amplitude_de_controle(
                        [i10.Medida([0.1, 0.2, 0.3], "dia")]),
                    i10.ViolacaoInvariante10)

    # dois controles que discordam SOBRE SIGNIFICANCIA: um nulo, outro
    # forte. E o caso de 22/09 — casado por sigma dava t ~ 0,2 e
    # pareado por dia dava t ~ 2,7 sobre os mesmos eventos.
    nulo = [0.02, -0.02] * 20                  # media 0, t ~ 0
    forte = [0.05] * 20 + [0.06] * 20          # media +5,5%, t enorme
    ms = [i10.Medida(nulo, "dia", 200, "casado por sigma"),
          i10.Medida(forte, "dia", 200, "pareado por dia")]
    texto, alerta = i10.amplitude_de_controle(ms)
    checar("controles discordantes DISPARAM alerta", alerta,
           [l.strip() for l in texto.split(chr(10)) if "ATRAVESSA" in l][:1])

    # e o caso estavel NAO deve disparar
    ms_ok = [i10.Medida([0.05] * 20 + [0.06] * 20, "dia", 200, "A"),
             i10.Medida([0.05] * 20 + [0.055] * 20, "dia", 200, "B")]
    _, alerta_ok = i10.amplitude_de_controle(ms_ok)
    checar("controles concordantes NAO disparam", not alerta_ok)


def teste_sobreposicao_falhas():
    """Janela de falha contada duas vezes."""
    print(chr(10) + "7. SOBREPOSICAO NO ARQUIVO DE FALHAS")
    import config
    import validacao_contexto as vc

    d = tempfile.mkdtemp(prefix="gate1b_")
    original = vc.DIR_EXECUCAO
    vc.DIR_EXECUCAO = d
    try:
        cab = vc.CABECALHO_14
        def linha(ts, sym):
            return [ts, sym, "100", "0.00001", "1.0", "1.0", "1.0",
                    "0.0001", "1.0", "1.0", "5000", "1.0", "0", "10"]
        p = os.path.join(d, "contexto_2026-02-01.csv")
        with open(p, "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f, lineterminator=chr(10))
            w.writerow(cab)
            for m in ("00", "05"):
                for s in config.MAJORS:
                    w.writerow(linha(f"2026-02-01T00:{m}:00+00:00", s))

        # duas janelas que cobrem o MESMO minuto — o caso de 24/09
        fal = os.path.join(d, "contexto_falhas_2026-02-01.csv")
        with open(fal, "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f, lineterminator=chr(10))
            w.writerow(["ts_inicio", "ts_fim", "minutos_perdidos", "motivo"])
            w.writerow(["2026-02-01T00:01:00+00:00",
                        "2026-02-01T00:04:00+00:00", 4, "minutos pulados"])
            w.writerow(["2026-02-01T00:04:00+00:00",
                        "2026-02-01T00:04:00+00:00", 1, "recuperado"])
        r = vc.validar(p)
        checar("janelas sobrepostas DISPARAM", not r["aprovado"],
               r["motivos"][0][:72] + "..." if r["motivos"] else "")
        checar("declarado != distintos e reportado",
               r.get("falhas_declaradas") == 5 and r.get("falhas_distintas") == 4,
               f"declarado={r.get('falhas_declaradas')} "
               f"distintos={r.get('falhas_distintas')}")

        # mesma cobertura, sem sobreposicao, deve passar
        with open(fal, "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f, lineterminator=chr(10))
            w.writerow(["ts_inicio", "ts_fim", "minutos_perdidos", "motivo"])
            w.writerow(["2026-02-01T00:01:00+00:00",
                        "2026-02-01T00:04:00+00:00", 4, "minutos pulados"])
        r = vc.validar(p)
        checar("mesma cobertura sem sobreposicao PASSA", r["aprovado"])
    finally:
        vc.DIR_EXECUCAO = original
        shutil.rmtree(d, ignore_errors=True)


def impressao_do_diretorio(caminho):
    """(nome, tamanho, mtime) de tudo em dados_execucao."""
    fora = {}
    for raiz, _, arqs in os.walk(caminho):
        for a in arqs:
            p = os.path.join(raiz, a)
            try:
                st = os.stat(p)
                fora[p] = (st.st_size, st.st_mtime_ns)
            except OSError:
                pass
    return fora


def teste_agregacao_obrigatoria():
    """
    `medir()` recusa rodar sem a unidade de contagem declarada.

    Este bloco existe por causa de uma armadilha carregada: `medir()`
    tinha `agregacao` implicita em "evento", que e o certo para
    reaplicar a tese e o errado para tudo que for novo. Quem escrevesse
    o teste de OI importaria `medir()` porque ela existe e funciona, e
    herdaria por omissao a contagem de eventos correlacionados como
    independentes - a primeira causa da morte da tese, reencarnada
    dentro do teste escrito para nao repeti-la.

    O Adendo 2 declara que o teste de OI agrega por dia. Declaracao em
    documento nao segura; o `raise` segura. Este bloco garante que o
    `raise` continua la depois de qualquer refatoracao.
    """
    print(chr(10) + "9. AGREGACAO OBRIGATORIA EM medir()")
    import inspect

    import analise

    try:
        analise.medir("bin_fut", ["BTC"], 0, 10 ** 14, "x")
        checar("medir() sem agregacao levanta excecao", False,
               "rodou com padrao - a armadilha voltou")
    except analise.AgregacaoNaoDeclarada:
        checar("medir() sem agregacao levanta excecao", True,
               "AgregacaoNaoDeclarada")
    except TypeError:
        checar("medir() sem agregacao levanta excecao", True,
               "TypeError de argumento faltando")

    try:
        analise.medir("bin_fut", ["BTC"], 0, 10 ** 14, "x", agregacao="mes")
        checar("medir() recusa agregacao desconhecida", False, "aceitou 'mes'")
    except analise.AgregacaoNaoDeclarada:
        checar("medir() recusa agregacao desconhecida", True)

    padrao = inspect.signature(analise.medir).parameters["agregacao"].default
    checar("o parametro nao tem padrao util", padrao is None,
           "default=%r" % (padrao,))

    fonte = inspect.getsource(analise.main)
    n = fonte.count('agregacao="evento"')
    checar("as chamadas de analise.py declaram 'evento' explicitamente",
           n >= 1, "%d chamada(s) explicita(s)" % n)


def main():
    print("GATE 1b - cada detector consegue disparar?")
    print("Nao basta ficar quieto: um detector que nunca disparou em teste")
    print("nenhum e indistinguivel de um detector quebrado.")

    # ISOLAMENTO: nada deste arquivo pode tocar em dados_execucao.
    # Em 23/09 o teste escreveu cinco lacunas fantasma no poller.log de
    # producao, porque CAMINHO_LOG era resolvido no import e nao
    # acompanhava o DIR_EXECUCAO remendado. O vazamento foi conferido
    # contando o CSV de falhas, que estava limpo — e declarado
    # inexistente. Duas saidas, uma verificada.
    from config import DIR_EXECUCAO
    antes = impressao_do_diretorio(DIR_EXECUCAO)

    for fn in (teste_agregacao_obrigatoria,
               teste_duplicata, teste_validador_contexto,
               teste_lacuna_contexto, teste_pulso_execucao,
               teste_mercado_invalido, teste_invariante10,
               teste_sobreposicao_falhas):
        try:
            fn()
        except Exception as e:
            import traceback
            print(f"  ERRO no bloco {fn.__name__}: {type(e).__name__}: {e}")
            traceback.print_exc()
            FALHAS.append(fn.__name__)

    print(chr(10) + "10. ISOLAMENTO DO PROPRIO TESTE")
    depois = impressao_do_diretorio(DIR_EXECUCAO)
    tocados = sorted(set(depois) - set(antes)) +               sorted(k for k in set(antes) & set(depois) if antes[k] != depois[k])
    checar("nenhum arquivo de producao foi tocado", not tocados,
           "; ".join(os.path.basename(t) for t in tocados[:4]) if tocados
           else "dados_execucao intacto")

    print()
    if FALHAS:
        print(f"GATE 1b REPROVADO - {len(FALHAS)} falha(s): {FALHAS}")
        return 1
    print("GATE 1b APROVADO - todos os detectores dispararam quando deviam")
    return 0


if __name__ == "__main__":
    sys.exit(main())
