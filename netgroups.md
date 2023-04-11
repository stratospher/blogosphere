# Netgroup diversification of outbound connections

Outbound connections are connections which the node initiates to peers.
Different types of outbound connections are mentioned in [enum ConnectionTypes](https://github.com/bitcoin/bitcoin/blob/master/src/node/connection_types.h#L25-L76).
They include OUTBOUND_FULL_RELAY, BLOCK_RELAY, MANUAL, ADDR_FETCH and FEELER connections.
## Outbound connections timeline
1. Outbound connections
   - always there, didn't have separate types in the early days
   - used to be simply identified by `!fInbound`
2. ADDR_FETCH
   - introduced in [#1141](https://github.com/bitcoin/bitcoin/commit/478b01d9a797f3ea41cca141992b161867a5996d)
   - renamed in [#19316](https://github.com/bitcoin/bitcoin/pull/19316/commits/3f1b7140e95d0f8f958cb35f31c3d964c57e484d) from oneshot to addrfetch
3. FEELER
   - introduced in [#8282](https://github.com/stratospher/bitcoin/commit/dbb1f640e67da25f0a41b9d2e696b789d2fd4e0d#diff-00021eed586a482abdb09d6cdada1d90115abe988a91421851960e26658bed02)
4. MANUAL
   - treated as separate connection type from  [#9319](https://github.com/bitcoin/bitcoin/commit/50bd12ce0c49e574a5baf1a8df3a667810c6ad1e#diff-00021eed586a482abdb09d6cdada1d90115abe988a91421851960e26658bed02) 
   - concept existed from [#1549](https://github.com/bitcoin/bitcoin/pull/1549) though (pass the peers to `ConnectNode()`) 
5. BLOCK_RELAY
   - introduced in [#15759](https://github.com/stratospher/bitcoin/commit/3a5e885306ea954d7eccdc11502e91a51dab8ec6)

## Netgroup

### Route based diversification
### 1. IPV4
- IPV4 address is made of 4 chunks (8 bits/1 byte each)
````
def get_group_ipv4(ip):
  ip_as_bytes = bytes(map(int, ip.split('.')))
  return bytes([1]) + ip_as_bytes[:2]

print("ipv4", get_group_ipv4("1.2.3.4").hex()) # prints 010102
# 01   = network class of ipv4
# 0102 = first 2 bytes of ipv4 address
# since 16 bits are variable, 2^16 possible netgroups
````
### 2. IPV6
- IPV6 address is made of 8 chunks (16 bits/2 bytes each)
```
def get_group_ipv6(ip):
   ip_as_bytes = bytes.fromhex(ip.replace(':',''))
   return bytes([2]) + ip_as_bytes[:4]

print("ipv6", get_group_ipv6("2001:2001:9999:9999:9999:9999:9999:9999").hex()) # prints 0220012001
# 02        = network class of ipv6
# 20012001  = first 4 bytes of ipv6 address
# since 32 bits are variable, 2^32 possible netgroups
```
### 3. Tor
*Construction*
- tor addresses are public key based addresses and interestingly constructed
- we choose a `PUBKEY` - 32 bytes ed25519 master pubkey of the hidden service
- Tor v3 addresses have `VERSION` = 3 (v2 onion services are no longer supported)
- `VERSION` is a one byte version field
- `CHECKSUM` is calculated using `CHECKSUM = H(".onion checksum" | PUBKEY | VERSION)[:2]`
- notice how it's truncated to 2 bytes
- Hash function(H) used is `sha3_256` ([SHA-3 "Keccak" hashes family was winner in SHA-3 NIST competition 2013.](https://cryptobook.nakov.com/cryptographic-hash-functions/secure-hash-algorithms#sha-3-sha3-256-sha3-512-keccak-256))
- `onion_address = base32(PUBKEY | CHECKSUM | VERSION) + ".onion"`
- this is how a Tor v3 address is constructed.
- without ".onion", length of Tor v3 address = length of base32(32 bytes + 2 bytes + 1 byte) = length of base32(35 bytes)
- base32 maps 8 bits to 5 bits. 35 bytes has 35*8 bits which gets grouped into groups of 5 bits and then mapped to base32 characters.
- number of base32 characters = 35*8/5 = 56 characters
- so a Tor v3 address is 56 characters long.
- since last 5 bits of address is `VERSION`=3 (00011) and in [base32 encoding](https://www.rfc-editor.org/rfc/rfc4648#section-6) `3` maps to `d`.
- so a tor v3 address will always end in a `d`.
- [see](https://github.com/bitcoin/bitcoin/blob/35fbc972082eca0fc848fba77360ff35f1ba69e1/src/netaddress.cpp#L225-L262) how tor address is decoded and `m_addr` stores its pubkey(and not address bytes) in bitcoin core.

*Netgroup*
- doesn't conceptually make sense since Tor addresses are public key based and not routing based.
- netgroup uses first 4 bits of pubkey (and not address, unlike ipv4/ipv6)
```
def get_group_tor(ip):
    ip = ip.replace('.onion','')
    raw_bytes = b32decode(ip, casefold=True)
    pubkey, checksum, version = raw_bytes[:32], raw_bytes[32:34], raw_bytes[-1:]
    assert version == b'\x03'
    assert checksum == sha3_256(b".onion checksum" + pubkey + version).digest()[:2]
    return bytes([3]) + bytes([pubkey[0]|0xf]) # only first 4 bits of 1st byte of pubkey taken

print("tor", get_group_tor("pg6mmjiyjmcrsslvykfwnntlaru7p5svn6y2ymmju6nubxndf4pscryd.onion").hex()) # prints 037f
# 03        = network class of Tor
# 7         = first 4 bits of Tor address
# f         = last 4 bits is set to 1111 (only first 4 bits used in netgroup logic)
# since 4 bits are variable, 2^4 possible netgroups
```
### 4. I2P
- I2P addresses are also public key based addresses.
- There are 2 kinds of I2P addresses:
   1. b32 address = standard b32 I2P address (52 base32 characters)
                  = 256 bit sha256 hash of destination 
   2. [b33 address](https://geti2p.net/spec/b32encrypted) = addresses for encrypted LS (56+ base32 characters)
- bitcoin core supports traditional b32 I2P addresses
- base32 maps 8 bits to 5 bits. 256 bits get grouped into groups of 5 bits and then mapped to base32 characters.
- number of base32 characters = 256/5 = 51.2 characters
- if we pad 4 bits (we pad using `=` to make length a multiple of 5), (256+4)/5 = 52 base32 characters
- see [construction](https://github.com/bitcoin/bitcoin/blob/master/src/i2p.cpp#L80-L100) of .b32.i2p address from an I2P destination in bitcoin core
- [see](https://github.com/bitcoin/bitcoin/blob/35fbc972082eca0fc848fba77360ff35f1ba69e1/src/netaddress.cpp#L264-L289) how I2P address is decoded and `m_addr` stores its address bytes in bitcoin core.
- netgroup uses first 4 bits of b32decoded I2P address
```
def get_group_i2p(ip):
  ip = ip.replace('.b32.i2p','')
  raw_bytes = b32decode(ip+"====", casefold=True) # pad so that b32decode works
  return bytes([4]) + bytes([raw_bytes[0]|0xf])
 
print("i2p", get_group_i2p("ukeu3k5oycgaauneqgtnvselmt4yemvoilkln7jpvamvfx7dnkdq.b32.i2p").hex()) # prints 04af
# 04     = network class of I2P
# a      = first 4 bits of I2P address
# f      = last 4 bits is set to 1111 (only first 4 bits used in netgroup logic)
# since 4 bits are variable, 2^4 possible netgroups
```
### 5. CJDNS
- CJDNS addresses are also public key based addresses
- CJDNS IPv6 address is generated by using the first 16 bytes of a double SHA-512 of your public key
- All CJDNS IPv6 addresses must begin with "fc" or else they are invalid
- netgroup uses first 12 bits of CJDNS address
```
def get_group_cjdns(ip):
   ip_as_bytes = bytes.fromhex(ip.replace(':',''))
   return bytes([5]) + bytes([ip_as_bytes[0]]) + bytes([ip_as_bytes[1]|0xf])

print("cjdns", get_group_cjdns("fc4b:50:7661:cccd:8697:40a4:5498:c51c")) # prints 05fc4f
# 05     = network class of CJDNS
# fc4    = first 12 bits of CJDNS address
# f      = last 4 bits is set to 1111 (only first 12 bits used in netgroup logic)
# since 4 bits are variable, 2^4 possible netgroups
```
## Bucketing algorithm in addrman

### 1. new table
- key  = secret key to randomize bucket selection with
- addr = IP address
- src  = IP address of source of addr
- addr, src are assumed to be IPV4 addresses in the below code snippet
- see [implementation](https://github.com/bitcoin/bitcoin/blob/master/src/addrman.cpp#L53-L59) in bitcoin core
```
def get_new_bucket(key, addr, src):
    addr_group = get_group_ipv4(addr)
    src_group = get_group_ipv4(src)
    hash1 =  int.from_bytes(double_hash(key + bytes([len(addr_group)]) + addr_group + bytes([len(src_group)]) + src_group)[:8], 'little')
    hash1 = hash1 % ADDRMAN_NEW_BUCKETS_PER_SOURCE_GROUP #64
    hash2 = int.from_bytes(double_hash(key + bytes([len(src_group)]) + src_group + hash1.to_bytes(8, 'little'))[:8], 'little')
    return hash2 % ADDRMAN_NEW_BUCKET_COUNT #1024
```
- new bucket selected is `hash2%1024`
- so we need to compute `hash1%64` first which is then used to compute `hash2%1024`
- since double hashing is collision resistant, number of possible values for:
    - `hash1` depends on number of unique combination of `addr_group` and `src_group`
    - `hash2` depends on number of unique combination of `hash1%64` and `src_group`

**_Steps to calculate number of possible new table buckets that can be filled_**: (used in table calculation below)
   1. compute number of possible values for `addr_group`(netgroup of IP address) and `src_group`(netgroup of source of IP address)
   2. number of possible values for `hash1` = number of possible values for `addr_group` * number of possible values for `src_group`
   3. number of possible values for `hash1%64` = 64 (if number of possible values for `hash1` >= 64, this is what happens in all cases evaluated below)
   4. since `src_group` is already chosen at this point, we calculate number of possible values for `hash1%64` for 1 `src_group`:
      * = number of possible values for `addr_group`
      * = 64 (if number of possible values for `addr_group` >= 64) (todo: note about how we limit dependent varai)
   5. `hash2` depends on number of unique combination of `hash1%64` and `src_group`
      * `src_group` has n possibilities
      * `hash1%64` for 1 `src_group` has  (number of possible values for `hash1%64` for 1 `src_group`) possibilities (from step 3)
      * `hash2` has n * (number of possible values for `hash1%64` for 1 `src_group`) possibilities
   6. number of possible values for `hash2%1024` = 1024 (if number of possible values for `hash2` >= 1024, otherwise it is the original value of `hash2` itself)

|                               | `src_group` is IPV4/IPV6                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    | `src_group` is Tor/I2P/CJDNS                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                            |
|-------------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `addr_group` is IPV4/IPV6     | <ol><li>`addr_group` is IPV4/IPV6 and `src_group` is IPV4/IPV6. Each has 2^16/2^32 possibilities based on IPV4/IPV6 address.</li><li>number of possible values for `hash1`<br>= number of possible values for `addr_group` * number of possible values for `src_group` (>=64)</li><li>number of possible values for `hash1%64` = 64</li><li>number of possible values for `hash1%64` for 1 `src_group`<br>= number of possible values for `addr_group`(this is >= 64) = 64</li><li>`hash2` depends on number of unique combination of `hash1%64` and `src_group`<br>= 64 * (2^16) or 64 * (2^32) (this is >= 1024)</li><li>number of possible values for `hash2%1024` = 1024</li><li>hence all 1024 buckets possible in new table</li></ol> | <ol><li>`addr_group` is IPV4/IPV6(2^16/2^32 possibilities based on IPV4/IPV6 address) and `src_group` is Tor/I2P/CJDNS (16 possibilities).</li><li>number of possible values for `hash1` <br>= number of possible values for `addr_group` * number of possible values for `src_group` (>=64)</li><li>number of possible values for `hash1%64` = 64</li><li>number of possible values for `hash1%64` for 1 `src_group`<br>= number of possible values for `addr_group`(this is >= 64) = 64</li><li>`hash2` depends on number of unique combination of `hash1%64` and `src_group`<br>= 64 * 16 (this is >= 1024)</li><li>number of possible values for `hash2%1024` = 1024</li><li>hence all 1024 buckets possible in new table</li></ol> |
| `addr_group` is Tor/I2P/CJDNS | <ol><li>`addr_group` is Tor/I2P/CJDNS (16 possibilities) and `src_group` is IPV4/IPV6(2^16/2^32 possibilities based on IPV4/IPV6 address).</li><li>number of possible values for `hash1`<br>= number of possible values for `addr_group` * number of possible values for `src_group` (>=64)</li><li>number of possible values for `hash1%64` = 64</li><li>number of possible values for `hash1%64` for 1 `src_group` = number of possible values for `addr_group` = 16</li><li>`hash2` depends on number of unique combination of `hash1%64` and `src_group`<br>= 16 * 2^16 or 16 * 2^32 (this is >= 1024)</li><li>number of possible values for `hash2%1024` = 1024</li><li>hence all 1024 buckets possible in new table</li></ol>         | <ol><li>`addr_group` is Tor/I2P/CJDNS (16 possibilities) and `src_group` is Tor/I2P/CJDNS (16 possibilities).</li><li>number of possible values for `hash1`<br>= number of possible values for `addr_group` * number of possible values for `src_group` (>=64)</li><li>number of possible values for `hash1%64` = 64</li><li>number of possible values for `hash1%64` for 1 `src_group` = number of possible values for `addr_group` = 16</li><li>`hash2` depends on number of unique combination of `hash1%64` and `src_group`<br>= 16 * 16 (this is < 1024)</li><li>number of possible values for `hash2%1024` = 256</li><li>hence only 256 buckets possible in new table (256/1024 = 1/4 new table occupied)</li></ol>               |

### 2. tried table
```
def get_key(ip, port):
    ip_as_bytes = bytes(map(int, ip.split('.')))
    return ip_as_bytes + (port // 0x100).to_bytes(1, 'little') + (port & 0x0FF).to_bytes(1, 'little')

def get_tried_bucket(key, addr, port):
    addr_group = get_group_ipv4(addr)
    addr_id = get_key(addr, port) #00000000000000000000ffff fa010101208d
    hash1 = int.from_bytes(double_hash(key + bytes([len(addr_id)]) + addr_id), 'little')
    hash1 = hash1 % ADDRMAN_TRIED_BUCKETS_PER_GROUP # 8
    hash2 = int.from_bytes(double_hash(key + bytes([len(addr_group)]) + addr_group + hash1.to_bytes(8, 'little'))[:8], 'little')
    return hash2 % ADDRMAN_TRIED_BUCKET_COUNT # 256
```
- tried bucket selected is `hash2%256`
- so we need to compute `hash1%8` first which is then used to compute `hash2%256`
- `hash1` depends on IP address and port itself - which would obviously be greater than 8 possibilities
- so `hash1%8` has 8 possibilities
- `hash2` depends on `hash1` and `addr_group`
- IP address is:
  1. IPV4/IPV6 address
        - `addr_group` has 2 ** 16 possibilities if IPV4 address (uses 1st 2 bytes/16 bits of IPV4 address)
        - `addr_group` has 2 ** 32 possibilities if IPV6 address (uses 1st 4 bytes/32 bits of IPV6 address)
        - since `hash2` depends on `hash1` and `addr_group`, `hash2` would have 8 * (2 ** 16) and 8 * (2 ** 32) possibilities respectively
        - these are anyways greater than 256, `hash2%256` could result in any of the 256 possibilities [0, 255]
        - hence all 256 buckets possible in tried table
  2. Tor/I2P/CJDNS address
        - `addr_group` has `2**4` possibilities (uses 4 bits from address which are variable)
        - since `hash2` depends on `hash1` and `addr_group`, `hash2` would have 8 * (2 ** 4) = 128 possibilities
        - this is < 256, `hash2%256` could result in 128 possibilities
        - this is 128/256 = 1/2 buckets possible in tried table
  
## Netgroup diversification of outbound connections