import socket

# 创建UDP套接字
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

# 服务器的IP地址和端口号
server_address = ('192.168.18.200', 56119)

# 发送数据
message = b'\x28\x5A\x01'
sock.sendto(message, server_address)

# 接收服务器的响应
data, server = sock.recvfrom(4096)
print(f"Received: {data} from {server}")

# 关闭套接字
sock.close()