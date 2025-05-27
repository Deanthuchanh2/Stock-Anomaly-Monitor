import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import datetime
from io import BytesIO
import xlsxwriter
from fpdf import FPDF
import os
from azureml.core import Workspace
from azureml.core.authentication import InteractiveLoginAuthentication
import warnings
warnings.filterwarnings("ignore", category=FutureWarning)

try:
    import pandas_ta as ta
    has_rsi = True
except ImportError:
    has_rsi = False

auth = InteractiveLoginAuthentication(tenant_id="79f22664-3501-4e6b-a5eb-7a0de80c4e0f")
ws = Workspace(
    subscription_id="ac1d1618-29fc-4fab-a96d-aa004a3d7fcd",
    resource_group="DuyHoang",
    workspace_name="DUYHOANG_ML",
    auth=auth
)
datastore = ws.get_default_datastore()
remote_path = "UI/OUTCOME/dunusual_stock.csv"
datastore.download(target_path=".", prefix=remote_path, overwrite=True, show_progress=True)
local_path = "UI/OUTCOME/dunusual_stock.csv"

try:
    df = pd.read_csv(local_path, encoding="utf-8-sig")
except UnicodeDecodeError:
    df = pd.read_csv(local_path, encoding="latin1")
df['Ngày'] = pd.to_datetime(df['Ngày']).dt.tz_localize(None)

# Cấu hình giao diện
st.set_page_config(layout="wide", page_title="Dashboard Cảnh báo Cổ phiếu", page_icon="📈")
st.markdown("""
    <div style='text-align: center;'>
        <h1 style='color: #0A4D68;'> Dashboard Giám sát Giao dịch Bất Thường</h1>
        <p style='color: gray;'>Cập nhật & cảnh báo các giao dịch bất thường trên thị trường chứng khoán</p>
    </div>
    <hr style='border: 1px solid #ccc;'>
""", unsafe_allow_html=True)

# Bộ lọc thời gian
with st.sidebar:
    st.header("⚙️ Bộ lọc")
    min_date = df['Ngày'].min().date()
    max_date = df['Ngày'].max().date()
    start_date, end_date = st.date_input("📅 Chọn khoảng thời gian:", (min_date, max_date), min_value=min_date, max_value=max_date)

# Lọc dữ liệu
mask = (df['Ngày'].dt.date >= start_date) & (df['Ngày'].dt.date <= end_date)
df_filtered = df[mask]
df_bat_thuong = df_filtered[df_filtered['Nhận diện bất thường'].astype(str).str.strip().str.lower() == "bất thường"]
df_bat_thuong['Date'] = df_bat_thuong['Ngày'].dt.date

# 🔢 Chỉ số tổng quan
st.subheader("📌 Tổng quan")
col1, col2, col3 = st.columns(3)
col1.metric("📈 Tổng cảnh báo", len(df_bat_thuong))
col2.metric("📅 Ngày có cảnh báo", df_bat_thuong['Ngày'].nunique())
col3.metric("🏷️ Mã cổ phiếu cảnh báo", df_bat_thuong['Mã cổ phiếu'].nunique())

# 🚨 Bảng dữ liệu
st.subheader("🚨 Danh sách cổ phiếu có dấu hiệu bất thường")
all_columns = df_bat_thuong.columns.tolist()
default_cols = ['Ngày', 'Mã cổ phiếu', 'Giá đóng cửa', 'Ngành', 'Tên công ty']
selected_cols = st.multiselect("Chọn các cột hiển thị", all_columns, default=default_cols)

if df_bat_thuong.empty:
    st.success("✅ Không phát hiện giao dịch bất thường trong khoảng thời gian.")
else:
    st.dataframe(df_bat_thuong[selected_cols], use_container_width=True)

    # 📊 Biểu đồ số lượng cảnh báo theo ngày
    st.subheader("📊 Biểu đồ tổng số cổ phiếu bất thường theo ngày")
    fig_count = px.bar(df_bat_thuong.groupby('Date').size().reset_index(name='Số lượng'),
                       x='Date', y='Số lượng', title='Số lượng cổ phiếu bất thường theo ngày')
    fig_count.update_layout(plot_bgcolor='#f9f9f9', paper_bgcolor='#f9f9f9')
    st.plotly_chart(fig_count, use_container_width=True)

    # 📊 Heatmap theo ngành
    st.subheader("📊 Heatmap cảnh báo theo ngành và ngày")
    heat_data = df_bat_thuong.groupby(['Ngành', 'Date']).size().reset_index(name='Số cảnh báo')
    fig_heatmap = px.density_heatmap(heat_data, x='Date', y='Ngành', z='Số cảnh báo', color_continuous_scale='OrRd')
    st.plotly_chart(fig_heatmap, use_container_width=True)

    # 🔍 Phân tích chi tiết cổ phiếu
    st.subheader("🔎 Phân tích chi tiết cổ phiếu")
    stock_list = df_bat_thuong['Mã cổ phiếu'].unique()
    selected_stock = st.selectbox("Chọn mã cổ phiếu", stock_list)
    df_stock = df[df['Mã cổ phiếu'] == selected_stock].sort_values('Ngày')

    # Bollinger Bands
    def calculate_bollinger_bands(data, window=5, std_dev=2):
        data = data.copy()
        data['Middle Band'] = data['Giá đóng cửa'].rolling(window=window).mean()
        rolling_std = data['Giá đóng cửa'].rolling(window=window).std()
        data['Upper Band'] = data['Middle Band'] + std_dev * rolling_std
        data['Lower Band'] = data['Middle Band'] - std_dev * rolling_std
        return data

    df_stock = calculate_bollinger_bands(df_stock)

    # Tính RSI nếu chưa có
    if has_rsi and 'RSI' not in df_stock.columns:
        df_stock['RSI'] = ta.rsi(df_stock['Giá đóng cửa'], length=14)

    st.subheader("📉 Biểu đồ phân tích kỹ thuật")
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["Bollinger Bands", "RSI", "Giá đóng cửa", "Khối lượng", "MACD"])

    with tab1:
        fig_boll = go.Figure()
        fig_boll.add_trace(go.Scatter(x=df_stock['Ngày'], y=df_stock['Giá đóng cửa'], name='Giá đóng cửa'))
        fig_boll.add_trace(go.Scatter(x=df_stock['Ngày'], y=df_stock['Upper Band'], name='Upper Band', line=dict(color='red', dash='dot')))
        fig_boll.add_trace(go.Scatter(x=df_stock['Ngày'], y=df_stock['Middle Band'], name='Middle Band', line=dict(color='gray')))
        fig_boll.add_trace(go.Scatter(x=df_stock['Ngày'], y=df_stock['Lower Band'], name='Lower Band', line=dict(color='blue', dash='dot')))
        fig_boll.update_layout(title=f"Bollinger Bands - {selected_stock}", xaxis_title="Ngày", yaxis_title="Giá", plot_bgcolor='#fff')
        st.plotly_chart(fig_boll, use_container_width=True)

    with tab2:
        if 'RSI' in df_stock.columns:
            fig_rsi = go.Figure()
            fig_rsi.add_trace(go.Scatter(x=df_stock['Ngày'], y=df_stock['RSI'], name='RSI', line=dict(color='orange')))
            fig_rsi.add_trace(go.Scatter(x=df_stock['Ngày'], y=[70]*len(df_stock), name='Overbought (70)', line=dict(color='red', dash='dash')))
            fig_rsi.add_trace(go.Scatter(x=df_stock['Ngày'], y=[30]*len(df_stock), name='Oversold (30)', line=dict(color='green', dash='dash')))
            fig_rsi.update_layout(title="RSI", xaxis_title="Ngày", yaxis_title="RSI", plot_bgcolor='#fff')
            st.plotly_chart(fig_rsi, use_container_width=True)

            # Cảnh báo RSI
            rsi_latest = df_stock['RSI'].iloc[-1]
            if rsi_latest > 70:
                st.warning("⚠️ RSI vượt 70 - Cảnh báo mua quá mức (Overbought)")
            elif rsi_latest < 30:
                st.warning("⚠️ RSI dưới 30 - Cảnh báo bán quá mức (Oversold)")
            else:
                st.success("✅ RSI trong vùng an toàn")
        else:
            st.info("🛠️ Chưa có chỉ số RSI – Cài pandas_ta để tự động tính.")

    with tab3:
        st.plotly_chart(px.line(df_stock, x='Ngày', y='Giá đóng cửa', title=f'Giá đóng cửa - {selected_stock}', template="simple_white"), use_container_width=True)

    with tab4:
        st.plotly_chart(px.line(df_stock, x='Ngày', y='Khối lượng giao dịch', title='Khối lượng giao dịch', template="simple_white"), use_container_width=True)

    with tab5:
        st.plotly_chart(px.line(df_stock, x='Ngày', y=['MACD', 'Signal_Line'], title='MACD & Signal Line', template="simple_white"), use_container_width=True)
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


    st.subheader("📥 Tải Dữ Liệu")
    with st.expander("Tải dữ liệu cổ phiếu bất thường"):
        export_type = st.selectbox("Chọn định dạng xuất", ["Excel", "PDF"])
        time_frame = st.radio("Chọn khoảng dữ liệu", ("Ngày", "Tuần", "Toàn bộ"))
        export_start, export_end = st.date_input("📆 Khoảng thời gian xuất file:",
                                                 (min_date, max_date),
                                                 min_value=min_date, max_value=max_date,
                                                 key="export_date")
        mask_export = (df_bat_thuong['Ngày'].dt.date >= export_start) & (df_bat_thuong['Ngày'].dt.date <= export_end)
        df_export = df_bat_thuong[mask_export]
        if time_frame == "Tuần":
            df_export = df_export.resample('W-Mon', on='Ngày').last().dropna()

        if df_export.empty:
            st.warning("⚠️ Không có dữ liệu trong khoảng thời gian đã chọn.")
        else:
            if export_type == "Excel":
                def to_excel(df):
                    for col in df.columns:
                        if pd.api.types.is_datetime64_any_dtype(df[col]):
                            df[col] = pd.to_datetime(df[col]).dt.tz_localize(None)
                    output = BytesIO()
                    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                        df.to_excel(writer, index=False, sheet_name='Abnormal Stocks')
                    return output.getvalue()

                excel_data = to_excel(df_export)
                st.download_button(label="📥 Tải file Excel", data=excel_data,
                                   file_name="abnormal_stocks.xlsx",
                                   mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

            elif export_type == "PDF":
                def to_pdf(df):
                    pdf = FPDF()
                    pdf.add_page()
                    font_path = "DejaVuSans.ttf"
                    if not os.path.exists(font_path):
                        st.error("Không tìm thấy file font 'DejaVuSans.ttf'.")
                        return None
                    pdf.add_font("DejaVu", "", font_path, uni=True)
                    pdf.set_font("DejaVu", size=12)
                    pdf.cell(0, 10, txt="Danh sách cổ phiếu bất thường", ln=True, align='C')
                    pdf.ln(10)
                    for col in df.columns.tolist():
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
                    st.download_button(label="📄 Tải file PDF", data=pdf_data,
                                       file_name="abnormal_stocks.pdf",
                                       mime="application/pdf")
