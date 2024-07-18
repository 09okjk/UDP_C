import streamlit as st
import socket
from datetime import datetime
import binascii
import time
import os

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
        ip = hex_response[28:40] if len(hex_response) > 40 else '00000000'
        return header, command, channel, length, mac, ip
    elif command == '04':
        switch_status = hex_response[6:8]
        return switch_status
    return header, command

def log_data_to_file(timestamp, channel,length, data_packet):
    a_response = binascii.hexlify(data_packet).decode()
    data = a_response[16:len(a_response)]
    with open("data.txt", "a") as file:
        file.write(f"{timestamp}\n")
        file.write(f"Channel: {channel}\n")
        file.write(f"Length: {length}\n")
        file.write(f"Data Packet: {data}\n")
        file.write("\n")

def run_sampling_loop(sock, address, f_header):
    response_count = 0
    response_count_placeholder = st.empty()
    
    while st.session_state["sampling_status"] == "on":
        fourth_dialogue_data = f_header + b'\x02' + bytes.fromhex(st.session_state["channel"]) + bytes.fromhex(st.session_state["length"]) + bytes.fromhex(st.session_state["mac"]) + bytes.fromhex(st.session_state["ip"])
        fourth_response = send_and_receive_udp(sock, fourth_dialogue_data, address, st.session_state["timeout"])
        
        if fourth_response:
            response_count += 1
            response_count_placeholder.write(f"接收到的数据包数量: {response_count}")
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            log_data_to_file(timestamp, st.session_state["channel"],st.session_state["length"], fourth_response)

        time.sleep(st.session_state["sleeptime"])

st.title("数据接收处理")

# 初始化 session_state
if "sampling_status" not in st.session_state:
    st.session_state["sampling_status"] = "off"
if "connection_verified" not in st.session_state:
    st.session_state["connection_verified"] = False
if "timeout" not in st.session_state:
    st.session_state["timeout"] = 30  # 默认超时时间为30秒
if "sleeptime" not in st.session_state:
    st.session_state["sleeptime"] = 10  # 默认超时时间为30秒

# 获得用户输入的IP地址、端口号和采样率
col1, col2 = st.columns(2)
with col1:
    ip_address = st.text_input("输入IP地址:")
    timeout = st.number_input("设置数据接收超时时间(秒):", min_value=1, value=30)
with col2:
    port = st.number_input("输入端口号:", min_value=1, max_value=65535, value=1234)
    sleep_time = st.number_input("设置采样间隔时间(秒):", min_value=1, value=10)
sample_rate = st.selectbox("选择采样频率", ['256k', '128k', '64k', '8k'])

f_header = b'\x28\x5A'
hz_dict = {'256k': '00', '128k': '01', '64k': '02', '8k': '03'}
switch_dict = {'on': '00', 'off': '01'}

col3, col4 = st.columns(2)
with col3:
    if st.button('提交'):
        if not ip_address:
            st.error("IP地址不能为空")
        elif port == 0:
            st.error("端口号不能为空")
        else:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                # 获取物理地址和ip地址
                first_dialogue_data = f_header + b'\x01'
                first_response = send_and_receive_udp(sock, first_dialogue_data, (ip_address, port), timeout)
                
                if first_response:
                    header, command, channel, length, mac, ip = parse_response(first_response)
                    
                    # 保存这些变量到 session_state
                    st.session_state["channel"] = channel
                    st.session_state["length"] = length
                    st.session_state["mac"] = mac
                    st.session_state["ip"] = ip
                    
                    # 采样频率设置
                    second_dialogue_data = f_header + b'\x03' + bytes.fromhex(hz_dict[sample_rate])
                    second_response = send_and_receive_udp(sock, second_dialogue_data, (ip_address, port), timeout)
                    
                    if second_response:
                        st.session_state["connection_verified"] = True
                        st.session_state["timeout"] = timeout
                        st.session_state["sleeptime"] = sleep_time
                        st.success("连接成功，可以开始采集数据")
                    else:
                        st.session_state["connection_verified"] = False
                else:
                    st.session_state["connection_verified"] = False

with col4:
    if st.session_state["connection_verified"]:
        if st.button('切换采集状态(开/关)'):
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock: 
                # 振动采集开关设置
                new_status = "off" if st.session_state["sampling_status"] == "on" else "on"
                third_dialogue_data = f_header + b'\x04' + bytes.fromhex(switch_dict[new_status])
                status = parse_response(send_and_receive_udp(sock, third_dialogue_data, (ip_address, port), st.session_state["timeout"]))
                
                if status == "00":  # 成功开启
                    st.session_state["sampling_status"] = "on"
                    st.success("采集器开启")
                elif status == "01":  # 成功关闭
                    st.session_state["sampling_status"] = "off"
                    st.warning("采集器关闭")

                time.sleep(0.5)

                if st.session_state["sampling_status"] == "on":
                    run_sampling_loop(sock, (ip_address, port), f_header)
            
    else:
        st.info("请先点击提交按钮并确保连接成功")
st.write("---")

# 清空数据文件
if st.button('清空数据文件'):
    if os.path.exists("data.txt"):
        os.remove("data.txt")
        st.success("数据文件已清空")
    else:
        st.warning("数据文件不存在")

# 下载数据文件
if os.path.exists("data.txt"):
    with open("data.txt", "rb") as file:
        btn = st.download_button(
            label="下载数据文件",
            data=file,
            file_name="data.txt",
            mime="text/plain"
        )
else:
    st.warning("数据文件不存在")