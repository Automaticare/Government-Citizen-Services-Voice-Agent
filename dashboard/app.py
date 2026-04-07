"""
Streamlit Analytics Dashboard for Citizen Services Voice Agent.

Tab-based layout:
1. Overview — KPIs, call volume, resolution
2. Intents & Performance — intent distribution, response times, node timing
3. Auth & Language — authentication metrics, language breakdown
4. Knowledge Gaps — RAG score analysis, low-score queries
5. Conversation Flows — node transition visualization (placeholder)
6. System Health — anomaly detection, thresholds
7. AI Insights — LLM-powered recommendations
8. Logs — recent conversations table

Run:
    python -m streamlit run dashboard/app.py
"""

import os
import sys
from datetime import datetime, timedelta

import pandas as pd
import streamlit as st
from sqlalchemy import create_engine

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


# --- Pre-compute shared metrics ---
total_requests = len(df)
unique_conversations = df["conversation_id"].nunique()
avg_response_ms = df["response_time_ms"].mean() if df["response_time_ms"].notna().any() else 0
escalated = (df["intent"] == "escalate").sum()
resolved = total_requests - escalated
resolution_rate = resolved / max(1, total_requests) * 100
escalation_rate = escalated / max(1, total_requests) * 100


# --- Tabs ---
tab_overview, tab_intents, tab_auth, tab_knowledge, tab_flows, tab_health, tab_insights, tab_logs = st.tabs([
    "Overview",
    "Intents & Performance",
    "Auth & Language",
    "Knowledge Gaps",
    "Conversation Flows",
    "System Health",
    "AI Insights",
    "Logs",
])


# =====================================================
# TAB 1: OVERVIEW
# =====================================================
with tab_overview:
    # KPIs
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Total Requests", total_requests)
    col2.metric("Conversations", unique_conversations)
    col3.metric("Avg Response", f"{avg_response_ms:.0f}ms")
    col4.metric("Resolution Rate", f"{resolution_rate:.0f}%")
    col5.metric("Escalation Rate", f"{escalation_rate:.1f}%")

    st.divider()

    # Call volume + turns
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Requests Over Time")
        df_vol = df.copy()
        df_vol["hour"] = df_vol["timestamp"].dt.floor("h")
        volume = df_vol.groupby("hour").size().reset_index(name="requests")
        st.line_chart(volume, x="hour", y="requests")

    with col2:
        st.subheader("Turns Per Conversation")
        turns = df.groupby("conversation_id")["message_count"].max().reset_index()
        turns.columns = ["conversation_id", "turns"]
        avg_turns = turns["turns"].mean()
        st.metric("Average Turns", f"{avg_turns:.1f}")
        st.bar_chart(turns["turns"].value_counts().sort_index())

    st.divider()

    # Resolution breakdown
    st.subheader("Resolution Breakdown")
    col1, col2 = st.columns(2)

    with col1:
        col_a, col_b = st.columns(2)
        col_a.metric("Resolved by Agent", resolved)
        col_b.metric("Escalated to Human", escalated)

    with col2:
        if escalated > 0:
            st.caption("Intents before escalation")
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
# TAB 2: INTENTS & PERFORMANCE
# =====================================================
with tab_intents:
    # Intent distribution + table side by side
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Intent Distribution")
        intent_counts = df["intent"].value_counts()
        if not intent_counts.empty:
            st.bar_chart(intent_counts)

    with col2:
        st.subheader("Intent Summary")
        intent_table = df.groupby("intent").agg(
            count=("intent", "size"),
            avg_response_ms=("response_time_ms", "mean"),
        ).reset_index()
        intent_table["avg_response_ms"] = intent_table["avg_response_ms"].round(0).astype(int)
        intent_table.columns = ["Intent", "Count", "Avg Response (ms)"]
        st.dataframe(intent_table, hide_index=True, use_container_width=True)

    st.divider()

    # Response time overview
    st.subheader("Response Time")

    if df["response_time_ms"].notna().any():
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Min", f"{df['response_time_ms'].min():.0f}ms")
        col2.metric("P50", f"{df['response_time_ms'].median():.0f}ms")
        col3.metric("P95", f"{df['response_time_ms'].quantile(0.95):.0f}ms")
        col4.metric("Max", f"{df['response_time_ms'].max():.0f}ms")

        df_perf = df.copy()
        df_perf["minute"] = df_perf["timestamp"].dt.floor("min")
        perf_trend = df_perf.groupby("minute")["response_time_ms"].mean().reset_index()
        perf_trend.columns = ["time", "response_ms"]
        st.line_chart(perf_trend, x="time", y="response_ms")

    st.divider()

    # Node-level timing
    st.subheader("Node-Level Timing")

    if "intent_classify_ms" in df.columns and df["intent_classify_ms"].notna().any():
        col1, col2 = st.columns(2)

        with col1:
            st.caption("Intent Classification")
            classify_df = df[df["intent_classify_ms"].notna()]
            col_a, col_b = st.columns(2)
            col_a.metric("Avg", f"{classify_df['intent_classify_ms'].mean():.0f}ms")
            col_b.metric("P95", f"{classify_df['intent_classify_ms'].quantile(0.95):.0f}ms")

        with col2:
            st.caption("Service Node (Total - Classify)")
            both = df[(df["response_time_ms"].notna()) & (df["intent_classify_ms"].notna())].copy()
            if not both.empty:
                both["service_ms"] = both["response_time_ms"] - both["intent_classify_ms"]
                col_a, col_b = st.columns(2)
                col_a.metric("Avg", f"{both['service_ms'].mean():.0f}ms")
                col_b.metric("P95", f"{both['service_ms'].quantile(0.95):.0f}ms")

        # Per-intent breakdown table
        timing_df = df[df["intent_classify_ms"].notna()].copy()
        if not timing_df.empty:
            timing_df["service_ms"] = timing_df["response_time_ms"] - timing_df["intent_classify_ms"]
            breakdown = timing_df.groupby("intent").agg(
                classify_ms=("intent_classify_ms", "mean"),
                service_ms=("service_ms", "mean"),
                total_ms=("response_time_ms", "mean"),
            ).round(0).astype(int).reset_index()
            breakdown.columns = ["Intent", "Classify (ms)", "Service (ms)", "Total (ms)"]
            st.dataframe(breakdown, hide_index=True, use_container_width=True)
    else:
        st.info("No node-level timing data yet.")


# =====================================================
# TAB 3: AUTH & LANGUAGE
# =====================================================
with tab_auth:
    # Auth KPIs
    st.subheader("Authentication")

    auth_count = (df["auth_status"] == "authenticated").sum()
    unauth_count = (df["auth_status"] == "unauthenticated").sum()

    col1, col2, col3 = st.columns(3)
    col1.metric("Authenticated Requests", auth_count)
    col2.metric("Unauthenticated Requests", unauth_count)

    if not auth_df.empty:
        auth_df["timestamp"] = pd.to_datetime(auth_df["timestamp"])
        success_count = (auth_df["result"] == "success").sum()
        failure_count = (auth_df["result"] == "failure").sum()
        col3.metric("Auth Success Rate", f"{success_count / max(1, success_count + failure_count) * 100:.0f}%")

        col1, col2 = st.columns(2)

        with col1:
            st.caption("Failure Reasons")
            failures = auth_df[auth_df["result"] == "failure"]
            if not failures.empty:
                st.bar_chart(failures["failure_reason"].value_counts())
            else:
                st.success("No auth failures")

        with col2:
            st.caption("Auth Methods")
            method_counts = auth_df["method"].value_counts()
            if not method_counts.empty:
                st.bar_chart(method_counts)
    else:
        col3.metric("Auth Success Rate", "N/A")

    st.divider()

    # Language
    st.subheader("Language")

    col1, col2 = st.columns(2)

    with col1:
        lang_counts = df["language"].value_counts()
        st.bar_chart(lang_counts)

    with col2:
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
# TAB 4: KNOWLEDGE GAPS
# =====================================================
with tab_knowledge:
    rag_df = df[df["rag_query"].notna() & (df["rag_query"] != "")]

    if not rag_df.empty:
        col1, col2, col3 = st.columns(3)
        avg_rag = rag_df["rag_score"].mean()
        low_score = rag_df[rag_df["rag_score"] < 0.4]
        high_score = rag_df[rag_df["rag_score"] >= 0.7]

        col1.metric("Total RAG Queries", len(rag_df))
        col2.metric("Avg Score", f"{avg_rag:.2f}")
        col3.metric("Low Score (<0.4)", len(low_score))

        st.divider()

        col1, col2 = st.columns(2)

        with col1:
            st.subheader("Score Distribution")
            if rag_df["rag_score"].notna().any():
                st.bar_chart(rag_df["rag_score"].dropna())

        with col2:
            st.subheader("Knowledge Gaps")
            if not low_score.empty:
                gaps = low_score[["rag_query", "rag_score"]].sort_values("rag_score")
                gaps.columns = ["Query", "Score"]
                st.dataframe(gaps, hide_index=True, use_container_width=True)
                st.caption("Consider adding more content to the knowledge base for these topics.")
            else:
                st.success("No knowledge gaps — all queries scored above 0.4")
    else:
        st.info("No RAG queries logged yet. FAQ conversations will populate this section.")


# =====================================================
# TAB 5: CONVERSATION FLOWS (placeholder for ISSUE-40)
# =====================================================
with tab_flows:
    st.subheader("Conversation Flow Visualization")
    st.info("Coming soon — node transition diagrams showing common conversation paths, drop-off points, and bottlenecks.")

    # Show basic workflow node distribution as interim
    node_counts = df[df["workflow_node"] != ""]["workflow_node"].value_counts()
    if not node_counts.empty:
        st.subheader("Workflow Node Distribution")
        st.bar_chart(node_counts)
    else:
        st.caption("No workflow node data yet.")


# =====================================================
# TAB 6: SYSTEM HEALTH
# =====================================================
with tab_health:
    anomalies = []

    # 1. Escalation rate (threshold: 20%)
    if escalation_rate > 20:
        anomalies.append(("🔴", "High Escalation Rate", f"{escalation_rate:.1f}% (threshold: 20%)"))
    elif escalation_rate > 10:
        anomalies.append(("🟡", "Elevated Escalation Rate", f"{escalation_rate:.1f}% (threshold: 20%)"))

    # 2. Response time (threshold: 3000ms)
    if df["response_time_ms"].notna().any():
        avg_resp = df["response_time_ms"].mean()
        if avg_resp > 3000:
            anomalies.append(("🔴", "High Response Latency", f"{avg_resp:.0f}ms avg (threshold: 3000ms)"))
        elif avg_resp > 2000:
            anomalies.append(("🟡", "Elevated Response Latency", f"{avg_resp:.0f}ms avg (threshold: 3000ms)"))

    # 3. Auth failure rate (threshold: 30%)
    auth_fail_rate = 0
    if not auth_df.empty:
        total_auth = len(auth_df)
        auth_failures = (auth_df["result"] == "failure").sum()
        auth_fail_rate = auth_failures / max(1, total_auth) * 100
        if auth_fail_rate > 30:
            anomalies.append(("🔴", "High Auth Failure Rate", f"{auth_fail_rate:.0f}% ({auth_failures}/{total_auth})"))
        elif auth_fail_rate > 15:
            anomalies.append(("🟡", "Elevated Auth Failure Rate", f"{auth_fail_rate:.0f}% ({auth_failures}/{total_auth})"))

    # 4. Resolution rate (threshold: 70%)
    if resolution_rate < 70:
        anomalies.append(("🔴", "Low Resolution Rate", f"{resolution_rate:.0f}% (threshold: 70%)"))
    elif resolution_rate < 85:
        anomalies.append(("🟡", "Below Target Resolution", f"{resolution_rate:.0f}% (threshold: 85%)"))

    # 5. Volume anomaly
    df_hourly = df.copy()
    df_hourly["hour"] = df_hourly["timestamp"].dt.floor("h")
    hourly_counts = df_hourly.groupby("hour").size()
    if len(hourly_counts) > 2:
        avg_hourly = hourly_counts.mean()
        last_hour = hourly_counts.iloc[0] if len(hourly_counts) > 0 else 0
        if last_hour > avg_hourly * 2:
            anomalies.append(("🟡", "Volume Spike", f"Last hour: {last_hour} (avg: {avg_hourly:.0f})"))
        elif last_hour < avg_hourly * 0.3 and avg_hourly > 3:
            anomalies.append(("🟡", "Volume Drop", f"Last hour: {last_hour} (avg: {avg_hourly:.0f})"))

    # Display
    if not anomalies:
        st.success("All systems healthy — no anomalies detected")
    else:
        for icon, title, detail in anomalies:
            st.warning(f"{icon} **{title}** — {detail}")

    st.divider()

    # Health summary
    st.subheader("Thresholds")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Escalation Rate", f"{escalation_rate:.1f}%")
    col2.metric("Avg Response", f"{avg_response_ms:.0f}ms")
    col3.metric("Auth Fail Rate", f"{auth_fail_rate:.0f}%" if not auth_df.empty else "N/A")
    col4.metric("Resolution Rate", f"{resolution_rate:.0f}%")


# =====================================================
# TAB 7: AI INSIGHTS
# =====================================================
with tab_insights:
    st.caption("Powered by GPT-4o + ElevenLabs documentation RAG")

    if st.button("Generate Insights"):
        with st.spinner("Analyzing metrics and platform documentation..."):
            from dashboard.insights import generate_insights
            insights = generate_insights(df, auth_df)

        if insights:
            for insight in insights:
                priority = insight.get("priority", "low")
                icon = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(priority, "ℹ️")
                itype = insight.get("type", "")
                title = insight.get("title", "")
                detail = insight.get("detail", "")
                st.info(f"{icon} **[{itype.upper()}] {title}**\n\n{detail}")
        else:
            st.success("No recommendations at this time.")

    st.divider()
    st.caption("Note: Insight quality improves with more conversation data. Current recommendations may be generic with limited data volume.")


# =====================================================
# TAB 8: LOGS
# =====================================================
with tab_logs:
    st.subheader("Recent Conversations")
    recent = df.head(50)[["timestamp", "conversation_id", "intent", "workflow_node", "auth_status", "language", "message_count", "response_time_ms"]]
    st.dataframe(recent, hide_index=True, use_container_width=True)
