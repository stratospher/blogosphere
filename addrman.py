from hashlib import sha256

ADDRMAN_NEW_BUCKETS_PER_SOURCE_GROUP = 64
ADDRMAN_NEW_BUCKET_COUNT = 1024

def get_group_ipv4(ip):
    ip_as_bytes = bytes(map(int, ip.split('.')))
    return bytes([1]) + ip_as_bytes[:2]

def double_hash(bytes):
    return sha256(sha256(bytes).digest()).digest()

def get_new_bucket(key, addr, src):
    addr_group = get_group_ipv4(addr)
    src_group = get_group_ipv4(src)
    hash1 =  int.from_bytes(double_hash(key + bytes([len(addr_group)]) + addr_group
                                            + bytes([len(src_group)]) + src_group)[:8], 'little')
    hash1 = hash1 % ADDRMAN_NEW_BUCKETS_PER_SOURCE_GROUP #64
    hash2 = int.from_bytes(double_hash(key + bytes([len(src_group)]) + src_group
                                           + hash1.to_bytes(8, 'little'))[:8], 'little')
    return hash2 % ADDRMAN_NEW_BUCKET_COUNT #1024

key = bytes.fromhex("41f758f2e5cc078d3795b4fc0cb60c2d735fa92cc020572bdc982dd2d564d11b")
addr = "250.1.2.1"
src = "250.1.2.1"
bucket = get_new_bucket(key, addr, src)
print("bucket is", bucket) # 786

ADDRMAN_TRIED_BUCKETS_PER_GROUP = 8
ADDRMAN_TRIED_BUCKET_COUNT = 256
def get_key(ip, port):
    ip_as_bytes = bytes(map(int, ip.split('.')))
    print(ip_as_bytes.hex())
    print((port // 0x100).to_bytes(1, 'little').hex())
    print((port & 0x0FF).to_bytes(1, 'little').hex())
    return ip_as_bytes + (port // 0x100).to_bytes(1, 'little') + (port & 0x0FF).to_bytes(1, 'little')

def get_tried_bucket(key, addr, port):
    addr_group = get_group_ipv4(addr)
    addr_id = get_key(addr, port) #00000000000000000000ffff fa010101208d
    print(addr_id.hex())
    hash1 = int.from_bytes(double_hash(key + bytes([len(addr_id)]) + addr_id), 'little')
    hash1 = hash1 % ADDRMAN_TRIED_BUCKETS_PER_GROUP
    hash2 = int.from_bytes(double_hash(key + bytes([len(addr_group)]) + addr_group
                                           + hash1.to_bytes(8, 'little'))[:8], 'little')
    return hash2 % ADDRMAN_TRIED_BUCKET_COUNT

key = bytes.fromhex("1bd164d5d22d98dc2b5720c02ca95f732d0cb60cfcb495378d07cce5f258f741")
addr = "250.1.1.1"
port = 8333
src = "250.1.1.1"
bucket = get_tried_bucket(key, addr, port)
print("bucket is", bucket)
