# Updated Streamlit App Snippet (cleaned + collapsible help)

import streamlit as st

st.set_page_config(page_title="Mortgage Roulette", layout="wide")

st.title("Welcome to Mortgage Roulette")

# Collapsible How to use
with st.expander("ℹ️ How to use"):
    st.markdown(
        "- For best viewing on mobile, switch to **landscape mode**\n"
        "- Use chart icons (top right) to **download PNG**\n"
        "- Additional download options (HTML / JSON) are below each chart"
    )

st.write("...rest of your app remains unchanged...")
