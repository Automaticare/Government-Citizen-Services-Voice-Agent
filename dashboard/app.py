"""
Streamlit Analytics Dashboard for Citizen Services Voice Agent.

Displays real-time metrics from conversation_logs and auth_audit_log tables:
- Overview KPIs
- Call volume and trends
- Resolution metrics
- Intent distribution and performance
- Authentication analytics
- Language analytics
- Performance metrics
- Workflow node distribution

Run:
    python -m streamlit run dashboard/app.py
"""

import os
import sys
from datetime import datetime, timedelta

import pandas as pd
import streamlit as st
from sqlalchemy import create_engine

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///data/citizens.db")
engine = create_engine(DATABASE_URL)


def load_conversation_logs() -> pd.DataFrame:
    """Load conversation logs from database."""
    try:
        return pd.read_sql("SELECT * FROM conversation_logs ORDER BY timestamp DESC", engine)
    except Exception:
        return pd.DataFrame()


def load_auth_audit_logs() -> pd.DataFrame:
    """Load auth audit logs from database."""
    try:
        return pd.read_sql("SELECT * FROM auth_audit_log ORDER BY timestamp DESC", engine)
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

date_range = st.sidebar.selectbox(
    "Date Range",
    ["Last 24 Hours", "Last 7 Days", "Last 30 Days", "All Time"],
    index=3,
)

auto_refresh = st.sidebar.checkbox("Auto-refresh (30s)", value=False)
if auto_refresh:
    st.rerun()

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


# =====================================================
# OVERVIEW KPIs
# =====================================================
st.header("Overview")
col1, col2, col3, col4, col5 = st.columns(5)

total_requests = len(df)
unique_conversations = df["conversation_id"].nunique()
avg_response_ms = df["response_time_ms"].mean() if df["response_time_ms"].notna().any() else 0
auth_rate = (df["auth_status"] == "authenticated").mean() * 100

# Resolution rate: requests that did NOT escalate
escalated = (df["intent"] == "escalate").sum()
resolved = total_requests - escalated
resolution_rate = resolved / max(1, total_requests) * 100

col1.metric("Total Requests", total_requests)
col2.metric("Unique Conversations", unique_conversations)
col3.metric("Avg Response", f"{avg_response_ms:.0f}ms")
col4.metric("Resolution Rate", f"{resolution_rate:.0f}%")
col5.metric("Auth Rate", f"{auth_rate:.0f}%")


# =====================================================
# CALL VOLUME & TRENDS
# =====================================================
st.header("Call Volume & Trends")

col1, col2 = st.columns(2)

with col1:
    st.subheader("Requests Over Time")
    df["hour"] = df["timestamp"].dt.floor("h")
    volume = df.groupby("hour").size().reset_index(name="requests")
    st.line_chart(volume, x="hour", y="requests")

with col2:
    st.subheader("Avg Turns Per Conversation")
    turns = df.groupby("conversation_id")["message_count"].max().reset_index()
    turns.columns = ["conversation_id", "turns"]
    avg_turns = turns["turns"].mean()
    st.metric("Average Turns", f"{avg_turns:.1f}")
    st.bar_chart(turns["turns"].value_counts().sort_index())


# =====================================================
# RESOLUTION METRICS
# =====================================================
st.header("Resolution Metrics")

col1, col2, col3 = st.columns(3)

col1.metric("Resolved by Agent", resolved)
col2.metric("Escalated to Human", escalated)
col3.metric("Escalation Rate", f"{escalated / max(1, total_requests) * 100:.1f}%")

# Resolution by intent
st.subheader("Escalation by Context")
if escalated > 0:
    # Look at what happened before escalation in each conversation
    escalated_convs = df[df["intent"] == "escalate"]["conversation_id"].unique()
    pre_escalation = df[
        (df["conversation_id"].isin(escalated_convs)) &
        (df["intent"] != "escalate")
    ]
    if not pre_escalation.empty:
        st.bar_chart(pre_escalation["intent"].value_counts())
    else:
        st.info("Direct escalation — no prior intent")
else:
    st.success("No escalations in this period")


# =====================================================
# INTENT DISTRIBUTION & PERFORMANCE
# =====================================================
st.header("Intent Analytics")

col1, col2 = st.columns(2)

with col1:
    st.subheader("Intent Distribution")
    intent_counts = df["intent"].value_counts()
    if not intent_counts.empty:
        st.bar_chart(intent_counts)

with col2:
    st.subheader("Intent Table")
    intent_table = df.groupby("intent").agg(
        count=("intent", "size"),
        avg_response_ms=("response_time_ms", "mean"),
    ).reset_index()
    intent_table["avg_response_ms"] = intent_table["avg_response_ms"].round(0).astype(int)
    intent_table.columns = ["Intent", "Count", "Avg Response (ms)"]
    st.dataframe(intent_table, hide_index=True, use_container_width=True)

# Response time by intent
st.subheader("Response Time by Intent")
intent_response = df.groupby("intent")["response_time_ms"].mean().dropna().sort_values(ascending=False)
if not intent_response.empty:
    st.bar_chart(intent_response)


# =====================================================
# LANGUAGE ANALYTICS
# =====================================================
st.header("Language Analytics")

col1, col2 = st.columns(2)

with col1:
    st.subheader("Language Distribution")
    lang_counts = df["language"].value_counts()
    st.bar_chart(lang_counts)

with col2:
    st.subheader("Language Table")
    lang_table = df.groupby("language").agg(
        count=("language", "size"),
        auth_rate=("auth_status", lambda x: (x == "authenticated").mean() * 100),
        avg_response_ms=("response_time_ms", "mean"),
    ).reset_index()
    lang_table["auth_rate"] = lang_table["auth_rate"].round(0).astype(int)
    lang_table["avg_response_ms"] = lang_table["avg_response_ms"].round(0).astype(int)
    lang_table.columns = ["Language", "Requests", "Auth Rate (%)", "Avg Response (ms)"]
    st.dataframe(lang_table, hide_index=True, use_container_width=True)


# =====================================================
# AUTHENTICATION METRICS
# =====================================================
st.header("Authentication Analytics")

col1, col2, col3 = st.columns(3)

auth_count = (df["auth_status"] == "authenticated").sum()
unauth_count = (df["auth_status"] == "unauthenticated").sum()

col1.metric("Authenticated", auth_count)
col2.metric("Unauthenticated", unauth_count)

if not auth_df.empty:
    auth_df["timestamp"] = pd.to_datetime(auth_df["timestamp"])
    success_count = (auth_df["result"] == "success").sum()
    failure_count = (auth_df["result"] == "failure").sum()
    col3.metric("Auth Success Rate", f"{success_count / max(1, success_count + failure_count) * 100:.0f}%")

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Auth Failure Reasons")
        failures = auth_df[auth_df["result"] == "failure"]
        if not failures.empty:
            st.bar_chart(failures["failure_reason"].value_counts())
        else:
            st.success("No auth failures")

    with col2:
        st.subheader("Auth Method Distribution")
        method_counts = auth_df["method"].value_counts()
        if not method_counts.empty:
            st.bar_chart(method_counts)


# =====================================================
# PERFORMANCE METRICS
# =====================================================
st.header("Performance")

if df["response_time_ms"].notna().any():
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Min", f"{df['response_time_ms'].min():.0f}ms")
    col2.metric("P50", f"{df['response_time_ms'].median():.0f}ms")
    col3.metric("P95", f"{df['response_time_ms'].quantile(0.95):.0f}ms")
    col4.metric("Max", f"{df['response_time_ms'].max():.0f}ms")

    st.subheader("Response Time Trend")
    df["minute"] = df["timestamp"].dt.floor("min")
    perf_trend = df.groupby("minute")["response_time_ms"].mean().reset_index()
    perf_trend.columns = ["time", "response_ms"]
    st.line_chart(perf_trend, x="time", y="response_ms")


# =====================================================
# WORKFLOW NODE DISTRIBUTION
# =====================================================
st.header("Workflow Nodes")
node_counts = df[df["workflow_node"] != ""]["workflow_node"].value_counts()
if not node_counts.empty:
    st.bar_chart(node_counts)
else:
    st.info("No workflow node data yet")


# =====================================================
# RECENT CONVERSATIONS
# =====================================================
st.header("Recent Conversations")
recent = df.head(30)[["timestamp", "conversation_id", "intent", "workflow_node", "auth_status", "language", "message_count", "response_time_ms"]]
st.dataframe(recent, hide_index=True, use_container_width=True)
