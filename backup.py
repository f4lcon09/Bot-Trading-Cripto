#!/usr/bin/env python3
"""
BACKUP.PY - copia dados_execucao para fora deste disco, e GRITA quando para.

  python backup.py                 # copia e atualiza o status
  python backup.py --verificar     # so confere o frescor da ultima copia
  python backup.py --autoteste     # prova que ele consegue reprovar

Destino pela variavel de ambiente SNIPER_BACKUP_DIR. Sem default no
fonte: um default apontando para dentro desta maquina seria um backup
que nao e backup, e pior, pareceria um.

  set SNIPER_BACKUP_DIR=C:\\Users\\User\\OneDrive\\SniperV2_backup

--------------------------------------------------------------------
POR QUE ESTE ARQUIVO E O ITEM MAIS CARO DA FILA
--------------------------------------------------------------------
`dados_execucao/` tem openInterest, funding e mark price minuto a
minuto. Ao contrario do museu, isto NAO e reproduzivel: a Binance
retem openInterestHist por 1 mes a 5 minutos, a Hyperliquid so expoe o
snapshot atual. Se o disco morrer, estes dados nao existem em lugar
nenhum do mundo - nem na Binance, nem na Hyperliquid, nem em backup de
terceiro.

O museu volta com dois comandos. Isto nao volta com nenhum.

--------------------------------------------------------------------
INVARIANTE 11: UM BACKUP QUE PARA EM SILENCIO E PIOR QUE NENHUM
--------------------------------------------------------------------
Nenhum backup: o risco fica visivel e incomoda.
Backup que parou: a sensacao de copia fica, o risco volta, e ninguem sabe.

E o mesmo defeito do arquivo de falhas que so gravava em saida limpa, e
do detector de lacuna que exigia cabecalho identico: o instrumento
devolve "nada a relatar", que e exatamente o que devolveria funcionando.

Por isso:
  - toda copia grava `backup_status.json` com carimbo, contagem e bytes
  - `verificar_frescor()` REPROVA se a ultima copia passou de 24 h
  - `validacao_contexto.py` chama essa verificacao, e o poller a registra
    no log na subida

O detector de silencio do backup e o porteiro que ja reprova dado sujo,
nao um segundo instrumento que tambem pode emudecer.

--------------------------------------------------------------------
NUNCA APAGA NO DESTINO
--------------------------------------------------------------------
A copia e ADITIVA. Arquivo que existe no destino e nao existe mais na
origem FICA. Espelho propaga exclusao, e numa serie que so cresce e nao
se recupera o destino nunca deve perder arquivo - nem quando a origem
perde.
"""
import hashlib
import json
import os
import shutil
import sys
import time
from datetime import datetime, timedelta, timezone

from config import DIR_EXECUCAO

NOME_STATUS = "backup_status.json"

# Arquivos de RUNTIME, nao de dado. A lista e minima de proposito:
# tudo que ela exclui e coisa que este projeto decide NAO proteger, e
# uma lista generosa esconderia dado atras de conveniencia.
#
#   poller.lock - byte travado com msvcrt pelo processo vivo. Nao da
#     para copiar enquanto o poller roda, e uma trava no destino seria
#     ruido: a trava e do processo, nao da serie.
#
# poller.log NAO entra aqui. O CSV diz QUAIS minutos faltaram e o log
# diz POR QUE; perder o log e perder metade do registro.
EXCLUIDOS = ("poller.lock",)
HORAS_MAX = 24

# --------------------------------------------------------------------
# O BURACO QUE ESTE ARQUIVO NAO PODE FECHAR SOZINHO
#
# `copiar()` prova que os arquivos foram ESCRITOS na pasta do OneDrive.
# Nao prova que o OneDrive REPLICOU nada. Se o cliente estiver pausado,
# deslogado ou sem quota, os arquivos ficam no mesmo disco, o status diz
# "em dia", e a protecao e zero.
#
# Isso e um instrumento afirmando sucesso que nao mediu - a familia
# inteira de erros deste projeto, na ultima camada que sobrou.
#
# Nao ha como medir daqui sem depender de sinal fragil (atributo de
# arquivo, log do cliente, processo vivo). Entao nao se finge que mede:
# exige-se ATESTADO HUMANO da primeira replicacao, por destino. O
# atestado e uma AFIRMACAO DATADA DE UMA PESSOA, nao uma medicao, e o
# proprio arquivo diz isso.
#
#   python backup.py --confirmar-replicacao
# --------------------------------------------------------------------
NOME_ATESTADO = "replicacao_confirmada.json"

# O ATESTADO VENCE, e isto nao e burocracia.
#
# Atestado sem prazo resolve "ninguem verificou nunca" e NAO resolve
# "alguem verificou uma vez, em marco". O cliente de sincronizacao pode
# ser pausado, deslogado, estourar quota ou perder a vinculacao da conta
# a qualquer momento DEPOIS da confirmacao. O arquivo continua la, o
# porteiro continua aprovando, e a replicacao parou meses atras.
#
# E uma afirmacao pontual tratada como garantia continua - a forma exata
# do defeito que este projeto passou a semana cacando, agora na camada
# que protege o unico ativo irrecuperavel.
#
# Trinta dias converte "verificado uma vez" em "verificado
# periodicamente", que e a unica forma honesta de afirmar uma
# propriedade que muda sozinha. Custa dez segundos por mes.
DIAS_ATESTADO = 30
DIAS_AVISO_ATESTADO = 7


class BackupInvalido(Exception):
    """Destino ausente, no mesmo disco, ou dentro do proprio projeto."""


class BackupVencido(Exception):
    """A ultima copia bem-sucedida e velha demais para contar como copia."""


def agora():
    return datetime.now(timezone.utc)


def iso(dt):
    return dt.replace(microsecond=0).isoformat()


# Redirecionamento do status, usado SO pelo autoteste.
#
# Em 28/09/2026 o autoteste sobrescreveu o status de PRODUCAO com o de
# uma copia de 17 bytes numa pasta temporaria, e o porteiro passou a
# reportar "backup em dia" com base nela. O bloco de isolamento do Gate
# 1b nao pegou porque ele tira impressao de dados_execucao/, e o status
# mora na raiz do projeto: o detector de vazamento tinha escopo MENOR
# que o vazamento.
#
# E a terceira vez neste projeto que um caminho e resolvido de um jeito
# e escrito de outro - depois do CAMINHO_LOG preso no import e do
# `>> log` no .bat.
_STATUS_ALT = None


def caminho_status():
    """No projeto, FORA de dados_execucao.

    O Gate 1b tira impressao digital de DIR_EXECUCAO e reprova se algo
    ali muda durante o teste. Um status escrito dentro dele faria o
    proprio backup reprovar o gate de isolamento.
    """
    if _STATUS_ALT:
        return _STATUS_ALT
    return os.path.join(os.path.dirname(os.path.abspath(DIR_EXECUCAO)),
                        NOME_STATUS)


def caminho_atestado():
    """Ao lado do status: a confirmacao humana de que a replicacao ocorreu."""
    return os.path.join(os.path.dirname(caminho_status()), NOME_ATESTADO)


def destino():
    d = os.environ.get("SNIPER_BACKUP_DIR", "").strip()
    if not d:
        raise BackupInvalido(
            "SNIPER_BACKUP_DIR nao definida. Sem default no fonte: um "
            "default apontando para dentro desta maquina seria um backup "
            "que nao e backup, e pareceria um.")
    return d


# Raizes de sincronizacao declaradas PELO PROPRIO SISTEMA, por variavel
# de ambiente. Nao sao adivinhadas por nome de pasta: uma pasta chamada
# "OneDrive" que ninguem sincroniza nao replica nada, e o teste de nome
# aceitaria justamente o caso que nao protege.
VARS_NUVEM = ("OneDrive", "OneDriveConsumer", "OneDriveCommercial")


def mesmo_volume(a, b):
    """
    True se `a` e `b` estao no MESMO volume, perguntado ao SISTEMA.

    O sinal primario e `st_dev`, que vem do sistema de arquivos. A letra
    do caminho e secundaria e sozinha nao basta: uma pasta chamada
    "Google Drive" em C: tem a letra C: e nao replica nada, e um ponto de
    montagem pode ter letra propria com o mesmo volume por baixo.

    Se nao der para perguntar ao sistema, a resposta conservadora e
    "mesmo volume" - que EXIGE justificativa extra em vez de dispensar.
    """
    try:
        return os.stat(a).st_dev == os.stat(b).st_dev
    except OSError:
        return (os.path.splitdrive(os.path.abspath(a))[0].upper()
                == os.path.splitdrive(os.path.abspath(b))[0].upper())


def raiz_nuvem(caminho):
    """(nome_da_var, raiz) se `caminho` esta sob raiz sincronizada, ou None."""
    c = os.path.abspath(caminho).rstrip(os.sep)
    for v in VARS_NUVEM:
        raiz = os.environ.get(v, "").strip().rstrip(os.sep)
        if not raiz:
            continue
        raiz = os.path.abspath(raiz)
        if c == raiz or c.startswith(raiz + os.sep):
            return v, raiz
    return None


def conferir_destino(d, origem=None):
    """
    Recusa destino que nao protege contra morte do disco.

    O risco declarado e o disco morrer. Uma pasta no mesmo volume nao
    protege contra isso - EXCETO se ela for replicada para fora da
    maquina, que e o caso de uma raiz sincronizada.

    A permissao nao e por nome de pasta. E pela variavel de ambiente que
    o proprio sistema define ao instalar o cliente de sincronizacao: uma
    pasta batizada "OneDrive" que ninguem sincroniza nao replica nada, e
    aceitar por nome deixaria passar exatamente o caso que nao protege.
    """
    origem = os.path.abspath(origem or DIR_EXECUCAO)
    d_abs = os.path.abspath(d)
    if not os.path.isdir(d_abs):
        raise BackupInvalido(
            f"destino {d_abs!r} nao existe. Crie a pasta primeiro - "
            f"criar sozinho esconderia caminho digitado errado.")
    if d_abs == origem or d_abs.startswith(origem + os.sep):
        raise BackupInvalido(
            f"destino {d_abs!r} esta DENTRO da origem. Isso nao e copia.")
    if mesmo_volume(d_abs, origem):
        nuvem = raiz_nuvem(d_abs)
        if nuvem is None:
            raise BackupInvalido(
                f"destino esta no MESMO VOLUME da origem "
                f"({os.path.splitdrive(d_abs)[0]}, st_dev igual) e nao esta "
                f"sob raiz sincronizada. Backup no mesmo disco nao protege "
                f"contra o risco declarado, que e o disco morrer. Use um "
                f"volume distinto - como a letra de um cliente em modo "
                f"streaming - ou pasta sincronizada declarada pelo sistema "
                f"({', '.join(VARS_NUVEM)}).")
    return d_abs


def justificativa_destino(d, origem=None):
    """Por que este destino conta como copia. Vai para o status."""
    d_abs = os.path.abspath(d)
    origem = os.path.abspath(origem or DIR_EXECUCAO)
    if not mesmo_volume(d_abs, origem):
        return (f"volume distinto ({os.path.splitdrive(d_abs)[0]}), "
                f"confirmado por st_dev")
    nuvem = raiz_nuvem(d_abs)
    if nuvem:
        return f"mesmo volume, sob raiz sincronizada {nuvem[0]}={nuvem[1]}"
    return "sem justificativa"


def _digest(caminho, blocos=1 << 20):
    h = hashlib.sha256()
    with open(caminho, "rb") as f:
        for b in iter(lambda: f.read(blocos), b""):
            h.update(b)
    return h.hexdigest()


def copiar(origem=None, dest=None, verificar_digest=True):
    """
    Copia aditiva de origem -> dest/<basename(origem)>.

    Devolve o dicionario de status. Levanta em qualquer erro: copia que
    falha em silencio e o defeito que este arquivo existe para nao ter.
    """
    origem = os.path.abspath(origem or DIR_EXECUCAO)
    if not os.path.isdir(origem):
        raise BackupInvalido(f"origem {origem!r} nao existe")
    raiz = conferir_destino(dest or destino(), origem)
    alvo = os.path.join(raiz, os.path.basename(origem))
    os.makedirs(alvo, exist_ok=True)

    copiados, iguais, bytes_copiados, erros = 0, 0, 0, []
    for nome in sorted(os.listdir(origem)):
        o = os.path.join(origem, nome)
        if not os.path.isfile(o) or nome in EXCLUIDOS:
            continue
        d = os.path.join(alvo, nome)
        try:
            st_o = os.stat(o)
            precisa = True
            if os.path.exists(d):
                st_d = os.stat(d)
                precisa = (st_o.st_size != st_d.st_size
                           or st_o.st_mtime_ns > st_d.st_mtime_ns)
            if not precisa:
                iguais += 1
                continue
            shutil.copy2(o, d)
            if verificar_digest and _digest(o) != _digest(d):
                raise OSError("digest divergente apos a copia")
            copiados += 1
            bytes_copiados += st_o.st_size
        except OSError as e:
            erros.append(f"{nome}: {type(e).__name__}: {e}")

    # Contagem no DESTINO, nao na origem: e ele que tem de estar certo.
    #
    # NOME_STATUS e excluido: ele e escrito por este proprio arquivo e
    # nao e dado coletado. Contado junto, o numero inflava em 1 a partir
    # da SEGUNDA execucao - metrica que muda de definicao sozinha entre
    # a primeira e a segunda rodada. O autoteste pegou isso.
    no_destino = [n for n in os.listdir(alvo)
                  if os.path.isfile(os.path.join(alvo, n))
                  and n != NOME_STATUS and n not in EXCLUIDOS]
    faltando = sorted(
        n for n in os.listdir(origem)
        if os.path.isfile(os.path.join(origem, n))
        and n not in EXCLUIDOS and n not in no_destino)

    status = {
        "quando_utc": iso(agora()),
        "origem": origem,
        "destino": alvo,
        "por_que_conta_como_copia": justificativa_destino(raiz, origem),
        "excluidos_por_serem_runtime": list(EXCLUIDOS),
        "arquivos_no_destino": len(no_destino),
        "copiados": copiados,
        "inalterados": iguais,
        "bytes_copiados": bytes_copiados,
        "faltando_no_destino": faltando,
        "erros": erros,
    }
    # `ok` EXIGE justificativa. Um status com "sem justificativa" e
    # ok=true seria contradicao interna: o guarda registrou que o destino
    # nao se justifica como copia externa, e o registro dizia que estava
    # tudo bem. Aconteceu em 28/09/2026, quando o autoteste - que roda
    # com o guarda desligado - escreveu no status de producao.
    if status["por_que_conta_como_copia"] == "sem justificativa":
        erros.append(
            "destino sem justificativa de copia externa: nao esta em outro "
            "volume nem sob raiz sincronizada declarada pelo sistema")
    status["ok"] = not erros and not faltando
    with open(caminho_status(), "w", encoding="utf-8") as f:
        json.dump(status, f, ensure_ascii=False, indent=2)
    # Uma segunda copia do status VAI para o destino, para que a pasta de
    # backup diga por si mesma quando foi atualizada - sem depender de
    # um arquivo que mora no disco que pode morrer.
    try:
        with open(os.path.join(alvo, NOME_STATUS), "w",
                  encoding="utf-8") as f:
            json.dump(status, f, ensure_ascii=False, indent=2)
    except OSError as e:
        status["erros"].append(f"status no destino: {e}")
        status["ok"] = False

    if not status["ok"]:
        raise BackupInvalido(
            f"copia incompleta: {len(erros)} erro(s), "
            f"{len(faltando)} arquivo(s) faltando no destino. "
            f"{'; '.join(erros[:3])}")
    return status


def ler_status():
    try:
        with open(caminho_status(), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def confirmar_replicacao(quem="", dest=None):
    """
    Grava o atestado humano de que a replicacao para fora do disco ocorreu.

    NAO e medicao. E a afirmacao datada de uma pessoa que abriu o
    servico na web e viu os arquivos la. Fica escrito no proprio
    atestado para que ninguem confunda as duas coisas depois.
    """
    alvo = os.path.join(conferir_destino(dest or destino()),
                        os.path.basename(os.path.abspath(DIR_EXECUCAO)))
    agora_ = agora()
    at = {
        "destino": alvo,
        "quando_utc": iso(agora_),
        "vence_em_utc": iso(agora_ + timedelta(days=DIAS_ATESTADO)),
        "validade_dias": DIAS_ATESTADO,
        "quem": quem or os.environ.get("USERNAME", "nao informado"),
        "natureza": "AFIRMACAO HUMANA, NAO MEDICAO",
        "por_que_vence": (
            "a sincronizacao pode ser pausada, deslogada, estourar quota ou "
            "perder a vinculacao da conta DEPOIS desta confirmacao. Sem "
            "prazo, uma afirmacao pontual viraria garantia continua."),
        "o_que_foi_conferido": (
            "abri o servico de sincronizacao na web, entrei na pasta de "
            "destino e vi os arquivos de contexto la - fora deste disco"),
    }
    with open(caminho_atestado(), "w", encoding="utf-8") as f:
        json.dump(at, f, ensure_ascii=False, indent=2)
    return at


def ler_atestado():
    try:
        with open(caminho_atestado(), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def exigir_atestado(alvo):
    """Levanta BackupVencido se ninguem confirmou a replicacao DESTE destino."""
    at = ler_atestado()
    if at is None:
        raise BackupVencido(
            f"ninguem confirmou que a replicacao para fora do disco "
            f"ocorreu. Os arquivos estao em {alvo}, mas isso prova apenas "
            f"que foram ESCRITOS ali - nao que o cliente de sincronizacao "
            f"os enviou. Confira na web e rode: "
            f"python backup.py --confirmar-replicacao")
    if os.path.normcase(at.get("destino", "")) != os.path.normcase(alvo):
        raise BackupVencido(
            f"o atestado existente e para {at.get('destino')!r}, e o destino "
            f"atual e {alvo!r}. Destino novo exige confirmacao nova.")
    try:
        quando = datetime.fromisoformat(at["quando_utc"])
    except (KeyError, ValueError) as e:
        raise BackupVencido(f"carimbo ilegivel no atestado: {e}") from e
    idade = agora() - quando
    limite = timedelta(days=at.get("validade_dias") or DIAS_ATESTADO)
    if idade > limite:
        raise BackupVencido(
            f"o atestado de replicacao venceu: confirmado em "
            f"{at['quando_utc']}, {idade.days} dias atras, validade de "
            f"{limite.days} dias. A sincronizacao pode ter parado desde "
            f"entao - confirmacao pontual nao e garantia continua. "
            f"Confira na web e rode: python backup.py "
            f"--confirmar-replicacao")
    at["_dias_restantes"] = (limite - idade).days
    return at


def verificar_frescor(horas_max=HORAS_MAX, exigir_replicacao=True):
    """
    (ok, mensagem). Levanta BackupVencido se passou do prazo.

    Chamada pelo `validacao_contexto.py` e registrada pelo poller na
    subida. Ausencia de status conta como VENCIDO, nunca como zero:
    nunca ter copiado e o pior caso, nao o caso neutro.

    A AUTORIDADE E O DESTINO, nao o status local. O status local mora no
    disco que pode morrer e pode ser sobrescrito por qualquer coisa que
    rode nesta maquina - foi o que o autoteste fez em 28/09/2026. O
    status que vale e o que esta DENTRO da pasta de backup: se ele nao
    existir ou discordar, isto reprova.
    """
    s = ler_status()
    if s is None:
        raise BackupVencido(
            f"nao existe {NOME_STATUS}. Nenhuma copia registrada - e "
            f"ausencia de medida nao e medida de zero (invariante 11).")
    if not s.get("ok"):
        raise BackupVencido(
            f"a ultima copia registrada FALHOU em {s.get('quando_utc')}: "
            f"{'; '.join(s.get('erros') or ['motivo nao registrado'])}")
    try:
        quando = datetime.fromisoformat(s["quando_utc"])
    except (KeyError, ValueError) as e:
        raise BackupVencido(f"carimbo ilegivel no status: {e}") from e
    idade = agora() - quando
    if idade > timedelta(hours=horas_max):
        raise BackupVencido(
            f"ultima copia em {s['quando_utc']} - "
            f"{idade.total_seconds() / 3600:.1f} h atras, limite "
            f"{horas_max} h. Os dados de hoje nao tem copia.")

    # --- a autoridade e o DESTINO ---------------------------------
    alvo = s.get("destino") or ""
    if not alvo:
        raise BackupVencido("o status local nao diz qual e o destino")
    remoto_p = os.path.join(alvo, NOME_STATUS)
    try:
        with open(remoto_p, encoding="utf-8") as f:
            remoto = json.load(f)
    except (OSError, ValueError) as e:
        raise BackupVencido(
            f"o status local diz que copiou para {alvo!r}, mas nao ha "
            f"{NOME_STATUS} legivel la ({type(e).__name__}). O status que "
            f"vale e o que mora DENTRO do backup - o local pode ter sido "
            f"escrito por qualquer coisa nesta maquina.") from e
    if not remoto.get("ok"):
        raise BackupVencido(
            f"o status DENTRO do destino marca falha em "
            f"{remoto.get('quando_utc')}")
    if os.path.normcase(remoto.get("destino", "")) != os.path.normcase(alvo):
        raise BackupVencido(
            f"o status no destino aponta para {remoto.get('destino')!r}, "
            f"diferente de {alvo!r}. Os dois registros discordam.")
    try:
        quando_r = datetime.fromisoformat(remoto["quando_utc"])
    except (KeyError, ValueError) as e:
        raise BackupVencido(
            f"carimbo ilegivel no status do destino: {e}") from e
    idade_r = agora() - quando_r
    if idade_r > timedelta(hours=horas_max):
        raise BackupVencido(
            f"o status DENTRO do destino e de {remoto['quando_utc']}, "
            f"{idade_r.total_seconds() / 3600:.1f} h atras. O local esta "
            f"fresco e o do destino nao: sinal de que o local foi escrito "
            f"por algo que nao copiou de verdade.")

    if exigir_replicacao:
        at = exigir_atestado(alvo)
        faltam = at.get("_dias_restantes")
        extra = (f"; replicacao confirmada por {at['quem']} em "
                 f"{at['quando_utc']} (afirmacao humana, "
                 f"{faltam} dia(s) de validade)")
        if faltam is not None and faltam <= DIAS_AVISO_ATESTADO:
            extra += (" -- ATENCAO: reconfirme antes de vencer, ou o "
                      "porteiro vai reprovar")
    else:
        extra = "; replicacao NAO exigida nesta chamada"

    return True, (f"ultima copia {idade.total_seconds() / 3600:.1f} h "
                  f"atras, {remoto.get('arquivos_no_destino')} arquivos em "
                  f"{alvo}{extra}")


# --------------------------------------------------------------------
# AUTOTESTE
# --------------------------------------------------------------------
def _ok(cond, rotulo, detalhe=""):
    print("  %s %s%s" % ("OK   " if cond else "FALHA", rotulo,
                         ("   " + detalhe) if detalhe else ""))
    return bool(cond)


def _recusa(fn, exc, rotulo):
    try:
        fn()
    except exc as e:
        return _ok(True, rotulo, "-> " + type(e).__name__)
    except Exception as e:  # noqa: BLE001
        return _ok(False, rotulo, "-> excecao errada: " + type(e).__name__)
    return _ok(False, rotulo, "-> NAO recusou")


def _impressao(caminho):
    try:
        st = os.stat(caminho)
        return (st.st_size, st.st_mtime_ns)
    except OSError:
        return None


def autoteste():
    global _STATUS_ALT
    import tempfile
    r = []
    base = tempfile.mkdtemp(prefix="backup_teste_")

    # ISOLAMENTO, antes de qualquer coisa.
    #
    # Em 28/09/2026 este autoteste sobrescreveu o status de PRODUCAO com
    # o de uma copia de 17 bytes numa pasta temporaria, e o porteiro
    # passou a reportar "backup em dia" com base nela. O bloco de
    # isolamento do Gate 1b nao pegou porque ele vigia dados_execucao/, e
    # o status mora na raiz do projeto - o detector tinha escopo MENOR
    # que o vazamento.
    #
    # Agora o status e REDIRECIONADO para a pasta temporaria, e a
    # impressao dos arquivos de producao e conferida no fim.
    prod_status, prod_atestado = caminho_status(), caminho_atestado()
    antes = (_impressao(prod_status), _impressao(prod_atestado))
    _STATUS_ALT = os.path.join(base, NOME_STATUS)
    origem = os.path.join(base, "dados")
    os.makedirs(origem)
    for i in range(3):
        with open(os.path.join(origem, "arq%d.csv" % i), "w") as f:
            f.write("ts,v\n1,%d\n" % i)

    print(chr(10) + "1. RECUSA DESTINO QUE NAO E BACKUP")
    r.append(_recusa(lambda: conferir_destino(os.path.join(base, "nao_existe"),
                                              origem),
                     BackupInvalido, "destino inexistente"))
    r.append(_recusa(lambda: conferir_destino(origem, origem),
                     BackupInvalido, "destino igual a origem"))
    r.append(_recusa(lambda: conferir_destino(os.path.join(origem, "sub"),
                                              origem),
                     BackupInvalido, "destino dentro da origem"))
    r.append(_recusa(lambda: conferir_destino(base, origem),
                     BackupInvalido, "destino no mesmo volume"))
    # a permissao e por variavel de ambiente, nunca por nome de pasta
    falsa = os.path.join(base, "OneDrive")
    os.makedirs(falsa, exist_ok=True)
    r.append(_recusa(lambda: conferir_destino(falsa, origem),
                     BackupInvalido,
                     "pasta CHAMADA OneDrive sem sincronizacao"))
    os.environ["OneDrive"] = falsa
    try:
        r.append(_ok(conferir_destino(falsa, origem) is not None,
                     "a mesma pasta passa quando o sistema a declara",
                     "OneDrive=<raiz>"))
        r.append(_ok("raiz sincronizada" in
                     justificativa_destino(falsa, origem),
                     "o status registra POR QUE o destino conta"))
    finally:
        os.environ.pop("OneDrive", None)
    os.environ.pop("SNIPER_BACKUP_DIR", None)
    r.append(_recusa(destino, BackupInvalido, "sem SNIPER_BACKUP_DIR"))

    print(chr(10) + "2. FRESCOR: AUSENCIA CONTA COMO VENCIDO")
    # `real` aqui e o status REDIRECIONADO, nao o de producao.
    real = caminho_status()
    assert base in real, "o status deveria estar redirecionado para o temp"
    if os.path.exists(real):
        os.remove(real)
    r.append(_recusa(verificar_frescor, BackupVencido, "sem status nenhum"))
    for rotulo, dados in (
            ("copia marcada como falha",
             {"quando_utc": iso(agora()), "ok": False,
              "erros": ["disco cheio"]}),
            ("copia de 48 h atras",
             {"quando_utc": iso(agora() - timedelta(hours=48)),
              "ok": True, "arquivos_no_destino": 3, "destino": "x"}),
            ("carimbo ilegivel", {"quando_utc": "ontem", "ok": True}),
            ("status sem destino",
             {"quando_utc": iso(agora()), "ok": True})):
        with open(real, "w", encoding="utf-8") as f:
            json.dump(dados, f)
        r.append(_recusa(verificar_frescor, BackupVencido, rotulo))

    print(chr(10) + "2b. A AUTORIDADE E O DESTINO, NAO O STATUS LOCAL")
    # Um status local fresco e valido, apontando para um destino que NAO
    # tem o proprio status, tem de reprovar. E exatamente o estado que o
    # vazamento de 28/09/2026 produziu: local dizendo "em dia", nada
    # provando isso do lado do backup.
    remoto_dir = os.path.join(base, "destino_remoto")
    os.makedirs(remoto_dir, exist_ok=True)
    local_fresco = {"quando_utc": iso(agora()), "ok": True,
                    "arquivos_no_destino": 3, "destino": remoto_dir}
    with open(real, "w", encoding="utf-8") as f:
        json.dump(local_fresco, f)
    r.append(_recusa(verificar_frescor, BackupVencido,
                     "local fresco, destino sem status"))

    def _por_status_remoto(dados):
        with open(os.path.join(remoto_dir, NOME_STATUS), "w",
                  encoding="utf-8") as f:
            json.dump(dados, f)

    _por_status_remoto({"quando_utc": iso(agora() - timedelta(hours=48)),
                        "ok": True, "destino": remoto_dir,
                        "arquivos_no_destino": 3})
    r.append(_recusa(verificar_frescor, BackupVencido,
                     "local fresco, destino de 48 h"))
    _por_status_remoto({"quando_utc": iso(agora()), "ok": False,
                       "destino": remoto_dir, "arquivos_no_destino": 3})
    r.append(_recusa(verificar_frescor, BackupVencido,
                     "destino marca falha"))
    _por_status_remoto({"quando_utc": iso(agora()), "ok": True,
                       "destino": os.path.join(base, "outro"),
                       "arquivos_no_destino": 3})
    r.append(_recusa(verificar_frescor, BackupVencido,
                     "os dois registros discordam do destino"))

    print(chr(10) + "2c. SEM ATESTADO DE REPLICACAO, NAO CONTA")
    _por_status_remoto({"quando_utc": iso(agora()), "ok": True,
                       "destino": remoto_dir, "arquivos_no_destino": 3})
    r.append(_recusa(verificar_frescor, BackupVencido,
                     "ninguem confirmou a replicacao"))
    with open(caminho_atestado(), "w", encoding="utf-8") as f:
        json.dump({"destino": remoto_dir, "quando_utc": iso(agora()),
                   "quem": "teste", "natureza": "AFIRMACAO HUMANA"}, f)
    ok, msg = verificar_frescor()
    r.append(_ok(ok, "com atestado e os dois status frescos, aceita",
                 msg.split(";")[0]))
    with open(caminho_atestado(), "w", encoding="utf-8") as f:
        json.dump({"destino": os.path.join(base, "mudou"),
                   "quando_utc": iso(agora()), "quem": "teste"}, f)
    r.append(_recusa(verificar_frescor, BackupVencido,
                     "atestado de OUTRO destino nao serve"))

    print(chr(10) + "2d. O ATESTADO VENCE")
    # "alguem verificou uma vez, em marco" tem de reprovar igual a
    # "ninguem verificou nunca". A sincronizacao pode parar depois da
    # confirmacao, e o arquivo de atestado nao sabe disso.
    def _atesta(dias_atras, **kw):
        d = {"destino": remoto_dir, "quem": "teste",
             "quando_utc": iso(agora() - timedelta(days=dias_atras)),
             "validade_dias": DIAS_ATESTADO}
        d.update(kw)
        with open(caminho_atestado(), "w", encoding="utf-8") as f:
            json.dump(d, f)

    _atesta(40)
    r.append(_recusa(verificar_frescor, BackupVencido,
                     "atestado de 40 dias atras"))
    _atesta(31)
    r.append(_recusa(verificar_frescor, BackupVencido,
                     "atestado de 31 dias atras"))
    _atesta(29)
    ok, msg = verificar_frescor()
    r.append(_ok(ok, "atestado de 29 dias ainda vale",
                 "restam %s dia(s)"
                 % exigir_atestado(remoto_dir).get("_dias_restantes")))
    _atesta(25)
    _, msg = verificar_frescor()
    r.append(_ok("ATENCAO" in msg, "avisa quando faltam <= %d dias"
                 % DIAS_AVISO_ATESTADO))
    _atesta(1)
    _, msg = verificar_frescor()
    r.append(_ok("ATENCAO" not in msg, "nao avisa quando esta longe de vencer"))
    _atesta(0, quando_utc="ontem")
    r.append(_recusa(verificar_frescor, BackupVencido,
                     "carimbo ilegivel no atestado"))
    # e um atestado gravado agora carrega o prazo escrito nele
    _atesta(0)
    at_novo = ler_atestado()
    r.append(_ok(at_novo.get("validade_dias") == DIAS_ATESTADO,
                 "o atestado carrega a propria validade"))

    print(chr(10) + "3. A COPIA COPIA, E NAO APAGA NO DESTINO")
    # Um segundo volume nao da para simular em teste. Em vez de desligar
    # o guarda com um stub - que foi o que escondia o defeito de
    # `ok: true` com "sem justificativa" - o temp e DECLARADO como raiz
    # sincronizada, pela mesma variavel de ambiente que vale em producao.
    # Assim o caminho exercitado e o real, guarda incluso.
    dest = os.path.join(base, "espelho")
    os.makedirs(dest)
    alvo = os.path.join(dest, "dados")

    def copia():
        return copiar(origem, dest, verificar_digest=True)

    os.environ["OneDrive"] = base
    try:
        s1 = copia()
        r.append(_ok(s1["copiados"] == 3, "copiou os tres arquivos",
                     "copiados=%d" % s1["copiados"]))
        r.append(_ok(s1["ok"], "status ok"))
        s2 = copia()
        r.append(_ok(s2["copiados"] == 0 and s2["inalterados"] == 3,
                     "segunda passada nao recopia",
                     "copiados=%d inalterados=%d"
                     % (s2["copiados"], s2["inalterados"])))
        os.remove(os.path.join(origem, "arq1.csv"))
        s3 = copia()
        sobrou = os.path.exists(os.path.join(alvo, "arq1.csv"))
        r.append(_ok(sobrou, "arquivo apagado na ORIGEM permanece no destino",
                     "aditivo, nao espelho"))
        r.append(_ok(s3["arquivos_no_destino"] == 3,
                     "destino mantem os tres",
                     "no destino=%d" % s3["arquivos_no_destino"]))
        with open(os.path.join(origem, "arq0.csv"), "a") as f:
            f.write("2,99\n")
        s4 = copia()
        r.append(_ok(s4["copiados"] == 1, "arquivo que cresceu e recopiado"))
        r.append(_ok(os.path.exists(os.path.join(alvo, NOME_STATUS)),
                     "o destino carrega o proprio status"))
    finally:
        os.environ.pop("OneDrive", None)
        _STATUS_ALT = None
        shutil.rmtree(base, ignore_errors=True)

    print(chr(10) + "4. ISOLAMENTO: O TESTE NAO TOCOU PRODUCAO")
    depois = (_impressao(prod_status), _impressao(prod_atestado))
    r.append(_ok(antes[0] == depois[0],
                 "backup_status.json de producao intacto",
                 "antes=%s depois=%s" % (antes[0], depois[0])))
    r.append(_ok(antes[1] == depois[1],
                 "replicacao_confirmada.json de producao intacto"))
    r.append(_ok(_STATUS_ALT is None, "o redirecionamento foi desfeito"))

    print(chr(10) + "=" * 62)
    print("%d/%d verificacoes passaram" % (sum(r), len(r)))
    print("=" * 62)
    return 0 if all(r) else 1


def main(argv):
    if "--autoteste" in argv:
        return autoteste()
    if "--confirmar-replicacao" in argv:
        print("CONFIRMACAO DE REPLICACAO")
        print("Isto NAO e uma medicao. E a sua afirmacao, datada, de que")
        print("voce abriu o servico de sincronizacao NA WEB, entrou na")
        print("pasta de destino e VIU os arquivos de contexto la.")
        print("")
        print("O backup.py sabe que escreveu os arquivos na pasta local.")
        print("Ele nao tem como saber se o cliente replicou: pausado,")
        print("deslogado ou sem quota, o resultado e arquivo no mesmo")
        print("disco com status dizendo 'em dia'. Por isso a confirmacao")
        print("e humana, e por isso ela fica registrada como humana.")
        print("")
        try:
            at = confirmar_replicacao(quem=" ".join(
                a for a in argv if not a.startswith("--")))
        except BackupInvalido as e:
            print("FALHOU: %s" % e)
            return 1
        print("registrado: %s por %s" % (at["quando_utc"], at["quem"]))
        print("destino:    %s" % at["destino"])
        print("Se o destino mudar, a confirmacao tera de ser refeita.")
        return 0
    if "--verificar" in argv:
        try:
            _, msg = verificar_frescor()
        except BackupVencido as e:
            print("BACKUP VENCIDO: %s" % e)
            return 1
        print("backup em dia: %s" % msg)
        return 0
    t0 = time.time()
    try:
        s = copiar()
    except (BackupInvalido, BackupVencido) as e:
        print("BACKUP FALHOU: %s" % e)
        return 1
    print("backup ok em %.1f s" % (time.time() - t0))
    print("  destino            %s" % s["destino"])
    print("  arquivos           %d" % s["arquivos_no_destino"])
    print("  copiados agora     %d  (%.1f KiB)"
          % (s["copiados"], s["bytes_copiados"] / 1024.0))
    print("  inalterados        %d" % s["inalterados"])
    print("  status             %s" % caminho_status())
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
