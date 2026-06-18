import streamlit as st


def apply_css():
    st.markdown(
        """
        <style>
        :root {
            --accent: #E87A45;
            --ink: #17191C;
            --muted: #6B6F76;
            --line: #E8EAED;
            --bg: #FAFAF9;
            --surface: #FFFFFF;
            --mono: 'IBM Plex Mono', ui-monospace, Menlo, Monaco, Consolas, monospace;
            --sans: system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
        }
        .stApp {
            background: var(--bg);
            color: var(--ink);
            font-family: var(--sans);
        }
        .block-container {
            max-width: 1180px;
            padding-top: 1.5rem;
        }
        h1, h2, h3, .mono {
            font-family: var(--mono);
        }
        h1 {
            color: var(--accent);
            font-weight: 500;
            letter-spacing: -0.03em;
        }
        .card {
            background: var(--surface);
            border: 1px solid var(--line);
            border-radius: 8px;
            padding: 16px;
            margin-bottom: 12px;
        }
        .muted {
            color: var(--muted);
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
