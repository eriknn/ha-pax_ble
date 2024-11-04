import math
from struct import pack, unpack

data = bytes.fromhex("64 68 1E 0C 13 04 7E 0C 34 09 28 04 00 19 00")
v = unpack("<2B4HBBBBB", data)

hum = round(math.log2(v[2] - 30) * 10, 2)

print(v[4])
print(hum)