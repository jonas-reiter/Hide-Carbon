import os
import re
import pandas as pd
import streamlit as st
import plotly.express as px
from dotenv import load_dotenv
from groq import Groq
from sqlalchemy import create_engine, text


load_dotenv()

st.set_page_config(
    page_title="Assistente SQL com Groq",
    layout="wide"
)


# =========================
# CONEXÃO COM BANCO
# =========================

def criar_engine():   
    database_url = os.getenv("DATABASE_URL")
 
    if not database_url:
        raise ValueError("DATABASE_URL não encontrada no .env")

    return create_engine(database_url)


# =========================
# GROQ
# =========================

def gerar_sql(modelagem, pergunta):
    client = Groq(api_key=os.getenv("GROQ_API_KEY"))

    prompt = f"""
Você é um especialista em SQL PostgreSQL.

Com base na modelagem abaixo, gere APENAS uma consulta SQL SELECT.
Não explique nada.
Não use markdown.
Não use ```sql.
Não gere INSERT, UPDATE, DELETE, DROP, ALTER ou TRUNCATE.

MODELAGEM DO BANCO:
{modelagem}

PERGUNTA DO USUÁRIO:
{pergunta}

Não esqueça dos detalhes específicos da linguagem POSTGRESQL, como aspas duplas para nomes de tabelas e colunas.
"""

    resposta = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {
                "role": "system",
                "content": "Você gera apenas SQL seguro para consulta em banco MySQL."
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        temperature=0
    )

    sql = resposta.choices[0].message.content.strip()
    sql = limpar_sql(sql)

    return sql


def limpar_sql(sql):
    sql = sql.replace("```sql", "").replace("```", "").strip()
    return sql


def validar_sql(sql):
    sql_limpo = sql.strip().lower()

    comandos_bloqueados = [
        "insert", "update", "delete", "drop", "alter",
        "truncate", "create", "replace", "grant", "revoke"
    ]

    if not sql_limpo.startswith("select"):
        return False, "A consulta precisa começar com SELECT."

    for comando in comandos_bloqueados:
        if re.search(rf"\b{comando}\b", sql_limpo):
            return False, f"Comando bloqueado encontrado: {comando.upper()}"

    return True, "SQL válido."


# =========================
# EXECUÇÃO SQL
# =========================

def executar_sql(sql):
    engine = criar_engine()

    with engine.connect() as conn:
        df = pd.read_sql(text(sql), conn)

    return df

def gerar_codigo_grafico_com_ia(df):
    client = Groq(api_key=os.getenv("GROQ_API_KEY"))

    colunas = [
        {
            "nome": col,
            "tipo": str(df[col].dtype)
        }
        for col in df.columns
    ]

    amostra = df.head(20).to_dict(orient="records")

    prompt = f"""
Você é um especialista em visualização de dados com Python, Pandas, Plotly Express e Streamlit.

Com base nas colunas e na amostra do DataFrame, gere um código Python para exibir o melhor gráfico possível no Streamlit.

IMPORTANTE:
- O DataFrame já existe e se chama df.
- O Streamlit já está importado como st.
- O Pandas já está importado como pd.
- O Plotly Express já está importado como px.
- Gere APENAS código Python.
- Não use markdown.
- Não use ```python.
- Não importe bibliotecas.
- Não crie dados fictícios.
- Não altere o banco de dados.
- Não use input().
- Não use print().
- O código deve exibir o gráfico usando st.plotly_chart(..., use_container_width=True).
- Antes do gráfico, use st.subheader com um título adequado.
- Use apenas colunas existentes no DataFrame.
- Se houver coluna de data, converta com pd.to_datetime quando necessário.
- Se for comparação entre categorias, use gráfico de barras.
- Se for evolução temporal, use gráfico de linha.
- Se for composição de total, use gráfico de pizza.
- Se houver muitas categorias, use apenas o top 10.

COLUNAS DO DATAFRAME:
{colunas}

AMOSTRA DOS DADOS:
{amostra}
"""

    resposta = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {
                "role": "system",
                "content": "Você gera apenas código Python seguro para gráficos em Streamlit usando Plotly Express."
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        temperature=0
    )

    codigo = resposta.choices[0].message.content.strip()
    codigo = codigo.replace("```python", "").replace("```", "").strip()

    return codigo

# =========================
# INTERFACE
# =========================

st.title("Assistente SQL com Groq + Streamlit")

if "sql_gerado" not in st.session_state:
    st.session_state.sql_gerado = ""

tab1, tab2, tab3 = st.tabs(["Gerar SQL", "Executar SQL", "Gerar Gráfico"])

with tab1:
    st.subheader("1. Informe a modelagem do banco")

    modelagem = '''
    CREATE TABLE "produtos" (
  "id" INT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
  "nomeProduto" VARCHAR(255) NOT NULL,
  "codigoBarras" VARCHAR(13) NOT NULL,
  "categoriaId" int NOT NULL
);

CREATE TABLE "categorias" (
  "id" INT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
  "nomeCategoria" VARCHAR(255) NOT NULL
);

CREATE TABLE "vendas" (
  "id" INT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
  "dataHora" TIMESTAMP DEFAULT (NOW()),
  "quantidade" int NOT NULL,
  "produtoId" INT NOT NULL
);

ALTER TABLE "produtos" ADD FOREIGN KEY ("categoriaId") REFERENCES "categorias" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "vendas" ADD FOREIGN KEY ("produtoId") REFERENCES "produtos" ("id") DEFERRABLE INITIALLY IMMEDIATE;
'''

    pergunta = st.text_area(
        "O que você quer consultar?",
        height=120,
        placeholder="Exemplo: Quero o total vendido por produto no mês de julho."
    )

    if st.button("Gerar SQL"):
        if not modelagem or not pergunta:
            st.warning("Informe a modelagem e a pergunta.")
        else:
            with st.spinner("Gerando SQL com Groq..."):
                sql = gerar_sql(modelagem, pergunta)
                valido, mensagem = validar_sql(sql)

                if valido:
                    st.session_state.sql_gerado = sql
                    st.success("SQL gerado com sucesso.")
                    st.code(sql, language="sql")
                else:
                    st.error(mensagem)
                    st.code(sql, language="sql")


with tab2:
    st.subheader("2. Executar SQL e visualizar resultado")

    sql_editavel = st.text_area(
        "SQL para execução",
        value=st.session_state.sql_gerado,
        height=250
    )

    if st.button("Executar consulta"):
        valido, mensagem = validar_sql(sql_editavel)

        if not valido:
            st.error(mensagem)
        else:
            try:
                with st.spinner("Executando consulta..."):
                    df = executar_sql(sql_editavel)

                st.success(f"Consulta executada. {len(df)} registros encontrados.")
                st.dataframe(df, use_container_width=True)

                csv = df.to_csv(index=False).encode("utf-8")

                st.download_button(
                    label="Baixar CSV",
                    data=csv,
                    file_name="resultado_consulta.csv",
                    mime="text/csv"
                )
                st.session_state.df_resultado = df

            except Exception as e:
                st.error("Erro ao executar SQL.")
                st.exception(e)
                
with tab3:
    st.subheader("3. Gerar gráfico com IA")

    if "df_resultado" not in st.session_state:
        st.warning("Nenhum DataFrame encontrado. Execute uma consulta primeiro.")
    else:
        df = st.session_state.df_resultado

        st.write("DataFrame base:")
        st.dataframe(df, use_container_width=True)

        if "codigo_grafico_ia" not in st.session_state:
            st.session_state.codigo_grafico_ia = ""

        if st.button("Gerar código do gráfico com IA"):
            with st.spinner("Gerando código do gráfico com Groq..."):
                st.session_state.codigo_grafico_ia = gerar_codigo_grafico_com_ia(df)

        codigo_editavel = st.text_area(
            "Código Python do gráfico",
            value=st.session_state.codigo_grafico_ia,
            height=300
        )

        if st.button("Executar gráfico"):
            try:
                ambiente_seguro = {
                    "st": st,
                    "pd": pd,
                    "px": px,
                    "df": df
                }

                exec(codigo_editavel, ambiente_seguro)

            except Exception as e:
                st.error("Erro ao executar o código do gráfico.")
                st.exception(e)