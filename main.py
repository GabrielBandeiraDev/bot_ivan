import os
import json
import sqlite3
import requests

from datetime import datetime
from pathlib import Path

from apscheduler.schedulers.blocking import BlockingScheduler
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
ENV_FILE = BASE_DIR / ".env"
ARQUIVO_ESTADO = BASE_DIR / "estado.json"
DB_PATH = BASE_DIR / "separacao.db"

MODELOS = ["Stage 280W", "VL 320 Sub", "CI6S PLUS"]
STATUS_OK = {"OK"}


def criar_env_se_necessario():
    if ENV_FILE.exists():
        return

    ENV_FILE.write_text(
        "BOT_TOKEN=\n"
        "CHAT_ID=-5185287364\n",
        encoding="utf-8",
    )
    print(f"Arquivo .env criado em {ENV_FILE}")
    print("Coloque o token do bot em BOT_TOKEN e rode de novo.")


def carregar_config():
    criar_env_se_necessario()
    load_dotenv(ENV_FILE)

    bot_token = os.getenv("BOT_TOKEN", "").strip()
    chat_id = os.getenv("CHAT_ID", "-5185287364").strip()

    if not bot_token:
        raise SystemExit(
            "BOT_TOKEN vazio. Edite o arquivo .env com a chave do bot e rode novamente."
        )

    return bot_token, chat_id


BOT_TOKEN = ""
CHAT_ID = ""


def enviar(msg):
    requests.post(
        f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
        json={"chat_id": CHAT_ID, "text": msg},
        timeout=30,
    )


def estado_inicial_modelo():
    return {
        "percentual": 0,
        "skus_pendentes": [],
        "skus_pendentes_anterior": [],
    }


def carregar_estado():
    if not ARQUIVO_ESTADO.exists():
        return {modelo: estado_inicial_modelo() for modelo in MODELOS}

    with open(ARQUIVO_ESTADO, encoding="utf-8") as f:
        estado = json.load(f)

    if "percentual" in estado:
        return {modelo: estado_inicial_modelo() for modelo in MODELOS}

    for modelo in MODELOS:
        estado.setdefault(modelo, estado_inicial_modelo())

    return estado


def salvar_estado(dados):
    with open(ARQUIVO_ESTADO, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=2)


def obter_itens(modelo):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT
            modelo,
            sku,
            descricao,
            responsavel,
            status,
            prazo,
            qtd_necessaria,
            qtd_separada,
            observacao
        FROM separacao
        WHERE modelo = ?
          AND sku IS NOT NULL
          AND TRIM(sku) != ''
          AND UPPER(TRIM(sku)) != 'SKU'
        """,
        (modelo,),
    )

    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows


def atualizar_skus_pendentes(estado_modelo, itens):
    skus_ativos = sorted(
        str(item["sku"]).strip()
        for item in itens
        if str(item["status"] or "").strip().upper() not in STATUS_OK
    )
    estado_modelo["skus_pendentes"] = skus_ativos
    return estado_modelo


def formatar_percentual(percentual):
    return f"{percentual:.2f}".replace(".", ",") + "%"


def situacao(percentual):
    return "Concluído" if percentual >= 100 else "Em andamento"


def montar_mensagem_status(modelo, percentual, pendentes):
    msg = (
        f"📊 Status do Modelo: {modelo}\n\n"
        f"🔹 Progresso: {formatar_percentual(percentual)}\n"
        f"🔹 Situação: {situacao(percentual)}"
    )

    if pendentes:
        skus = "\n".join(f"• {str(item['sku']).strip()}" for item in pendentes)
        msg += f"\n\n⏳ Itens pendentes:\n{skus}"

    if percentual >= 100:
        msg += "\n\n✅ Separação concluída!"
    else:
        msg += "\n\n🚀 Continue o processo para atingir 100%"

    return msg


def calcular_metricas(itens):
    total = len(itens)
    if total == 0:
        return 0

    ok = sum(
        1 for item in itens
        if str(item["status"] or "").strip().upper() in STATUS_OK
    )
    return round((ok / total) * 100, 2)


def listar_pendentes(itens):
    return [
        item for item in itens
        if str(item["status"] or "").strip().upper() not in STATUS_OK
    ]


def processar_modelo(modelo, estado, enviar_mudancas):
    itens = obter_itens(modelo)
    if not itens:
        return None

    percentual = calcular_metricas(itens)
    estado_modelo = atualizar_skus_pendentes(estado.setdefault(modelo, estado_inicial_modelo()), itens)

    ultimo_percentual = estado_modelo.get("percentual", 0)
    skus_anteriores = set(estado_modelo.get("skus_pendentes_anterior", []))
    skus_atuais = set(estado_modelo.get("skus_pendentes", []))

    mudou = percentual != ultimo_percentual or skus_atuais != skus_anteriores
    pendentes = listar_pendentes(itens)
    mensagem = montar_mensagem_status(modelo, percentual, pendentes)

    if enviar_mudancas and mudou:
        enviar(mensagem)
        estado_modelo["ultima_mudanca"] = datetime.now().isoformat()

    estado_modelo["percentual"] = percentual
    estado_modelo["skus_pendentes_anterior"] = list(skus_atuais)
    estado[modelo] = estado_modelo

    return mensagem if not enviar_mudancas else None


def analisar():
    estado = carregar_estado()

    for modelo in MODELOS:
        processar_modelo(modelo, estado, enviar_mudancas=True)

    salvar_estado(estado)


def resumo():
    estado = carregar_estado()
    mensagens = []

    for modelo in MODELOS:
        msg = processar_modelo(modelo, estado, enviar_mudancas=False)
        if msg:
            mensagens.append(msg)

    if not mensagens:
        enviar("📊 Nenhum item encontrado no banco separacao.db")
    else:
        for msg in mensagens:
            enviar(msg)

    salvar_estado(estado)


def main():
    global BOT_TOKEN, CHAT_ID
    BOT_TOKEN, CHAT_ID = carregar_config()

    if not DB_PATH.exists():
        raise SystemExit(
            f"Banco {DB_PATH.name} não encontrado. "
            "Rode testeplanilha.py primeiro para importar os dados."
        )

    scheduler = BlockingScheduler()

    scheduler.add_job(analisar, "interval", minutes=5)
    scheduler.add_job(resumo, "cron", hour="8,12,18")

    enviar("🤖 Bot de separação iniciado. Monitorando 3 modelos.")
    resumo()
    print("Bot iniciado...")

    scheduler.start()


if __name__ == "__main__":
    main()
