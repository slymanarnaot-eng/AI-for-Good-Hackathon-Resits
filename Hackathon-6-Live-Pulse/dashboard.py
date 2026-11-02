from pathlib import Path
import sqlite3

import pandas as pd
import plotly.express as px
import streamlit as st


BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "rail_pulse_clean.db"
TIMEZONE = "Europe/Amsterdam"

st.set_page_config(
    page_title="Rail Pulse | Passenger Sentiment",
    page_icon="🚆",
    layout="wide",
)

st.title("🚆 Rail Pulse")
st.subheader("Dutch railway passenger sentiment")
st.caption(
    "A live pulse of public posts about railway service, "
    "disruptions and passenger experience."
)

if not DB_PATH.exists():
    st.error(f"Database not found: {DB_PATH}")
    st.stop()


@st.cache_data(ttl=15)
def load_data(database_path, modified_time):
    with sqlite3.connect(database_path) as connection:
        return pd.read_sql_query(
            """
            SELECT id, post_text, post_time, collected_at, sentiment, topic
            FROM posts
            ORDER BY post_time DESC
            """,
            connection,
        )


df = load_data(str(DB_PATH), DB_PATH.stat().st_mtime)

if df.empty:
    st.warning("No posts are stored in the database yet.")
    st.stop()

df["published_utc"] = pd.to_datetime(
    df["post_time"], utc=True, errors="coerce"
)
df["collected_utc"] = pd.to_datetime(
    df["collected_at"], utc=True, errors="coerce"
)

df = df.dropna(subset=["published_utc"]).copy()
df["published_local"] = df["published_utc"].dt.tz_convert(TIMEZONE)
df["day"] = df["published_local"].dt.date
df["sentiment"] = df["sentiment"].fillna("unknown").str.lower()
df["topic"] = df["topic"].fillna("Uncategorized")

sentiment_scores = {
    "negative": -1,
    "neutral": 0,
    "positive": 1,
}
df["sentiment_score"] = df["sentiment"].map(sentiment_scores)

min_date = df["day"].min()
max_date = df["day"].max()

st.sidebar.header("Filters")

period = st.sidebar.selectbox(
    "Publication period",
    [
        "All records",
        "Last 7 days",
        "Last 30 days",
        "Custom range",
    ],
)

filtered = df.copy()

if period == "Last 7 days":
    cutoff = pd.Timestamp.now(tz=TIMEZONE) - pd.Timedelta(days=7)
    filtered = filtered[filtered["published_local"] >= cutoff]

elif period == "Last 30 days":
    cutoff = pd.Timestamp.now(tz=TIMEZONE) - pd.Timedelta(days=30)
    filtered = filtered[filtered["published_local"] >= cutoff]

elif period == "Custom range":
    date_range = st.sidebar.date_input(
        "Choose dates",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date,
    )
    if isinstance(date_range, (tuple, list)) and len(date_range) == 2:
        start_date, end_date = date_range
        filtered = filtered[
            (filtered["day"] >= start_date)
            & (filtered["day"] <= end_date)
        ]

available_sentiments = sorted(filtered["sentiment"].unique())
selected_sentiments = st.sidebar.multiselect(
    "Sentiment",
    available_sentiments,
    default=available_sentiments,
)

filtered = filtered[
    filtered["sentiment"].isin(selected_sentiments)
]

available_topics = sorted(filtered["topic"].unique())
selected_topics = st.sidebar.multiselect(
    "Topic",
    available_topics,
    default=available_topics,
)

filtered = filtered[filtered["topic"].isin(selected_topics)]

keyword = st.sidebar.text_input(
    "Search post text",
    placeholder="e.g. vertraging, Leiden, lift",
)

if keyword.strip():
    filtered = filtered[
        filtered["post_text"].str.contains(
            keyword.strip(), case=False, na=False, regex=False
        )
    ]

if filtered.empty:
    st.info("No posts match the selected filters.")
    st.stop()

total = len(filtered)
negative_count = int((filtered["sentiment"] == "negative").sum())
neutral_count = int((filtered["sentiment"] == "neutral").sum())
positive_count = int((filtered["sentiment"] == "positive").sum())

negative_pct = negative_count / total * 100
neutral_pct = neutral_count / total * 100
positive_pct = positive_count / total * 100

st.caption(
    f"Showing {total:,} posts | "
    f"Publication dates: {filtered['day'].min()} to "
    f"{filtered['day'].max()}"
)

col1, col2, col3, col4 = st.columns(4)
col1.metric("Posts analyzed", f"{total:,}")
col2.metric("Negative", f"{negative_pct:.1f}%", f"{negative_count} posts")
col3.metric("Neutral", f"{neutral_pct:.1f}%", f"{neutral_count} posts")
col4.metric("Positive", f"{positive_pct:.1f}%", f"{positive_count} posts")

st.divider()

st.header("Sentiment over time")
st.write(
    "Daily post counts show the volume of collected opinions. "
    "The average sentiment score shows how the balance changes."
)

daily_counts = (
    filtered.groupby(["day", "sentiment"])
    .size()
    .reset_index(name="posts")
)

sentiment_colors = {
    "negative": "#DC4C4C",
    "neutral": "#9CA3AF",
    "positive": "#16A36A",
}

fig_counts = px.bar(
    daily_counts,
    x="day",
    y="posts",
    color="sentiment",
    barmode="stack",
    category_orders={
        "sentiment": ["negative", "neutral", "positive"]
    },
    color_discrete_map=sentiment_colors,
    labels={
        "day": "Publication date",
        "posts": "Number of posts",
        "sentiment": "Model sentiment",
    },
)
fig_counts.update_layout(
    legend_title_text="Sentiment",
    xaxis_title="Publication date",
    yaxis_title="Number of posts",
)
st.plotly_chart(fig_counts, use_container_width=True)

daily_mood = (
    filtered.dropna(subset=["sentiment_score"])
    .groupby("day")["sentiment_score"]
    .mean()
    .reset_index(name="average_score")
)

if not daily_mood.empty:
    fig_mood = px.line(
        daily_mood,
        x="day",
        y="average_score",
        markers=True,
        labels={
            "day": "Publication date",
            "average_score": "Average sentiment score",
        },
        title="Daily sentiment balance",
    )
    fig_mood.update_yaxes(
        range=[-1, 1],
        tickvals=[-1, 0, 1],
        ticktext=["Negative", "Neutral", "Positive"],
    )
    fig_mood.update_layout(
        xaxis_title="Publication date",
        yaxis_title="Average model score",
    )
    st.plotly_chart(fig_mood, use_container_width=True)

left, right = st.columns(2)

with left:
    st.subheader("Topics")
    topic_counts = (
        filtered.groupby("topic")
        .size()
        .reset_index(name="posts")
        .sort_values("posts", ascending=True)
    )
    fig_topics = px.bar(
        topic_counts,
        x="posts",
        y="topic",
        orientation="h",
        labels={"posts": "Number of posts", "topic": "Topic"},
    )
    st.plotly_chart(fig_topics, use_container_width=True)

with right:
    st.subheader("Sentiment breakdown")
    sentiment_counts = (
        filtered.groupby("sentiment")
        .size()
        .reset_index(name="posts")
    )
    fig_pie = px.pie(
        sentiment_counts,
        names="sentiment",
        values="posts",
        color="sentiment",
        color_discrete_map=sentiment_colors,
        hole=0.45,
    )
    st.plotly_chart(fig_pie, use_container_width=True)

st.divider()
st.header("Inspect the posts")

st.write(
    "Use this table to inspect the original text behind a change "
    "in sentiment or a peak in post volume."
)

display_df = filtered.sort_values(
    "published_local", ascending=False
).copy()

display_df["published_local"] = display_df["published_local"].astype(str)
display_df = display_df[
    ["published_local", "sentiment", "topic", "post_text"]
].rename(
    columns={
        "published_local": "Published (Amsterdam time)",
        "sentiment": "Model sentiment",
        "topic": "Topic",
        "post_text": "Post text",
    }
)

st.dataframe(
    display_df.head(200),
    use_container_width=True,
    hide_index=True,
    height=450,
)

csv = display_df.to_csv(index=False).encode("utf-8")
st.download_button(
    "Download filtered posts as CSV",
    data=csv,
    file_name="rail_pulse_filtered_posts.csv",
    mime="text/csv",
)

st.caption(
    "Interpretation warning: these are public posts collected by the "
    "configured sources, not a representative survey of all passengers. "
    "Sentiment labels are model predictions and may be wrong."
)
