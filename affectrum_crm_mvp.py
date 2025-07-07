import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import datetime
import base64

st.set_page_config(page_title="Affectrum CRM Dashboard", layout="wide")
st.title("🧠 Affectrum CRM Dashboard")

# Session state for notes
if "notes" not in st.session_state:
    st.session_state.notes = []

# Clinician session entry
st.sidebar.header("📅 Clinician Entry")
st.sidebar.date_input("Today's Date", value=datetime.date.today())

def export_notes_as_csv(notes):
    df_notes = pd.DataFrame(notes, columns=["Timestamp", "Note"])
    return df_notes.to_csv(index=False).encode("utf-8")

def export_notes_as_pdf(notes):
    from fpdf import FPDF
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    pdf.cell(200, 10, "Affectrum CRM Notes", ln=True, align="C")
    pdf.ln()
    for timestamp, note in notes:
        pdf.multi_cell(0, 10, f"[{timestamp}]\n{note}\n")
        pdf.ln()
    pdf_output = "/tmp/notes.pdf"
    pdf.output(pdf_output)
    with open(pdf_output, "rb") as f:
        return f.read()

st.markdown("## 📄 Upload Affectrum Log CSV")
st.markdown("Drag and drop your `.csv` file here, or click **Browse files** to select manually.")
uploaded_file = st.file_uploader("Choose a CSV file", type=["csv"], label_visibility="collapsed")

if uploaded_file:
    df = pd.read_csv(uploaded_file)
    df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
    df['Date_Day'] = df['Date'].dt.date

    with st.expander("📄 Raw Data Preview"):
        st.dataframe(df.head())

    st.sidebar.header("🔎 Filters")
    start_date = st.sidebar.date_input("Start Date", value=df['Date'].min().date())
    end_date = st.sidebar.date_input("End Date", value=df['Date'].max().date())
    substances = st.sidebar.multiselect("Filter by Substance", options=df[df['Type'] == 'substance']['Substance'].dropna().unique().tolist())
    activities = st.sidebar.multiselect("Filter by Activity", options=df[df['Type'] == 'activity']['Activity'].dropna().unique().tolist())

    mood_df = df[df['Type'] == 'mood'].dropna(subset=['Mood']).copy()
    mood_df = mood_df[(mood_df['Date_Day'] >= start_date) & (mood_df['Date_Day'] <= end_date)]

    # Mood Hover: default just Mood
    mood_df['Hover_Info'] = mood_df.apply(lambda row: f"Mood: {row['Mood']}", axis=1)

    # Filter logic with same-day matching
    if substances or activities:
        sub_map = df[df['Type'] == 'substance'].groupby('Date_Day')['Substance'].apply(list)
        act_map = df[df['Type'] == 'activity'].groupby('Date_Day')['Activity'].apply(list)
        mood_df['Substance_List'] = mood_df['Date_Day'].map(sub_map)
        mood_df['Activity_List'] = mood_df['Date_Day'].map(act_map)

        if substances:
            mood_df = mood_df[mood_df['Substance_List'].apply(lambda x: any(sub in x for sub in substances) if isinstance(x, list) else False)]
        if activities:
            mood_df = mood_df[mood_df['Activity_List'].apply(lambda x: any(act in x for act in activities) if isinstance(x, list) else False)]

        mood_df['Hover_Info'] = mood_df.apply(
            lambda row: f"Mood: {row['Mood']}\nSubstances: {row['Substance_List']}\nActivities: {row['Activity_List']}", axis=1
        )

    st.subheader("📈 Mood Trend Over Time")
    fig = px.line(
        mood_df, x='Date', y='Mood', markers=True,
        title='Mood Over Time', hover_data=['Hover_Info']
    )
    st.plotly_chart(fig, use_container_width=True)

    # Mood by Substance
    st.subheader("🧪 Mood by Substance")
    sub_df = df[df['Type'] == 'substance']
    merged_sub = pd.merge(mood_df[['Date', 'Mood']], sub_df[['Date', 'Substance']], on='Date', how='inner')
    if not merged_sub.empty:
        fig_sub = px.box(merged_sub, x='Substance', y='Mood', points='all')
        st.plotly_chart(fig_sub, use_container_width=True)

    # Mood by Activity
    st.subheader("🏃 Mood by Activity")
    act_df = df[df['Type'] == 'activity']
    merged_act = pd.merge(mood_df[['Date', 'Mood']], act_df[['Date', 'Activity']], on='Date', how='inner')
    if not merged_act.empty:
        fig_act = px.box(merged_act, x='Activity', y='Mood', points='all')
        st.plotly_chart(fig_act, use_container_width=True)

    # Mood vs Sleep Dual Axis
    sleep_df = df[df['Activity'].isin(['Sleep Start', 'Wake Up'])].sort_values('Date')
    sleep_sessions = []
    start_time = None
    for _, row in sleep_df.iterrows():
        if row['Activity'] == 'Sleep Start':
            start_time = row['Date']
        elif row['Activity'] == 'Wake Up' and start_time:
            sleep_hours = (row['Date'] - start_time).total_seconds() / 3600
            sleep_sessions.append({'Sleep Start': start_time, 'Wake Time': row['Date'], 'Sleep Hours': sleep_hours})
            start_time = None
    sleep_df_final = pd.DataFrame(sleep_sessions)
    if not sleep_df_final.empty:
        sleep_df_final['Sleep Date'] = sleep_df_final['Wake Time'].dt.date
        merged_df = pd.merge(mood_df, sleep_df_final, left_on='Date_Day', right_on='Sleep Date', how='left')
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=merged_df['Date'], y=merged_df['Mood'], mode='lines+markers', name='Mood', yaxis='y1'))
        fig.add_trace(go.Scatter(x=merged_df['Date'], y=merged_df['Sleep Hours'], mode='lines+markers', name='Sleep Duration (hrs)', yaxis='y2'))
        fig.update_layout(
            title='Mood and Sleep Duration Over Time',
            xaxis=dict(title='Date'),
            yaxis=dict(title='Mood (1-10)', range=[1, 10]),
            yaxis2=dict(title='Sleep Duration (hrs)', overlaying='y', side='right'),
            legend=dict(x=0.5, y=1.1, orientation='h')
        )
        st.subheader("🛌 Mood and Sleep Correlation")
        st.plotly_chart(fig, use_container_width=True)

    # Clinician Notes
    st.subheader("📝 Clinician Notes")
    st.markdown("Use this space to record trends or interpretations")
    note_input = st.text_area("Session Summary")
    if st.button("Save Note"):
        today_str = datetime.datetime.now().strftime("%Y-%m-%d")
        st.session_state.notes.append((today_str, note_input))
        st.success("Note saved!")

    if st.session_state.notes:
        st.write("### Saved Notes")
        for ts, note in st.session_state.notes:
            st.markdown(f"**{ts}**: {note}")

        st.download_button("\ud83d\udcc4 Download Notes as CSV", data=export_notes_as_csv(st.session_state.notes),
                           file_name="affectrum_notes.csv", mime="text/csv")

        try:
            pdf_bytes = export_notes_as_pdf(st.session_state.notes)
            b64_pdf = base64.b64encode(pdf_bytes).decode()
            href = f'<a href="data:application/octet-stream;base64,{b64_pdf}" download="affectrum_notes.pdf">📄 Download Notes as PDF</a>'
            st.markdown(href, unsafe_allow_html=True)
        except:
            st.warning("PDF export failed (requires `fpdf`). Run `pip install fpdf` if needed.")
else:
    st.info("👈 Upload a CSV file to begin.")
