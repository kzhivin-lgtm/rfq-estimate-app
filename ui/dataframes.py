import streamlit as st
import pandas as pd


def show_df(title: str, df: pd.DataFrame, height: int = 360):
    st.subheader(title)
    if df is None or df.empty:
        st.info("No data.")
        return
    st.dataframe(df, use_container_width=True, height=height)
