import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import datetime
from azureml.core import Workspace, Dataset
from azureml.core.authentication import InteractiveLoginAuthentication
from io import BytesIO
import xlsxwriter
from fpdf import FPDF
import os

# === Setup Azure ML Workspace ===
auth = InteractiveLoginAuthentication()
ws = Workspace(
    subscription_id="9b250c08-bb98-4839-80d0-a29aa5980162",
    resource_group="ML",
    workspace_name="ML_HOANG",
    auth=auth
)
datastore = ws.get_default_datastore()
dataset = Dataset.File.from_files(path=(datastore, 'UI/DF/dunusual_stock.csv'))
csv_path = dataset.download()[0]

# === Load data ===
try:
    df = pd.read_csv(csv_path, encoding='utf-8-sig')
except UnicodeDecodeError:
    df = pd.read_csv(csv_path, encoding='latin1')
df['Ngày'] = pd.to_datetime(df['Ngày']).dt.tz_localize(None)

# === Streamlit App ===
st.set_page_config(layout="wide")
st.markdown("<h1 style='text-align: center;'> Dashboard Giám sát Giao dịch Bất Thường</h1>", unsafe_allow_html=True)

min_date = df['Ngày'].min().date()
max_date = df['Ngày'].max().date()
start_date, end_date = st.date_input("\U0001F4C5 Chọn khoảng thời gian giao dịch:", (min_date, max_date), min_value=min_date, max_value=max_date)
mask = (df['Ngày'].dt.date >= start_date) & (df['Ngày'].dt.date <= end_date)
df_filtered = df[mask]
df_bat_thuong = df_filtered[df_filtered['Nhận diện bất thường'].astype(str).str.strip().str.lower() == "bất thường"]

st.subheader("\U0001F6A8 Danh sách cổ phiếu có dấu hiệu bất thường")
if df_bat_thuong.empty:
    st.success("✅ Không phát hiện giao dịch bất thường trong khoảng thời gian.")
else:
    st.dataframe(df_bat_thuong[[ 
        'Ngày', 'Mã cổ phiếu', 'Giá đóng cửa', 'Khối lượng giao dịch', 
        'Cảnh báo biến động giá', 'Cảnh báo dòng tiền khối ngoại', 
        'Cảnh báo thanh khoản', 'Cảnh báo Bollinger', 'Cảnh báo RSI', 
        'Cảnh báo MACD']], use_container_width=True)

    st.subheader("\U0001F50D Phân tích chi tiết cổ phiếu")
    stock_list = df_bat_thuong['Mã cổ phiếu'].unique()
    selected_stock = st.selectbox("Chọn mã cổ phiếu", stock_list)

    df_stock = df[df['Mã cổ phiếu'] == selected_stock].sort_values('Ngày')

    def calculate_bollinger_bands(data, window=20, std_dev=2):
        data = data.copy()
        data['Middle Band'] = data['Giá đóng cửa'].rolling(window=window).mean()
        rolling_std = data['Giá đóng cửa'].rolling(window=window).std()
        data['Upper Band'] = data['Middle Band'] + std_dev * rolling_std
        data['Lower Band'] = data['Middle Band'] - std_dev * rolling_std
        return data

    df_stock = calculate_bollinger_bands(df_stock)

    st.markdown("### \U0001F4CA Biểu đồ phân tích kỹ thuật")

    fig_boll = go.Figure()
    fig_boll.add_trace(go.Scatter(x=df_stock['Ngày'], y=df_stock['Giá đóng cửa'], name='Giá đóng cửa'))
    fig_boll.add_trace(go.Scatter(x=df_stock['Ngày'], y=df_stock['Upper Band'], name='Upper Band', line=dict(color='red', dash='dot')))
    fig_boll.add_trace(go.Scatter(x=df_stock['Ngày'], y=df_stock['Middle Band'], name='Middle Band', line=dict(color='gray')))
    fig_boll.add_trace(go.Scatter(x=df_stock['Ngày'], y=df_stock['Lower Band'], name='Lower Band', line=dict(color='blue', dash='dot')))
    fig_boll.update_layout(title=f"Bollinger Bands - {selected_stock}", xaxis_title="Ngày", yaxis_title="Giá", height=400)
    st.plotly_chart(fig_boll, use_container_width=True)

    fig_rsi = go.Figure()
    fig_rsi.add_trace(go.Scatter(x=df_stock['Ngày'], y=df_stock['RSI'], name='RSI', line=dict(color='orange')))
    fig_rsi.add_trace(go.Scatter(x=df_stock['Ngày'], y=[70]*len(df_stock), name='Overbought (70)', line=dict(color='red', dash='dash')))
    fig_rsi.add_trace(go.Scatter(x=df_stock['Ngày'], y=[30]*len(df_stock), name='Oversold (30)', line=dict(color='green', dash='dash')))
    fig_rsi.update_layout(title="RSI", xaxis_title="Ngày", yaxis_title="RSI", height=300)
    st.plotly_chart(fig_rsi, use_container_width=True)

    st.plotly_chart(px.line(df_stock, x='Ngày', y='Giá đóng cửa', title=f'📉 Giá đóng cửa - {selected_stock}'), use_container_width=True)
    st.plotly_chart(px.line(df_stock, x='Ngày', y='Khối lượng giao dịch', title='📊 Khối lượng giao dịch'), use_container_width=True)
    st.plotly_chart(px.line(df_stock, x='Ngày', y=['MACD', 'Signal_Line'], title='📉 MACD & Signal Line'), use_container_width=True)

    st.subheader("⚠️ Cảnh báo gần nhất")
    df_stock['Ngày_date'] = df_stock['Ngày'].dt.date
    df_stock['Nhận diện bất thường'] = df_stock['Nhận diện bất thường'].fillna('').astype(str)
    df_stock_bat_thuong = df_stock[(df_stock['Nhận diện bất thường'].str.strip().str.lower() == 'bất thường') & (df_stock['Ngày_date'] <= end_date)]
    if not df_stock_bat_thuong.empty:
        last_row = df_stock_bat_thuong.sort_values('Ngày', ascending=False).iloc[0]
        with st.expander("Chi tiết cảnh báo"):
            st.markdown(f"- **Ngày**: {last_row['Ngày'].date()}")
            for col in ['Cảnh báo biến động giá', 'Cảnh báo thanh khoản', 'Cảnh báo dòng tiền khối ngoại', 'Cảnh báo Bollinger', 'Cảnh báo RSI', 'Cảnh báo MACD', 'Cảnh báo ATR']:
                st.markdown(f"- **{col}**: {last_row.get(col, 'Không có')}")
            st.markdown(f"- **Anomaly Score**: {last_row.get('Anomaly_Score', 0):.3f}")
    else:
        st.info("✅ Không có giao dịch bất thường nào gần với ngày đã chọn.")

    # === Export Data ===
    st.subheader("\U0001F4E5 Tải Dữ Liệu")
    time_frame = st.radio("Chọn khoảng thời gian", ("Ngày", "Tuần", "Toàn bộ"))
    df_export = df_bat_thuong if time_frame == "Ngày" else df_bat_thuong.resample('W-Mon', on='Ngày').last() if time_frame == "Tuần" else df_bat_thuong
    export_type = st.selectbox("Chọn định dạng xuất", ["Excel", "PDF"])

    if export_type == "Excel":
        def to_excel(df):
            for col in df.columns:
                if pd.api.types.is_datetime64_any_dtype(df[col]):
                    df[col] = pd.to_datetime(df[col]).dt.tz_localize(None)
            output = BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df.to_excel(writer, index=False, sheet_name='Abnormal Stocks')
                writer.book.close()
            return output.getvalue()

        excel_data = to_excel(df_export)
        st.download_button(label="Tải file Excel", data=excel_data, file_name="abnormal_stocks.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    elif export_type == "PDF":
        def to_pdf(df):
            pdf = FPDF()
            pdf.add_page()
            font_path = "DejaVuSans.ttf"
            if not os.path.exists(font_path):
                st.error("Không tìm thấy file font 'DejaVuSans.ttf'. Vui lòng tải về và đặt cùng thư mục với script.")
                return None
            pdf.add_font("DejaVu", "", font_path, uni=True)
            pdf.set_font("DejaVu", size=12)
            pdf.cell(0, 10, txt="Danh sách cổ phiếu bất thường", ln=True, align='C')
            pdf.ln(10)

            col_names = df.columns.tolist()
            for col in col_names:
                pdf.cell(40, 10, str(col), 1, 0, 'C')
            pdf.ln()

            for row in df.itertuples(index=False):
                for value in row:
                    pdf.cell(40, 10, str(value), 1, 0, 'C')
                pdf.ln()

            pdf_output = BytesIO()
            pdf.output(pdf_output)
            return pdf_output.getvalue()

        pdf_data = to_pdf(df_export)
        if pdf_data:
            st.download_button(label="Tải file PDF", data=pdf_data, file_name="abnormal_stocks.pdf", mime="application/pdf")
