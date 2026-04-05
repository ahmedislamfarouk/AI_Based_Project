import streamlit as st
import pandas as pd
import glob
import os
import time

st.set_page_config(page_title="Multimodal Emotion Monitor", layout="wide")

st.title("🧠 Multimodal AI Monitor Dashboard")
st.markdown("---")

def get_latest_log():
    list_of_files = glob.glob('data/sessions/*.csv')
    if not list_of_files:
        return None
    return max(list_of_files, key=os.path.getctime)

latest_log = get_latest_log()

if latest_log:
    st.sidebar.success(f"Connected to log: {os.path.basename(latest_log)}")
    
    # Placeholders for dynamic content
    placeholder_data = st.empty()
    placeholder_charts = st.empty()

    while True:
        try:
            df = pd.read_csv(latest_log)
            
            with placeholder_data.container():
                col1, col2, col3 = st.columns(3)
                
                # Metrics for latest state
                if not df.empty:
                    latest = df.iloc[-1]
                    col1.metric("Video Emotion", latest['video_emotion'])
                    col2.metric("Voice Arousal", latest['voice_arousal'])
                    col3.metric("Distress Score", f"{latest['distress_level']}/100")

                    st.write("### 💬 Live AI Recommendation")
                    st.info(latest['recommendation'])

                    st.write("### 📋 Recent History")
                    st.dataframe(df.tail(10), use_container_width=True)

            with placeholder_charts.container():
                st.write("### 📈 Distress Trend")
                if 'distress_level' in df.columns:
                    st.line_chart(df['distress_level'])
            
            time.sleep(2)
        except Exception as e:
            st.error(f"Error reading log: {e}")
            time.sleep(2)
else:
    st.warning("No session logs found. Please start `main.py` to begin recording.")
    if st.button("Refresh"):
        st.rerun()
