# Intro

Achieving reliable block production across the network requires validators to successfully have blocks attested to and proven. One issue that can prevent this from happening is transaction availabiity. 

Unlike Ethereum, Aztec transactions are relatively large and computationally expensive to verify. As a result, it is infeasible to include them with block proposals as Ethereum does. This means that is validators and provers are unable to get access to the transactions contained within proposals, blocks can go unattested or unproven.

## Current Solution

When a block proposal is propagated around the network, any nodes that don't have the transactions associated with that proposal make requests to peers to retrieve those transactions. This is a best effort approach and is not guaranteed to be successful.

## Proposed Solution

The proposed solution is to encourage community run 'Supernodes'. Capable peers with high uptime and available bandwidth. The libp2p addresses of these supernodes would be listed as part of the publically available network configuration.

The operators of these supernodes will be able to configure:

1. Whether the supernode can be discovered over the discv5 protocol.
2. Whether the supernode will only allow connections to validators (requires an auth handshake).
3. All regular libp2p/gossipsub parameters such as the peering degree.

Other than that, a supernode is just a regular node like any other. But having a number of supernodes within the network can create an additional gossip overlay allowing message to flow quickly and reliably to critical participants.

1. Identification of Supernodes

Supernodes would be listed in the network configuration JSON file.

```JSON
  "testnet": {
    "bootnodes": [ 
      "..."
    ],
    "snapshots": [
      "..."
    ],
    "supernodes": [
      "/ip4/5.6.7.8/tcp/4242/p2p/QmYyQSo1c1Ym7orWxLYvCrM2EmxFTANf8wXmmE7DWjhx5N"
      "/ip4/1.2.3.4/tcp/4242/p2p/QmYyQSo1c1Ym7orWxLYvCrM2EnxFTANf8wXmmE7DWjhx5N"
    ],
    "registryAddress": "",
    "feeAssetHandlerAddress": "",
    "l1ChainId": 111555111
  }
```

2. Connection Process

As supernodes aren't discovered in the usual way, we will implement slightly different selection and connection logic. Nodes can configure a `TARGET_NUM_SUPERNODES`, defaulting to e.g. 2. Nodes that do so will continually attempt to maintain connections to `TARGET_NUM_SUPERNODES` randomly selected supernodes from the configuration.

Upon successful connection, the supernode may issue an authentication handshake request. This request is a superset of the status handshake request including an additional randomly generated field value challenge. Supernodes shouldn't issue this request if the connection is from another supernode.

```TS
const ourStatus = await this.createStatusMessage();
const authRequest = new AuthRequest(ourStatus, Fr.random());
```

Upon receipt of the auth request, a validator can choose to respond with a signature. The signature whould be over the challenge received in the request, prefixed by a domain separator.

```TS
export const VALIDATOR_AUTH_DOMAIN_SEPARATOR = 'Aztec Validator Challenge:';
getPayloadToSign(): Buffer32 {
  const fullChallenge = VALIDATOR_AUTH_DOMAIN_SEPARATOR + this.challenge.toString();
  return Buffer32.fromBuffer(keccak256(Buffer.from(fullChallenge, 'utf-8')));
}
```

Validators should only respond to auth requests from known Supernodes if they aish to keep their identity as a validator hidden.

3. Supernodes and Gossipsub

The ideal situation is that nodes send all received messages to all of their connected supernodes. To ensure this, we wil use the `directPeers` function of GossipSub. This is merely a publicly accessible `Set<string>` of PeerIds that are considered to always be in the mesh. Messages are always transmitted to `directPeers`, messages are always accepted from `directPeers` (unless invalid) and `directPeers` have relaxed levels of peer penalisation. Note this will be the case whether it's validators forwarding to supernodes or supernodes forwarding to other supernodes.

Supernodes will control the number of peers in their mesh using the usual method of gossipsub peering degree. Gossipsub and libp2p already provide sufficient configuration such that supernodes can accept many peers and maintain a large mesh.

The intention with this approach is that as soon as a validator receives any message over P2P, it is immediately sent to at least 1 supernode. From here it will very quickly be propagated around the supernode/validator overlay mesh. Messages originating from validators (block proposals and validators) in particular would be well served by the overlay.

4. Supernodes and Req/Resp

As stated above, when any node does not have transactions available for a block proposal, they initiate a series of requests to peers to retrieve those transactions. Validators that are connected to supernodes will include those supernodes as high performance or 'pinned' peers and request all missing data from them greatly increasing the probability of success.

5. Maintaining Supernode Connections

Connection managment between nodes and supernodes will be largely the same as existing connection management. The only difference being that on disconnection from a supernode, the supernode's PeerId will be removed from the `directPeers` collection within Gossipsub.
