import math
from struct import pack, unpack

data1 = bytes.fromhex("64 68 1E 0C 13 04 7E 0C 34 09 28 04 00 19 00")
data2 = bytes.fromhex("00 00 15 04 E2 03 00 00 00 00 E4 03 00 16 00")
data3 = bytes.fromhex("00 00 47 09 E2 03 00 00 00 00 E4 03 00 16 00")

v2 = unpack("<2B4HBBBBB", data2)
v3 = unpack("<2B4HBBBBB", data3)

hum2 = round(15*math.log2(v2[2]) - 75, 2)
hum3 = round(15*math.log2(v3[2]) - 75, 2)

#print(f"Trigger1: {v[0]}")
#print(f"Trigger2: {v[1]} {v[1] % 16} ")
print(f"Humidity: {v2[2]} - {hum2}")
print(f"Humidity: {v3[2]} - {hum3}")
#print(f"Gas: {v[3]}")
#print(f"Light: {v[4]}")