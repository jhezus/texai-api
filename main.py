from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import os

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class DadosLogin(BaseModel):
    usuario: str
    senha: str

class DadosSimulacao(BaseModel):
    anexo: str
    aliquota_iva_estimada: float = 26.5
    rbt12: float = 0.0
    faturamento_mes: float = 0.0
    b2b_percentual: float = 0.0
    folha_12meses: float = 0.0
    compras_mercadorias: float = 0.0
    aluguel_comercial: float = 0.0
    energia_telecom: float = 0.0
    outras_despesas_tributadas: float = 0.0

TABELA_SIMULADA = {
    "Anexo_I":   {"nominal": 0.095, "deduzir": 13860.00, "iva_interno": 0.4900},
    "Anexo_II":  {"nominal": 0.100, "deduzir": 13680.00, "iva_interno": 0.5050},
    "Anexo_III": {"nominal": 0.135, "deduzir": 17640.00, "iva_interno": 0.4720},
    "Anexo_IV":  {"nominal": 0.102, "deduzir": 12420.00, "iva_interno": 0.5100},
    "Anexo_V":   {"nominal": 0.195, "deduzir": 21060.00, "iva_interno": 0.4530},
    "Anexo_III_Regulamentado": {"nominal": 0.135, "deduzir": 17640.00, "iva_interno": 0.4720},
    "Anexo_V_Regulamentado":   {"nominal": 0.195, "deduzir": 21060.00, "iva_interno": 0.4530}
}

@app.get("/", response_class=HTMLResponse)
def ler_tela():
    caminho_html = os.path.join(os.path.dirname(__file__), "index.html")
    with open(caminho_html, "r", encoding="utf-8") as f:
        return f.read()

# AUTENTICAÇÃO DIRETA EM MEMÓRIA (RÁPIDA E SEGURA)
@app.post("/login")
def login(dados: DadosLogin):
    # Credenciais fixas de fábrica prontas para validação comercial
    if dados.usuario == "admin" and dados.senha == "admin123":
        return {"status": "sucesso", "mensagem": "Autenticado com sucesso"}
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuário ou senha incorretos")

@app.post("/calcular")
def calcular_tributacao(dados: DadosSimulacao):
    anexo_calculo = dados.anexo
    memoria_fator_r = ""
    aliquota_base_iva = dados.aliquota_iva_estimada / 100
    possui_deducao_30 = False
    
    if "Regulamentado" in dados.anexo:
        possui_deducao_30 = True
        aliquota_base_iva = aliquota_base_iva * 0.70

    if "Anexo_III" in dados.anexo or "Anexo_V" in dados.anexo:
        if dados.rbt12 > 0:
            proporcao = dados.folha_12meses / dados.rbt12
            pct_fator = round(proporcao * 100, 2)
            sufixo = "_Regulamentado" if possui_deducao_30 else ""
            if proporcao >= 0.28:
                anexo_calculo = "Anexo_III" + sufixo
                memoria_fator_r = f"Fator R: {pct_fator}% (>= 28%). Enquadrado no Anexo III."
            else:
                anexo_calculo = "Anexo_V" + sufixo
                memoria_fator_r = f"Fator R: {pct_fator}% (< 28%). Enquadrado no Anexo V."

    config = TABELA_SIMULADA.get(anexo_calculo, TABELA_SIMULADA["Anexo_I"])
    aliquota_efetiva = max(0.02, ((dados.rbt12 * config["nominal"]) - config["deduzir"]) / dados.rbt12 if dados.rbt12 > 0 else config["nominal"])

    das_puro = dados.faturamento_mes * aliquota_efetiva
    das_reduzido = dados.faturamento_mes * (aliquota_efetiva * (1 - config["iva_interno"]))
    
    total_despesas_credito = dados.compras_mercadorias + dados.aluguel_comercial + dados.energia_telecom + dados.outras_despesas_tributadas
    iva_debito = dados.faturamento_mes * aliquota_base_iva
    iva_credito = total_despesas_credito * aliquota_base_iva
    iva_a_pagar = max(0.0, iva_debito - iva_credito)
    total_hibrido = das_reduzido + iva_a_pagar

    if das_puro < total_hibrido and dados.b2b_percentual < 50:
        veredito = "SIMPLES PURO (POR DENTRO)"
        justificativa = "A sua operação é focada em cliente final (B2C) e o Simples Puro gera o menor desembolso de caixa direto."
    else:
        veredito = "SIMPLES REGULAR (HÍBRIDO)"
        justificativa = "O modelo Híbrido garante crédito integral de IVA para seus clientes PJ, blindando sua competitividade comercial."

    formula_efetiva = f"((R$ {dados.rbt12:,.2f} * {config['nominal']*100}%) - R$ {config['deduzir']:,.2f}) / R$ {dados.rbt12:,.2f} = {round(aliquota_efetiva * 100, 2)}%"
    formula_puro = f"R$ {dados.faturamento_mes:,.2f} * {round(aliquota_efetiva * 100, 2)}% = R$ {round(das_puro, 2):,.2f}"
    formula_reduzido = f"Guia DAS Reduzida: R$ {das_reduzido:,.2f}"
    formula_iva = f"Alíquota Aplicada: {round(aliquota_base_iva*100,2)}% | Débito: R$ {iva_debito:,.2f} | Crédito Amplo Acumulado: R$ {iva_credito:,.2f} | A pagar por fora: R$ {iva_a_pagar:,.2f}"

    return {
        "financeiro": {
            "anexo_utilizado": anexo_calculo.replace("_Regulamentado", " (Profissão Regulamentada - 30% desconto no IVA)"),
            "simples_puro_total": round(das_puro, 2),
            "simples_hibrido_das_reduzido": round(das_reduzido, 2),
            "simples_hibrido_iva_pagar": round(iva_a_pagar, 2),
            "simples_hibrido_total": round(total_hibrido, 2)
        },
        "comercial": {"veredito": veredito, "justificativa": justificativa},
        "memoria_calculo": {
            "fator_r": memoria_fator_r, "aliquota_efetiva": formula_efetiva,
            "simples_puro": formula_puro, "simples_reduzido": formula_reduzido, "iva_por_fora": formula_iva
        }
    }
