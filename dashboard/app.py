"""
Streamlit Analytics Dashboard for Citizen Services Voice Agent.

Multi-page layout with sidebar navigation:
1. Overview — KPIs, call volume, resolution
2. Intents & Performance — intent distribution, response times, node timing
3. Auth & Language — authentication metrics, language breakdown
4. Knowledge Gaps — RAG score analysis, low-score queries
5. Conversation Flows — Sankey diagram, common paths, entry/exit points
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

st.set_page_config(
    page_title="Citizen Services Analytics",
    page_icon="🏛️",
    layout="wide",
)

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///data/citizens.db")
engine = create_engine(DATABASE_URL)


# --- Data loading (cached, shared across pages) ---

@st.cache_data(ttl=30)
def load_conversation_logs() -> pd.DataFrame:
    try:
        return pd.read_sql("SELECT * FROM conversation_logs ORDER BY timestamp DESC", engine)
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=30)
def load_auth_audit_logs() -> pd.DataFrame:
    try:
        return pd.read_sql("SELECT * FROM auth_audit_log ORDER BY timestamp DESC", engine)
    except Exception:
        return pd.DataFrame()


def get_filtered_data():
    """Load and filter data based on sidebar date range. Returns (df, auth_df) or stops."""
    df = load_conversation_logs()
    auth_df = load_auth_audit_logs()

    if df.empty:
        st.warning("No conversation data yet. Start a conversation to see analytics.")
        st.stop()

    df["timestamp"] = pd.to_datetime(df["timestamp"])

    date_range = st.session_state.get("date_range", "All Time")
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

    return df, auth_df


# =====================================================
# PAGE: OVERVIEW
# =====================================================
def page_overview():
    st.header("Overview")
    df, auth_df = get_filtered_data()

    total_requests = len(df)
    unique_conversations = df["conversation_id"].nunique()
    avg_response_ms = df["response_time_ms"].mean() if df["response_time_ms"].notna().any() else 0
    escalated = (df["intent"] == "escalate").sum()
    resolved = total_requests - escalated
    resolution_rate = resolved / max(1, total_requests) * 100
    escalation_rate = escalated / max(1, total_requests) * 100

    # KPIs
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Total Requests", total_requests)
    col2.metric("Conversations", unique_conversations)
    col3.metric("Avg Response", f"{avg_response_ms:.0f}ms")
    col4.metric("Resolution Rate", f"{resolution_rate:.0f}%")
    col5.metric("Escalation Rate", f"{escalation_rate:.1f}%")

    st.divider()

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
# PAGE: INTENTS & PERFORMANCE
# =====================================================
def page_intents():
    st.header("Intents & Performance")
    df, _ = get_filtered_data()

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
# PAGE: AUTH & LANGUAGE
# =====================================================
def page_auth():
    st.header("Auth & Language")
    df, auth_df = get_filtered_data()

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
# PAGE: KNOWLEDGE GAPS
# =====================================================
def page_knowledge():
    st.header("Knowledge Gaps")
    df, _ = get_filtered_data()

    rag_df = df[df["rag_query"].notna() & (df["rag_query"] != "")]

    if not rag_df.empty:
        col1, col2, col3 = st.columns(3)
        avg_rag = rag_df["rag_score"].mean()
        low_score = rag_df[rag_df["rag_score"] < 0.4]

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
# PAGE: CONVERSATION FLOWS
# =====================================================
def page_flows():
    st.header("Conversation Flows")
    df, _ = get_filtered_data()

    flow_df = df[df["intent"].notna() & (df["intent"] != "")].sort_values(["conversation_id", "timestamp"])
    conversations = flow_df.groupby("conversation_id")["intent"].apply(list).reset_index()
    conversations.columns = ["conversation_id", "intents"]
    conversations = conversations[conversations["intents"].apply(len) >= 1]

    if conversations.empty:
        st.info("No conversation flow data yet. Conversations will populate this section.")
        return

    # Sankey diagram
    st.subheader("Intent Transition Flow")
    st.caption("How conversations move between intents. Thicker links = more frequent transitions.")

    from collections import Counter
    transitions = Counter()
    first_intents = Counter()
    last_intents = Counter()

    for _, row in conversations.iterrows():
        intents = row["intents"]
        first_intents[intents[0]] += 1
        last_intents[intents[-1]] += 1
        for i in range(len(intents) - 1):
            if intents[i] != intents[i + 1]:
                transitions[(intents[i], intents[i + 1])] += 1

    all_intents = sorted(set(
        list(first_intents.keys()) +
        list(last_intents.keys()) +
        [t[0] for t in transitions.keys()] +
        [t[1] for t in transitions.keys()]
    ))
    node_labels = ["START"] + all_intents + ["END"]
    node_idx = {label: i for i, label in enumerate(node_labels)}

    sources, targets, values = [], [], []

    for intent, count in first_intents.items():
        sources.append(node_idx["START"])
        targets.append(node_idx[intent])
        values.append(count)

    for (src, tgt), count in transitions.items():
        sources.append(node_idx[src])
        targets.append(node_idx[tgt])
        values.append(count)

    for intent, count in last_intents.items():
        sources.append(node_idx[intent])
        targets.append(node_idx["END"])
        values.append(count)

    node_colors = []
    for label in node_labels:
        if label in ("START", "END"):
            node_colors.append("#6c757d")
        elif label == "escalate":
            node_colors.append("#dc3545")
        elif label == "complaint":
            node_colors.append("#fd7e14")
        elif label in ("faq", "fee_inquiry"):
            node_colors.append("#0d6efd")
        elif label in ("status_check", "document_status", "appointment_list"):
            node_colors.append("#198754")
        elif label in ("appointment_book", "document_request"):
            node_colors.append("#6f42c1")
        elif label == "appointment_cancel":
            node_colors.append("#e83e8c")
        else:
            node_colors.append("#adb5bd")

    import plotly.graph_objects as go

    fig = go.Figure(data=[go.Sankey(
        node=dict(pad=20, thickness=25, label=node_labels, color=node_colors),
        link=dict(source=sources, target=targets, value=values, color="rgba(150,150,150,0.3)"),
    )])
    fig.update_layout(height=450, margin=dict(l=20, r=20, t=20, b=20))
    st.plotly_chart(fig, use_container_width=True)

    st.divider()

    st.subheader("Most Common Conversation Paths")
    path_counts = conversations["intents"].apply(lambda x: " -> ".join(x)).value_counts().head(10)
    if not path_counts.empty:
        path_table = path_counts.reset_index()
        path_table.columns = ["Path", "Count"]
        st.dataframe(path_table, hide_index=True, use_container_width=True)

    st.divider()

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Entry Points")
        st.caption("What citizens ask for first")
        first_df = pd.DataFrame(first_intents.items(), columns=["Intent", "Count"]).sort_values("Count", ascending=False)
        st.dataframe(first_df, hide_index=True, use_container_width=True)

    with col2:
        st.subheader("Exit Points")
        st.caption("Where conversations end")
        last_df = pd.DataFrame(last_intents.items(), columns=["Intent", "Count"]).sort_values("Count", ascending=False)
        st.dataframe(last_df, hide_index=True, use_container_width=True)

    st.divider()

    st.subheader("Conversation Depth")
    conversations["depth"] = conversations["intents"].apply(len)
    col1, col2, col3 = st.columns(3)
    col1.metric("Single-Intent", (conversations["depth"] == 1).sum())
    col2.metric("Multi-Intent", (conversations["depth"] > 1).sum())
    col3.metric("Avg Intents/Conv", f"{conversations['depth'].mean():.1f}")
    st.bar_chart(conversations["depth"].value_counts().sort_index())


# =====================================================
# PAGE: SYSTEM HEALTH
# =====================================================
def page_health():
    st.header("System Health")
    df, auth_df = get_filtered_data()

    total_requests = len(df)
    escalated = (df["intent"] == "escalate").sum()
    resolved = total_requests - escalated
    resolution_rate = resolved / max(1, total_requests) * 100
    escalation_rate = escalated / max(1, total_requests) * 100
    avg_response_ms = df["response_time_ms"].mean() if df["response_time_ms"].notna().any() else 0

    anomalies = []

    if escalation_rate > 20:
        anomalies.append(("🔴", "High Escalation Rate", f"{escalation_rate:.1f}% (threshold: 20%)"))
    elif escalation_rate > 10:
        anomalies.append(("🟡", "Elevated Escalation Rate", f"{escalation_rate:.1f}% (threshold: 20%)"))

    if df["response_time_ms"].notna().any():
        if avg_response_ms > 3000:
            anomalies.append(("🔴", "High Response Latency", f"{avg_response_ms:.0f}ms avg (threshold: 3000ms)"))
        elif avg_response_ms > 2000:
            anomalies.append(("🟡", "Elevated Response Latency", f"{avg_response_ms:.0f}ms avg (threshold: 3000ms)"))

    auth_fail_rate = 0
    if not auth_df.empty:
        total_auth = len(auth_df)
        auth_failures = (auth_df["result"] == "failure").sum()
        auth_fail_rate = auth_failures / max(1, total_auth) * 100
        if auth_fail_rate > 30:
            anomalies.append(("🔴", "High Auth Failure Rate", f"{auth_fail_rate:.0f}% ({auth_failures}/{total_auth})"))
        elif auth_fail_rate > 15:
            anomalies.append(("🟡", "Elevated Auth Failure Rate", f"{auth_fail_rate:.0f}% ({auth_failures}/{total_auth})"))

    if resolution_rate < 70:
        anomalies.append(("🔴", "Low Resolution Rate", f"{resolution_rate:.0f}% (threshold: 70%)"))
    elif resolution_rate < 85:
        anomalies.append(("🟡", "Below Target Resolution", f"{resolution_rate:.0f}% (threshold: 85%)"))

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

    if not anomalies:
        st.success("All systems healthy — no anomalies detected")
    else:
        for icon, title, detail in anomalies:
            st.warning(f"{icon} **{title}** — {detail}")

    st.divider()

    st.subheader("Thresholds")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Escalation Rate", f"{escalation_rate:.1f}%")
    col2.metric("Avg Response", f"{avg_response_ms:.0f}ms")
    col3.metric("Auth Fail Rate", f"{auth_fail_rate:.0f}%" if not auth_df.empty else "N/A")
    col4.metric("Resolution Rate", f"{resolution_rate:.0f}%")


# =====================================================
# PAGE: AI INSIGHTS
# =====================================================
def page_insights():
    st.header("AI Insights")
    df, auth_df = get_filtered_data()

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
# PAGE: LOGS
# =====================================================
def page_logs():
    st.header("Conversation Logs")
    df, _ = get_filtered_data()

    recent = df.head(100)[["timestamp", "conversation_id", "intent", "workflow_node", "auth_status", "language", "message_count", "response_time_ms"]]
    st.dataframe(recent, hide_index=True, use_container_width=True)


# =====================================================
# NAVIGATION
# =====================================================

# Sidebar: navigation + filters
pages = {
    "Overview": page_overview,
    "Intents & Performance": page_intents,
    "Auth & Language": page_auth,
    "Knowledge Gaps": page_knowledge,
    "Conversation Flows": page_flows,
    "System Health": page_health,
    "AI Insights": page_insights,
    "Logs": page_logs,
}

st.sidebar.title("Navigation")
selection = st.sidebar.radio("Go to", list(pages.keys()))

st.sidebar.divider()
st.sidebar.header("Filters")

date_range = st.sidebar.selectbox(
    "Date Range",
    ["Last 24 Hours", "Last 7 Days", "Last 30 Days", "All Time"],
    index=3,
    key="date_range",
)

auto_refresh = st.sidebar.checkbox("Auto-refresh (30s)", value=False)
if auto_refresh:
    st.rerun()

# Render selected page
pages[selection]()
