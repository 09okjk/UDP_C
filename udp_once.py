import streamlit as st
import socket
from datetime import datetime
import binascii
import time
import os
import csv
import pandas as pd
import altair as alt
import zipfile
from io import BytesIO

def send_and_receive_udp(sock, data, address, timeout):
    sock.settimeout(timeout)
    try:
        sock.sendto(data, address)
        response, _ = sock.recvfrom(1024)
        print(f'Request: {binascii.hexlify(data).decode()}')
        print(f'Response: {binascii.hexlify(response).decode()}')
        return response
    except socket.timeout:
        st.warning(f'等待时间超过 {timeout} 秒，未收到回复，请重试。')
        return None

def parse_response(response):
    hex_response = binascii.hexlify(response).decode()
    header = hex_response[:4]
    command = hex_response[4:6]
    if command == '01':
        channel = hex_response[6:8] if len(hex_response) > 8 else '00'
        length = hex_response[8:16] if len(hex_response) > 16 else '00000000'
        mac = hex_response[16:28] if len(hex_response) > 28 else '000000000000'
        ip = hex_response[28:40] if len(hex_response) > 60 else '00000000'
        return header, command, channel, length, mac, ip
    elif command == '04':
        switch_status = hex_response[6:8]
        return switch_status
    return header, command

def log_data_to_file(timestamp, channel, length, data):
    with open("data.txt", "a") as file:
        file.write(f"{timestamp}\n")
        file.write(f"Channel: {channel}\n")
        file.write(f"Length: {length}\n")
        file.write(f"Data Packet: {data}\n")
        file.write("\n")

def run_sampling(sock, address, f_header):
    fourth_dialogue_data = f_header + b'\x02' + bytes.fromhex(st.session_state["channel"]) + bytes.fromhex(st.session_state["length"]) + bytes.fromhex(st.session_state["mac"]) + bytes.fromhex(st.session_state["ip"])
    fourth_response = send_and_receive_udp(sock, fourth_dialogue_data, address, st.session_state["timeout"])
    if fourth_response:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        a_response = binascii.hexlify(fourth_response).decode()
        data_packet = a_response[16:len(a_response)]
        log_data_to_file(timestamp, st.session_state["channel"], st.session_state["length"], data_packet)
        df = hex_to_decimal_and_save(data_packet)
        return df

def hex_to_decimal_and_save(data_packet):
    if len(data_packet) % 8 != 0:
        raise ValueError("The length of data_packet must be divisible by 8.")
    
    hex_values = [data_packet[i:i+8] for i in range(0, len(data_packet), 8)]
    decimal_values = [int(value, 16) / 10000 for value in hex_values]

    df = pd.DataFrame({
        'Index': list(range(len(decimal_values))),
        'Decimal Value': decimal_values
    })

    if not os.path.exists("csv"):
        os.makedirs("csv")
    
    csv_name = f"output_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    st.session_state["csv_name"] = csv_name

    df.to_csv(f"csv/{csv_name}", index=False)
    
    return df

def create_zip_file(folder_path):
    s = BytesIO()
    with zipfile.ZipFile(s, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(folder_path):
            for file in files:
                zipf.write(os.path.join(root, file), os.path.relpath(os.path.join(root, file), folder_path))
    return s.getvalue()

if "sampling_status" not in st.session_state:
    st.session_state["sampling_status"] = "off"
if "connection_verified" not in st.session_state:
    st.session_state["connection_verified"] = False
if "timeout" not in st.session_state:
    st.session_state["timeout"] = 30
if "df_data" not in st.session_state:
    st.session_state["df_data"] = None
if "csv_name" not in st.session_state:
    st.session_state["csv_name"] = None

with st.sidebar:
    st.title("数据接收处理")

    col1, col2 = st.columns(2)
    with col1:
        ip_address = st.text_input("输入IP地址:")
    with col2:
        port = st.number_input("输入端口号:", min_value=1, max_value=65535, value=1234)
    timeout = st.number_input("设置数据接收超时时间(秒):", min_value=1, value=30)
    sample_rate = st.selectbox("选择采样频率", ['256k', '128k', '64k', '8k'])

    f_header = b'\x28\x5A'
    hz_dict = {'256k': '00', '128k': '01', '64k': '02', '8k': '03'}
    switch_dict = {'on': '00', 'off': '01'}

    if st.button('连接'):
        if not ip_address:
            st.error("IP地址不能为空")
        elif port == 0:
            st.error("端口号不能为空")
        else:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                first_dialogue_data = f_header + b'\x01'
                first_response = send_and_receive_udp(sock, first_dialogue_data, (ip_address, port), timeout)
                
                if first_response:
                    header, command, channel, length, mac, ip = parse_response(first_response)
                    
                    st.session_state["channel"] = channel
                    st.session_state["length"] = length
                    st.session_state["mac"] = mac
                    st.session_state["ip"] = ip
                    
                    second_dialogue_data = f_header + b'\x03' + bytes.fromhex(hz_dict[sample_rate])
                    second_response = send_and_receive_udp(sock, second_dialogue_data, (ip_address, port), timeout)
                    
                    if second_response:
                        st.session_state["connection_verified"] = True
                        st.session_state["timeout"] = timeout
                        st.success("连接成功，可以开始采集数据")
                    else:
                        st.session_state["connection_verified"] = False
                else:
                    st.session_state["connection_verified"] = False

    if st.session_state["connection_verified"]:
        if st.button('切换采集状态(开/关)'):
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock: 
                new_status = "off" if st.session_state["sampling_status"] == "on" else "on"
                third_dialogue_data = f_header + b'\x04' + bytes.fromhex(switch_dict[new_status])
                status = parse_response(send_and_receive_udp(sock, third_dialogue_data, (ip_address, port), st.session_state["timeout"]))
                
                if status == "00":
                    st.session_state["sampling_status"] = "on"
                    st.success("采集器开启")
                elif status == "01":
                    st.session_state["sampling_status"] = "off"
                    st.warning("采集器关闭")

                time.sleep(0.5)
        if st.button("发送数据") and st.session_state["sampling_status"] == "on":
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                st.session_state["df_data"] = run_sampling(sock, (ip_address, port), f_header)
    else:
        st.info("请先点击连接按钮并确保连接成功")
    
    st.write("---")

    col5, col6 = st.columns(2)
    with col5:
        if st.button('清空原始数据文件'):
            if os.path.exists("data.txt"):
                os.remove("data.txt")
                st.success("数据文件已清空")

        if st.button('清空csv目录下所有文件'):
            folder_path = "csv"
            if os.path.exists(folder_path):
                for file in os.listdir(folder_path):
                    os.remove(os.path.join(folder_path, file))
                st.success("CSV目录下的所有文件已清空")

    with col6:
        if os.path.exists("data.txt"):
            with open("data.txt", "rb") as file:
                st.download_button(
                    label="下载原始数据文件",
                    data=file,
                    file_name="data.txt",
                    mime="text/plain"
                )
        else:
            st.warning("数据文件不存在")

        if st.session_state["csv_name"]:
            csv_path = f"csv/{st.session_state['csv_name']}"
            if os.path.exists(csv_path):
                with open(csv_path, "rb") as file:
                    st.download_button(
                        label="下载当前CSV文件",
                        data=file,
                        file_name=st.session_state["csv_name"],
                        mime="text/csv"
                    )
            else:
                st.warning("当前CSV文件不存在")

        folder_path = "csv"
        if os.path.isdir(folder_path):
            zip_bytes = create_zip_file(folder_path)
            st.download_button(
                label="下载所有CSV文件的ZIP",
                data=zip_bytes,
                file_name=f'{os.path.basename(folder_path)}.zip',
                mime='application/zip'
            )
        else:
            st.warning("CSV目录不存在")

st.title('数据可视化')

step = st.number_input("输入纵坐标单位长度:", min_value=0.0000, max_value=20.0000, value=0.0000, step=0.0001, format="%.4f")

if st.button('Convert'):
    result_df = st.session_state["df_data"]
    if result_df is not None:
        data_chart = alt.Chart(result_df).mark_line().encode(
            x=alt.X('Index:Q', title='Index', scale=alt.Scale(zero=False)),
            y=alt.Y('Decimal Value:Q', title='Decimal Value', scale=alt.Scale(nice=True))
        ).properties(
            width=800,
            height=400
        )

        if step > 0:
            data_chart = data_chart.encode(y=alt.Y('Decimal Value:Q', scale=alt.Scale(nice=True, domain=[0, step * len(result_df) // 10])))

        st.altair_chart(data_chart, use_container_width=True)
    else:
        st.warning("请先发送数据")
