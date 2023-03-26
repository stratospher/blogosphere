Here's a writeup of the implementation details used in the test framework.
(Note: v2 P2P refers to the encrypted P2P transport protocol proposed in BIP 324)

## Need
We need a way in the functional test framework to make sure that v2 P2P enabled bitcoind process exhibits behaviour intended in BIP 324.
Example:
1. actually communicates on V2 P2P protocol (depending on whether the node you're connected to supports v2 P2P or not)
2. whether v2 P2P protocol is backward compatible with nodes communicating on v1 P2P protocol
3. whether traffic shaping during initial v2 handshake works
4. whether initial v2 handshake works as intended - [one such example](https://github.com/bitcoin/bips/blob/master/bip-0324.mediawiki#signaling-v2-support), if both our nodes run BIP 324 and i send you ellswift bytes, you should respond back only when mismatch from V1_PREFIX occurs.
5. whether we can send decoy messages
6. behaviour during false advertisement of v2 P2P support etc.

These require a way to pause and examine whether bitcoind process has sent/received correct responses, and so we need to extend BIP 324 support to `P2PConnection`.

## Basics
1. `TestNode` vs `P2PConnection` - ``TestNode`` runs an actual bitcoind process and `P2PConnection` is a class to make inbound/outbound connections to/from the `TestNode` which would mimic the behaviour of a peer and allow us to pause/examine responses.
2. Inbound connections to the `TestNode` are made using `add_p2p_connection()`
    - `TestNode` <---------- `P2PConnection`
    - Here, `P2PConnection` is the initiator of the connection
3. Outbound connections from the `TestNode` are made using `add_outbound_p2p_connection()`
    - `TestNode` ----------> `P2PConnection`
    - Here, `TestNode` is the initiator of the connection
4. A node advertising support for v2 P2P(using `NODE_P2P_V2` service flag) is different from a node actually supporting v2 P2P.
   ### supporting v2 P2P
    - since this branch is built on top of #24545, `TestNode`(a bitcoind process) supports v2 P2P.
    - we'd need additional options in `P2PConnection` so that we know if it supports v2 P2P or not.
   ### advertising to support v2 P2P
    - the node could be falsely advertised to support encrypted P2P transport when it actually doesn't support encrypted v2 P2P.
    - in the real world, the only way to know for sure if the other node supports BIP 324 is by sending it ellswift + garbage bytes and initiating v2 handshake to see if it actually responds. We initiate this v2 handshake based on the service flags this responder node advertises. But we can't know for sure until we actually establish a connection.
    - supposing it was falsely advertised to support v2 P2P by some intermediary, the responder node would terminate the connection. the initiator node would then have to reconnect using v1 P2P protocol. (See [BIP](https://github.com/bitcoin/bips/blob/master/bip-0324.mediawiki#signaling-v2-support))
    - In the test framework, we cannot test this false advertisement behaviour when the responder node is the actual bitcoind process(an inbound connection to the `TestNode` <---------- `P2PConnection`) since service advertisement is done using the CLI arg `"-v2transport=1"` and there's no false advertisement possible(in the test framework).
    - This false advertisement and reconnection property is however very important to ensure that no network partition happens and existing v1 P2P is always preserved for BIP 324 enabled nodes in the future.
    - by adding options in `P2PConnection` to falsely advertise v2 P2P support, it is possible to ensure the above-mentioned behaviour when the responder node is a `P2PConnection`(an Outbound connection from the `TestNode`). And since it's a transport protocol behaviour which has to be tested, we introduce a separate variable for this.
5. Ports
    - TODO
## Implementation details
1. `EncryptedP2PState` - we need a class which stores keys, session-id, functions to perform initial v2 handshake, encryption/decryption etc.
2. `v2_state` - `P2PConnection` needs an object of class `EncryptedP2PState` to store its keys, session-id etc.
3. `supports_v2_p2p` - boolean variable used by `P2PConnection` to denote if it supports v2 P2P.
4. CLI arg `"-v2transport=1"` - whether the `TestNode` running the actual bitcoind process signals/advertises V2 P2P support.
   - see [commit](https://github.com/bitcoin/bitcoin/pull/24545/commits/a5a83366a716b3ce68a9881cba27fbec6ea2b91f).
   - Default option is `False`.
5. `advertises_v2_p2p` - whether `P2PConnection` which mimics peer behaviour advertises V2 P2P support. Default option is `False`.
6. In the test framework, you can create Inbound and Outbound connections to `TestNode`
   1. During Inbound Connections, `P2PConnection` is the initiator [`TestNode` <--------- `P2PConnection`]
      - if the `TestNode` advertises/signals v2 P2P support (means `self.nodes[i]` set up with `"-v2transport=1"`), different behaviour will be exhibited based on whether:
        1. `P2PConnection` supports v2 P2P
        2. `P2PConnection` does not support v2 P2P
      - In a real world scenario, the initiator node would intrinsically know if they support v2 P2P based on whatever code they choose to run.
      - However, in the test scenario where we mimic peer behaviour, we have no way of knowing if `P2PConnection` should support v2 P2P or not.
      - we need an option to enable support for v2 P2P - this is done using the variable `supports_v2_p2p`
      - Since the `TestNode` advertises v2 P2P support (using `"-v2transport=1"`), our initiator `P2PConnection` would send:
        1. (if the `P2PConnection` supports v2 P2P) ellswift + garbage bytes to initiate the connection
        2. (if the `P2PConnection` does not support v2 P2P) version message to initiate the connection
      - if the `TestNode` doesn't signal v2 P2P support; `P2PConnection` being the initiator would send version message to initiate a connection.
   2. During Outbound Connections [`TestNode` --------> `P2PConnection`]
      - initiator `TestNode` would send:
         1. (if the `P2PConnection` advertises v2 P2P) ellswift + garbage bytes to initiate the connection
         2. (if the `P2PConnection` advertises v2 P2P) version message to initiate the connection
      - Suppose `P2PConnection` advertises v2 P2P support when it actually doesn't support v2 P2P (false advertisement scenario)
        - `TestNode` sends ellswift + garbage bytes
        - `P2PConnection` receives but can't process it and disconnects.
        - `TestNode` then tries using v1 P2P and sends version message
        - `P2PConnection` receives/processes this successfully and they communicate on v1 P2P