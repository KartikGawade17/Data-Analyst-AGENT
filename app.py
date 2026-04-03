# Streamlit UI For SQL Agent Project

import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt

from sqlalchemy import create_engine
from langchain_ollama import ChatOllama
from langgraph.graph import StateGraph, END
from typing import TypedDict

# -----------------------------
# Database Connection
# -----------------------------

username = "root"
password = "jessepinkman"
host = "localhost"
database = "company_db"

engine = create_engine(
    f"mysql+pymysql://{username}:{password}@{host}/{database}"
)

# -----------------------------
# LLM
# -----------------------------

llm = ChatOllama(model="llama3")

# -----------------------------
# Database Schema
# -----------------------------

schema = """
Table: employees
Columns: employee_id, employee_name, age, gender, department_id, salary, joining_date, city

Table: departments
Columns: department_id, department_name

Table: customers
Columns: customer_id, customer_name, gender, age, city, phone_number, email, registration_date

Table: products
Columns: product_id, product_name, category, brand, price, stock_quantity

Table: orders
Columns: order_id, customer_id, product_id, employee_id, quantity, order_amount, order_date, payment_method, order_status

Table: sales
Columns: sale_id, employee_id, product_name, sale_amount, sale_date, region
"""

# -----------------------------
# LangGraph State
# -----------------------------

class AgentState(TypedDict):
    user_question: str
    generated_sql: str
    dataframe: pd.DataFrame
    needs_chart: str

# -----------------------------
# Node 1 - Generate SQL
# -----------------------------

def generate_sql(state: AgentState):

    user_question = state.get("user_question", "")

    prompt = f"""
    You are an expert MySQL query generator.

    Database Schema:
    {schema}

    User Question:
    {user_question}

    Important Rules:
    1. Return exactly ONE MySQL query
    2. Do not explain anything
    3. Do not return markdown
    4. Use only the provided tables and columns
    5. Use LIMIT 10 when appropriate
    """

    response = llm.invoke(prompt)

    generated_sql = response.content.strip()

    generated_sql = generated_sql.replace("```sql", "")
    generated_sql = generated_sql.replace("```", "")
    generated_sql = generated_sql.strip()

    generated_sql = generated_sql.split(";")[0] + ";"

    state["generated_sql"] = generated_sql

    return state

# -----------------------------
# Node 2 - Execute SQL
# -----------------------------

def execute_sql(state: AgentState):

    generated_sql = state.get("generated_sql", "")

    df = pd.read_sql(generated_sql, engine)

    state["dataframe"] = df

    return state

# -----------------------------
# Node 3 - Decide Chart
# -----------------------------

def decide_chart(state: AgentState):

    user_question = state.get("user_question", "")
    df = state.get("dataframe", pd.DataFrame())

    chart_prompt = f"""
    User Question: {user_question}

    Data Columns: {list(df.columns)}

    Should this result be shown as a chart?

    Only answer YES or NO.
    """

    response = llm.invoke(chart_prompt)

    needs_chart = response.content.strip().upper()

    state["needs_chart"] = needs_chart

    return state

# -----------------------------
# Build Workflow
# -----------------------------

workflow = StateGraph(AgentState)

workflow.add_node("generate_sql", generate_sql)
workflow.add_node("execute_sql", execute_sql)
workflow.add_node("decide_chart", decide_chart)

workflow.set_entry_point("generate_sql")
workflow.add_edge("generate_sql", "execute_sql")
workflow.add_edge("execute_sql", "decide_chart")
workflow.add_edge("decide_chart", END)

app_graph = workflow.compile()

# -----------------------------
# Streamlit UI
# -----------------------------

st.set_page_config(page_title="SQL AI Agent", layout="wide")

st.title("SQL Data Analyst Agent")
st.write("Ask questions about your company database using natural language")

st.sidebar.header("Available Tables")

with st.sidebar.expander("employees"):
    st.write([
        "employee_id",
        "employee_name",
        "age",
        "gender",
        "department_id",
        "salary",
        "joining_date",
        "city"
    ])

with st.sidebar.expander("departments"):
    st.write([
        "department_id",
        "department_name"
    ])

with st.sidebar.expander("customers"):
    st.write([
        "customer_id",
        "customer_name",
        "city",
        "gender", "age", 
        "phone_number", 
        "email", 
        "registration_date"
    ])

with st.sidebar.expander("products"):
    st.write([
        "product_id",
        "product_name",
        "category",
        "price",
        "brand",
        "stock_quantity"
    ])

with st.sidebar.expander("orders"):
    st.write([
        "order_id",
        "customer_id",
        "product_id",
        "employee_id",
        "quantity",
        "order_amount",
        "order_date",
        "payment_method",
        "order_status"
    ])

with st.sidebar.expander("sales"):
    st.write([
        "sale_id",
        "employee_id",
        "product_name",
        "sale_amount",
        "sale_date",
        "region"
    ])

user_question = st.text_input(
    "Enter your question",
    placeholder="Example: Show top 5 employees with highest salary"
)

if st.button("Run Query"):

    if user_question:

        initial_state = {
            "user_question": user_question,
            "generated_sql": "",
            "dataframe": pd.DataFrame(),
            "needs_chart": ""
        }

        result = app_graph.invoke(initial_state)

        generated_sql = result["generated_sql"]
        df = result["dataframe"]
        needs_chart = result["needs_chart"]

        st.subheader("Generated SQL")
        st.code(generated_sql, language="sql")

        st.subheader("Result")
        st.dataframe(df)

        st.write(f"Chart Needed: {needs_chart}")

        if needs_chart == "YES" and len(df.columns) >= 2:

            try:
                x_column = df.columns[0]
                y_column = df.columns[1]

                df = df.head(10).copy()

                df[y_column] = pd.to_numeric(df[y_column], errors="coerce")
                df = df.dropna()

                if not df.empty:
                    fig, ax = plt.subplots(figsize=(8,5))
                    ax.bar(df[x_column].astype(str), df[y_column])
                    ax.set_title(user_question)
                    ax.set_xlabel(x_column)
                    ax.set_ylabel(y_column)
                    plt.xticks(rotation=30)
                    plt.tight_layout()

                    st.pyplot(fig)
                    plt.close(fig)
                else:
                    st.info("Chart could not be generated because numeric data was not available.")

            except Exception as e:
                st.error(f"Chart generation error: {e}")

    else:
        st.warning("Please enter a question")

