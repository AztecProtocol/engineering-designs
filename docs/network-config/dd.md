# Network Configuration Design Document

- Owner: @PhilWindle
- Target DD Approval Date: 2025-09-25
- Target Project Delivery Date: 2025-10-01

## Executive Summary

To make node configuration easier, we will provide the ability to specify a network on the command line. In tuen the node will request from a known GitHub location detals about the network it is running against.

## Introduction

The foundation want a simply way in which to store and serve some basic network configuration that will be retrieved by nodes on that network.

## Interface

A file will be served from the foundation's GitHub repository.

## Implementation

Node operators can specify `--network <network-name>` on the command line when they start their node. Alternatively they can provide the `NETWORK` environment variable with the same value.

When this argument is provided the node performs a lookup of basic information about the network such as where to find p2p bootnodes or state snapshots.

This information will be provided in the form of a json file, hosted at a known GitHub location owned by the foundation.

It will still be possible for an operator to override sections of the configuration with their own provided values. As an example, it is possible to override the `bootnodes` configuration by populating the `BOOTSTRAP_NODES` environment variable.

Parsing of this schema should be permissive, allowing for new keys to be added which a node at a given version is unaware of. In this case that node would continue to use it's previously provided values.

```
{
  "staging-public": { 
    "bootnodes": [ 
      "enr:-LO4QByYEImKOhVk1eW2haEtDs2hT5qv18c3kopfzUF18AcudF-vHjEZMSi8PQ9jiVJb7XjQeh4dKa7LCMixUoM4t0UEhWF6dGVjqDAwLTExMTU1MTExLTAwMDAwMDAwLTAtMjI3ODAyMzktMmRhOWY4MDGCaWSCdjSCaXCEI8mx0YlzZWNwMjU2azGhA7mqxGD1MiN_fXZO1xyF4hpN-DDeKYZH4p5a3HNZZqh0g3VkcIKd0A", "enr:-LO4QJ4muM-dC-5acMDxJotHyfDYfIDfpSCWY4zf1qsFNw_3MBZQnF9E-Sls4-vAJ1mjzr0J7zP96O6sAbSj2j4f2L4EhWF6dGVjqDAwLTExMTU1MTExLTAwMDAwMDAwLTAtMjI3ODAyMzktMmRhOWY4MDGCaWSCdjSCaXCEI_YzS4lzZWNwMjU2azGhAlCcUe4aoKJUqTDinwSFz7v-M7h1xHWDCtkQxBulmyo-g3VkcIKd0A", "enr:-LO4QLwNo4LfTH2SBERo6BecNf9OUkGPESpcZCpNjEBIUbVFZE-4JHR2-azPdYSSqrEbqoyUng_gN0uvKP_Y0I76WE8EhWF6dGVjqDAwLTExMTU1MTExLTAwMDAwMDAwLTAtMjI3ODAyMzktMmRhOWY4MDGCaWSCdjSCaXCEI7nykIlzZWNwMjU2azGhAsQLIIY2n2jwc-t1AoQXw0OxLACQakja5RSbwfKKAPrng3VkcIKd0A"
    ],
    "snapshots": [
      "https://storage.googleapis.com/aztec-testnet/snapshots/staging-public/",
      "https://another.provider.com/snapshots/staging-public/",
    ],
    "registryAddress": "0x2e48addca360da61e4d6c21ff2b1961af56eb83b",
    "feeAssetHandlerAddress": "0xb46dc3d91f849999330b6dd93473fa29fc45b076",
    "l1ChainId": 11155111
  },
  "staging-ignition": { 
    "bootnodes": [ 
      "enr:-LO4QIdX_xHV2gbbbFIKzh5p-EHTdo9AFe-7RQtPmE4iVh1nPl0JLbxJaMND0az-SWBLGRtcidhJ3qfqgHM2mwB6zgcEhWF6dGVjqDAwLTExMTU1MTExLTAwMDAwMDAwLTAtMjI3ODAyMzktMmRhOWY4MDGCaWSCdjSCaXCEI-yINolzZWNwMjU2azGhAmBLoVZQcZxzQXbEBFf-i_N6xdiHp1hMUXqZqqI4vrjfg3VkcIKd0A", "enr:-LO4QPlSjy2E9IcMJrm3pG0Mip1-vI_h1938EhHY3Uu3BvKIYY25tA0lS8AfKR_CKf19g24w9rDywcfbU1UlvhYtO_kEhWF6dGVjqDAwLTExMTU1MTExLTAwMDAwMDAwLTAtMjI3ODAyMzktMmRhOWY4MDGCaWSCdjSCaXCEIlloyIlzZWNwMjU2azGhA5-g_q23VshWq4a36nlaJz92kRSTzLhIRJjUS4A3OeYJg3VkcIKd0A", "enr:-LO4QPi-mMZ4_bLwQE9AB-vzVjwvfrmGtz59MuyClA2toznqC3m83Tz5dyVpVuDntKRfiNKA7iMUBL8EA7XNeAB8094EhWF6dGVjqDAwLTExMTU1MTExLTAwMDAwMDAwLTAtMjI3ODAyMzktMmRhOWY4MDGCaWSCdjSCaXCEIqgrUYlzZWNwMjU2azGhA4hb7dUIA0YfCCRGkKQAo7GXWoUXio_NzHdjzgi_5UU2g3VkcIKd0A"
    ],
    "snapshots": [
      "https://storage.googleapis.com/aztec-testnet/snapshots/staging-ignition/",
      "https://another.provider.com/snapshots/staging-ignition/",
    ],
    "registryAddress": "0x5f85fa0f40bc4b5ccd53c9f34258aa55d25cdde8",
    "feeAssetHandlerAddress": "0x67d645b0a3e053605ea861d7e8909be6669812c4",
    "l1ChainId": 11155111
  },
  "testnet": {
    "bootnodes": [ 
      "enr:-LO4QA4kHKdUJOirQ4NxtI-gjBNLRK1GPeKtmz664Uph-EqLW1B3EkCqu6ul5C7dejOBWbEWMOPZc07I0Bl8bmW5Vn0EhWF6dGVjqDAwLTExMTU1MTExLTAwMDAwMDAwLTAtMjI3ODAyMzktMmRhOWY4MDGCaWSCdjSCaXCEIlCfmYlzZWNwMjU2azGhAoRffgRFcK_rV5ddbmtUW9cyXrPwrDFL18OFRVejOOXDg3VkcIKd0A", "enr:-LO4QO3-kuKH3c-RgaxYBWk0PiV-97B4wnvHcgMxYpB-1WjoctKlpY3Fuh29AESLhBn1WtQXE-1G0Umo_VhTcu7bLloEhWF6dGVjqDAwLTExMTU1MTExLTAwMDAwMDAwLTAtMjI3ODAyMzktMmRhOWY4MDGCaWSCdjSCaXCEIicStolzZWNwMjU2azGhAxUvKI8xXnGpkj2VjRZk9VmMbtfHZUoszOvvl76qFrGeg3VkcIKd0A", "enr:-LO4QNTdBJe-2tIfXpzJmu4Tise0rRdPSn2gwQMtkVPe40szAdpWRgixGub2iUXMcxSQuQ8nkKh-GSvQpRKqw2XzUhQEhWF6dGVjqDAwLTExMTU1MTExLTAwMDAwMDAwLTAtMjI3ODAyMzktMmRhOWY4MDGCaWSCdjSCaXCEIrZz14lzZWNwMjU2azGhApwZiWnsA8TFqvz-sGDrgbi1AypT4QXJfFWdYOz2yeVtg3VkcIKd0A"
    ],
    "snapshots": [
      "https://storage.googleapis.com/aztec-testnet/snapshots/testnet/",
      "https://another.provider.com/snapshots/testnet/",
    ],
    "registryAddress": "0xc2f24280f5c7f4897370dfdeb30f79ded14f1c81",
    "feeAssetHandlerAddress": "0x50513c3713ffd33301e85f30d86ab764df421fe9",
    "l1ChainId": 11155111
  }
}
```

## Change Set

Fill in bullets for each area that will be affected by this change.

- [ ] Cryptography
- [ ] Noir
- [ ] Aztec.js
- [ ] PXE
- [ ] Aztec.nr
- [ ] Enshrined L2 Contracts
- [x] Sequencer
- [ ] AVM
- [ ] Public Kernel Circuits
- [ ] Rollup Circuits
- [ ] L1 Contracts
- [ ] Prover
- [ ] Economics
- [x] P2P Network
- [ ] DevOps

## Test Plan

Tests should be written that demonstrate the correct data is retrieved based on the provided network value. They shuold test that the schema is correctly interpreted. I should also be verified that operator provided values override those in the hosted file.

## Disclaimer

The information set out herein is for discussion purposes only and does not represent any binding indication or commitment by Aztec Labs and its employees to take any action whatsoever, including relating to the structure and/or any potential operation of the Aztec protocol or the protocol roadmap. In particular: (i) nothing in these projects, requests, or comments is intended to create any contractual or other form of legal relationship with Aztec Labs or third parties who engage with this AztecProtocol GitHub account (including, without limitation, by responding to a conversation or submitting comments) (ii) by engaging with any conversation or request, the relevant persons are consenting to Aztec Labs’ use and publication of such engagement and related information on an open-source basis (and agree that Aztec Labs will not treat such engagement and related information as confidential), and (iii) Aztec Labs is not under any duty to consider any or all engagements, and that consideration of such engagements and any decision to award grants or other rewards for any such engagement is entirely at Aztec Labs’ sole discretion. Please do not rely on any information on this account for any purpose - the development, release, and timing of any products, features, or functionality remains subject to change and is currently entirely hypothetical. Nothing on this account should be treated as an offer to sell any security or any other asset by Aztec Labs or its affiliates, and you should not rely on any content or comments for advice of any kind, including legal, investment, financial, tax, or other professional advice.
