import sqlite3

import pandas as pd

SHEET_ID = "1kc6yVfFWnKOIUnY1uNenvHfgqZYHqY0UfY4EwLUf-Rc"

ABAS = [
    {"nome": "Stage 280W", "gid": 2011103894},
    {"nome": "VL 320 Sub", "gid": 577741062},
    {"nome": "CI6S PLUS", "gid": 950211462},
]

COLUNAS = [
    "modelo",
    "sku",
    "descricao",
    "qtd_usa",
    "vol_miudz",
    "prazo",
    "qtd_necessaria",
    "qtd_separada",
    "responsavel",
    "status",
    "observacao",
]


def baixar_aba(nome, gid):
    url = (
        f"https://docs.google.com/spreadsheets/d/{SHEET_ID}"
        f"/export?format=csv&gid={gid}"
    )

    df = pd.read_csv(url, skiprows=2)
    df = df.rename(
        columns={
            "SKU": "sku",
            "DESCRIÇÃO": "descricao",
            "QTD USA": "qtd_usa",
            "VOL / MIUDZ": "vol_miudz",
            "PRAZO": "prazo",
            "QTD A SER PROD": "qtd_necessaria",
            "QT. SEPARADA": "qtd_separada",
            "RESPONSÁVEL": "responsavel",
            "STATUS": "status",
            "OBSERVAÇÕES": "observacao",
        }
    )

    df["modelo"] = nome
    df = df[df["sku"].notna()]
    df["sku"] = df["sku"].astype(str).str.strip()
    df = df[df["sku"] != ""]
    df = df[df["sku"].str.upper() != "SKU"]

    return df[COLUNAS]


def atualizar_banco():
    frames = []
    for aba in ABAS:
        df = baixar_aba(aba["nome"], aba["gid"])
        print(f"  {aba['nome']}: {len(df)} itens")
        frames.append(df)

    dados = pd.concat(frames, ignore_index=True)

    conn = sqlite3.connect("separacao.db")
    dados.to_sql("separacao", conn, if_exists="replace", index=False)
    conn.commit()
    conn.close()

    return len(dados)


def main():
    print("Baixando planilhas...")
    total = atualizar_banco()
    print(f"\nBanco atualizado com {total} registros de {len(ABAS)} abas.")


if __name__ == "__main__":
    main()
