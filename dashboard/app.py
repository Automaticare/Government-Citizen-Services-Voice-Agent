"""
Streamlit Analytics Dashboard for Citizen Services Voice Agent.

Displays real-time metrics from conversation_logs table:
- Call volume and response times
- Intent distribution
- Authentication metrics
- Language analytics

Run:
    streamlit run dashboard/app.py
"""

import os
import sys
from datetime import datetime, timedelta

import pandas as pd
import streamlit as st
from sqlalchemy import create_engine, text

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///data/citizens.db")
engine = create_engine(DATABASE_URL)


def load_conversation_logs() -> pd.DataFrame:
    """Load conversation logs from database."""
    query = "SELECT * FROM conversation_logs ORDER BY timestamp DESC"
    try:
        return pd.read_sql(query, engine)
    except Exception:
        return pd.DataFrame()


def load_auth_audit_logs() -> pd.DataFrame:
    """Load auth audit logs from database."""
    query = "SELECT * FROM auth_audit_log ORDER BY timestamp DESC"
    try:
        return pd.read_sql(query, engine)
    except Exception:
        return pd.DataFrame()


# --- Page config ---
st.set_page_config(
    page_title="Citizen Services Analytics",
    page_icon="🏛️",
    layout="wide",
)

st.title("Citizen Services Voice Agent — Analytics")
st.caption("Real-time metrics from conversation logs")

# --- Sidebar ---
st.sidebar.header("Filters")

# Date range
date_range = st.sidebar.selectbox(
    "Date Range",
    ["Last 24 Hours", "Last 7 Days", "Last 30 Days", "All Time"],
    index=3,
)

# Load data
df = load_conversation_logs()
auth_df = load_auth_audit_logs()

if df.empty:
    st.warning("No conversation data yet. Start a conversation to see analytics.")
    st.stop()

# Parse timestamps
df["timestamp"] = pd.to_datetime(df["timestamp"])

# Apply date filter
now = datetime.utcnow()
if date_range == "Last 24 Hours":
    df = df[df["timestamp"] > now - timedelta(hours=24)]
elif date_range == "Last 7 Days":
    df = df[df["timestamp"] > now - timedelta(days=7)]
elif date_range == "Last 30 Days":
    df = df[df["timestamp"] > now - timedelta(days=30)]

if df.empty:
    st.info("No data for the selected date range.")
    st.stop()

# --- Overview Metrics ---
st.header("Overview")
col1, col2, col3, col4 = st.columns(4)

total_requests = len(df)
unique_conversations = df["conversation_id"].nunique()
avg_response_ms = df["response_time_ms"].mean() if "response_time_ms" in df.columns else 0
auth_rate = (df["auth_status"] == "authenticated").mean() * 100

col1.metric("Total Requests", total_requests)
col2.metric("Unique Conversations", unique_conversations)
col3.metric("Avg Response Time", f"{avg_response_ms:.0f}ms")
col4.metric("Auth Rate", f"{auth_rate:.0f}%")

# --- Call Volume Over Time ---
st.header("Call Volume")
df["hour"] = df["timestamp"].dt.floor("h")
volume = df.groupby("hour").size().reset_index(name="requests")
st.line_chart(volume, x="hour", y="requests")

# --- Intent Distribution ---
st.header("Intent Distribution")
col1, col2 = st.columns(2)

with col1:
    intent_counts = df["intent"].value_counts()
    if not intent_counts.empty:
        st.bar_chart(intent_counts)
    else:
        st.info("No intent data")

with col2:
    st.dataframe(
        df["intent"].value_counts().reset_index().rename(
            columns={"index": "Intent", "intent": "Intent", "count": "Count"}
        ),
        hide_index=True,
    )

# --- Language Distribution ---
st.header("Language Analytics")
col1, col2 = st.columns(2)

with col1:
    lang_counts = df["language"].value_counts()
    st.bar_chart(lang_counts)

with col2:
    st.dataframe(
        df["language"].value_counts().reset_index().rename(
            columns={"language": "Language", "count": "Count"}
        ),
        hide_index=True,
    )

# --- Authentication Metrics ---
st.header("Authentication")
col1, col2, col3 = st.columns(3)

auth_count = (df["auth_status"] == "authenticated").sum()
unauth_count = (df["auth_status"] == "unauthenticated").sum()

col1.metric("Authenticated Requests", auth_count)
col2.metric("Unauthenticated Requests", unauth_count)

if not auth_df.empty:
    auth_df["timestamp"] = pd.to_datetime(auth_df["timestamp"])
    success_count = (auth_df["result"] == "success").sum()
    failure_count = (auth_df["result"] == "failure").sum()
    col3.metric("Auth Success Rate", f"{success_count / max(1, success_count + failure_count) * 100:.0f}%")

    st.subheader("Auth Failure Reasons")
    failures = auth_df[auth_df["result"] == "failure"]
    if not failures.empty:
        st.bar_chart(failures["failure_reason"].value_counts())

# --- Response Time Distribution ---
st.header("Performance")
if "response_time_ms" in df.columns and df["response_time_ms"].notna().any():
    st.subheader("Response Time Distribution")
    st.bar_chart(df["response_time_ms"].dropna().astype(int))

    col1, col2, col3 = st.columns(3)
    col1.metric("Min", f"{df['response_time_ms'].min():.0f}ms")
    col2.metric("Median", f"{df['response_time_ms'].median():.0f}ms")
    col3.metric("Max", f"{df['response_time_ms'].max():.0f}ms")

# --- Workflow Node Distribution ---
st.header("Workflow Nodes")
node_counts = df[df["workflow_node"] != ""]["workflow_node"].value_counts()
if not node_counts.empty:
    st.bar_chart(node_counts)
else:
    st.info("No workflow node data yet")

# --- Recent Conversations ---
st.header("Recent Conversations")
recent = df.head(20)[["timestamp", "conversation_id", "intent", "workflow_node", "auth_status", "language", "response_time_ms"]]
st.dataframe(recent, hide_index=True, use_container_width=True)
