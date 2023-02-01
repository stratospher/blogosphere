import hashlib

ADDRMAN_NEW_BUCKETS_PER_SOURCE_GROUP = 64
ADDRMAN_NEW_BUCKET_COUNT = 1024

def get_group(ip):
    ip_as_bytes = bytes(map(int, ip.split('.')))
    return bytes([1]) + ip_as_bytes[:2]

def get_new_bucket(key, addr, src):
    single_hash1 = hashlib.sha256(key + (3).to_bytes(1,'big') + get_group(addr) + (3).to_bytes(1,'big') + get_group(src)).digest()
    #print("hash", single_hash1.hex()) # in c++ code: "4d56a13ae003f52efcd14ad513ac3a874916caf91f518612016d943199584c59"
    double_hash1 = hashlib.sha256(single_hash1).digest()
    #print("double", double_hash1.hex()) # in c++ code: "d2a744abb8cacd63d0466f0b4f7021d2662af06694c8a488726cfe5b9eaab89c"
    hash1 =  int.from_bytes(double_hash1[:8], 'little') % ADDRMAN_NEW_BUCKETS_PER_SOURCE_GROUP
    single_hash2 = hashlib.sha256(key + (3).to_bytes(1,'big') + get_group(addr) + hash1.to_bytes(8, 'little')).digest()
    double_hash2 = hashlib.sha256(single_hash2).digest()
    hash2 = int.from_bytes(double_hash2[:8], 'little')
    return hash2 % ADDRMAN_NEW_BUCKET_COUNT

single_hash1 = hashlib.sha256((1).to_bytes(4, 'little')).digest()
# print(single_hash1.hex())
double_hash1 = hashlib.sha256(single_hash1).digest()
# print(double_hash1.hex())
key = bytes.fromhex("41f758f2e5cc078d3795b4fc0cb60c2d735fa92cc020572bdc982dd2d564d11b")
addr = "250.1.2.1"
src = "250.1.2.1"
bucket = get_new_bucket(key, addr, src)
print("bucket is", bucket) # 786
