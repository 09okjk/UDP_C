import csv
import pandas as pd

def hex_to_decimal_and_save(data_packet, output_file):
    # 确保数据包的长度可以被8整除
    if len(data_packet) % 8 != 0:
        raise ValueError("The length of data_packet must be divisible by 8.")
    
    # 将数据包切分为每8个字符一组
    hex_values = [data_packet[i:i+8] for i in range(0, len(data_packet), 8)]
    
    # 转换十六进制值为十进制
    decimal_values = [int(value, 16)/10000 for value in hex_values]

    # 创建DataFrame
    df = pd.DataFrame({
        'Index': list(range(len(decimal_values))),
        'Decimal Value': decimal_values
    })
    
    # 写入CSV文件
    with open(output_file, mode='w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(['Index', 'Decimal Value'])
        for index, value in enumerate(decimal_values):
            writer.writerow([index+1, value])

# 使用示例
data_packet = "000211320002112000021126000211360002112c0002113b0002113d0002116200021182000211740002113e0002112f000211610002115b0002116400021165000211230002110b00021140000211610002113a"
output_file = "output.csv"

hex_to_decimal_and_save(data_packet, output_file)