|                      |                                   |
| -------------------- | --------------------------------- |
| Issue                | [Native Merkle Trees](https://github.com/AztecProtocol/aztec-packages/issues/5040) |
| Owners               | @alexghr @PhilWindle |
| Approvers            | @just-mitch @spalladino @ludamad @charlielye @fcarreiro |
| Target Approval Date | 2024-07-05 |

## Executive Summary

This document proposes integrating the [Native Merkle Trees database](https://github.com/AztecProtocol/engineering-designs/blob/f9d1a897303c1481c790cecc4616961e1c183622/in-progress/0003-native-merkle-trees.md) directly into the TypeScript project using a native module written in C++ using [Node-API](https://nodejs.org/docs/latest-v18.x/api/n-api.html) rather than message passing.

## Introduction

The original native Merkle tree spec proposed building a `MerkleTreesDb` native binary in C++. The TypeScript code would use message passing over streams to communicate with the database. A long lived process would be started once and accept messages over an input stream (e.g. stdin or a socket), process the messages and return the result over another stream (e.g. stdout).

[Node-API](https://nodejs.org/docs/latest-v18.x/api/n-api.html) is an API for building native addons that integrate seamlessly into NodeJS.

This approach would simplify deployment and maintenance (no new binaries need to be managed/started) while providing an easier to use interface from the TypeScript side.

## Interface

A new module would be written in C++ that would adapt the existing Native Merkle Trees database to Node-API semantics. This module could sit alongside the stream-based message passing implementation detailed in the [original spec](https://github.com/AztecProtocol/engineering-designs/blob/f9d1a897303c1481c790cecc4616961e1c183622/in-progress/0003-native-merkle-trees.md#interface)

This module would be built with CMake normally as the rest of the C++ code, with the exception that its build artifact would be a shared library (with a custom extension `.node` instead of `.so`). The TypeScript project would use [`bindings`](https://www.npmjs.com/package/bindings) to load the native module and re-export the functions and classes from C++.

> [!NOTE]
> TypeScript definitions would have to be written from the C++ code. Ideally these would be generated from existing code, but if that doesn't work then they would have to be written and maintained manually.

## Implementation

The implementation would use the [Node Addon API](https://github.com/nodejs/node-addon-api) instead of Node-API directly. Node Addon API is a C++ wrapper (by the Nodejs team) of N-API and exposes an object oriented interface to N-API.

```tree
barretenberg/cpp/src/barretenberg
# other modules
├── crypto
│   └── merkle_tree     # tree implementations, leaf types, lmdb integration, etc
├── world_state         # equivalent of MerkleTrees from TypeScript
├── world_state_napi    # <--- the proposed new module
└── world_state_service # binary using message passing
```

### Addon

The module would export a single Addon class:

```cpp
// world_state_addon.hpp
class WorldStateAddon : public Napi::ObjectWrap<WorldStateAddon> {
  public:
    WorldStateAddon(const Napi::CallbackInfo&);

    Napi::Value getTreeMetaData(const Napi::CallbackInfo&);
    Napi::Value getSiblingPath(const Napi::CallbackInfo&);
    // etc other methods from the public API of [MerkleTrees in TS](https://github.com/AztecProtocol/aztec-packages/blob/88d43e753079f9b0c263b655bfd779c2098e9097/yarn-project/world-state/src/world-state-db/merkle_trees.ts)

    static Napi::Function get_class(Napi::Env);

  private:
    std::unique_ptr<bb::world_state::WorldStateService> _world_state_svc;
};
```

```cpp
// world_state_addon.cpp
WorldStateAddon::WorldStateAddon(const Napi::CallbackInfo& info)
    : ObjectWrap(info)
{
    Napi::Env env = info.Env();

    if (info.Length() < 1) {
        Napi::TypeError::New(env, "Wrong number of arguments").ThrowAsJavaScriptException();
        return;
    }

    if (!info[0].IsString()) {
        Napi::TypeError::New(env, "Directory needs to be a string").ThrowAsJavaScriptException();
        return;
    }

    std::string data_dir = info[0].ToString();
    _world_state_svc = std::make_unique<bb::world_state::WorldStateService>(data_dir);
}

Napi::Value WorldStateAddon::getLeafValue(const Napi::CallbackInfo& info)
{
  auto env = info.Env();
  Napi::Promise::Deferred deferred(env);

  auto tree_id = info[0].As<Napi::String>();
  bool lossy;
  bb::crypto::merkle_tree::index_t leaf_index = info[0].As<Napi::BigInt>().Uint64Value(&lossy);
  if (lossy) {
    deferred.Reject(Napi::TypeError::New(env, "Invalid leaf index").Value());
    return deferred.Promise();
  }

  bool include_uncomitted = info[2].As<Napi::Boolean>();

  // pointer to helper class for async code (gets cleaned up later), see below
  auto* tree_op = new bb::world_state::TreeOp(env, deferred, [=]() {
    bb::crypto::merkle_tree::Signal signal(1);
    bb::fr leaf(0);
    auto callback = [&](bb::fr& value) {
      leaf = value;
      signal.signal_level(0);
    };
    // for illustration purposes only, actual function call will be different
    _world_state_svc[tree_id].get_leaf_value(leaf_index, include_uncomitted, callback);
    signal.wait_for_level(0);
    return leaf;
  });

  tree_op ->Queue();

  return deferred.Promise();
}
// etc.

// init the module
Napi::Function WorldStateAddon::get_class(Napi::Env env)
{
    return DefineClass(env, "WorldState",
      {
          WorldStateAddon::InstanceMethod("getLeafValue", &WorldStateAddon::getLeafValue),
          // other instance methods
      });
}

Napi::Object Init(Napi::Env env, Napi::Object exports)
{
    Napi::String name = Napi::String::New(env, "WorldState");
    exports.Set(name, WorldStateAddon::get_class(env));
    return exports;
}

NODE_API_MODULE(addon, Init)
```

> [!NOTE]
> The instance methods on the C++ class will be exported as instance methods on the JavaScript instance too.
> Instance methods _must_ return a Napi::Value (ie. `any` in TS-land), even though the method returns something more specific (e.g. a Promise) and accept a single Napi::Callback parameter.
> Instance methods can not be `const`.

The equivalent TS code would look like this:

```ts
const bindings = require('bindings'); // from the bindings npm package
const { WorldState }= bindings('world_state_napi'); // looks for the dynamic library named world_state_napi.node in a set of known folders (relative to package.json)

async function main() {
  const worldState = new WorldState('./data'); // WorldState is the name under which the C++ class was exported
  const firstLeaf = await worldState.getLeafValue("notes_tree", 0, false);
  console.log(Fr.fromString(firstLeaf));

  await worldState.handleL2BlockAndMessages(L2Block.random(), []);
  console.log(Fr.fromString(await worldState.getLeafValue('notes_tree', 0, false)));
} // as soon as main finishes executing, `worldState` goes out of scope and at some point gets garbage collected which in turn calls its C++ destructor.

main();
```

### Classes & instances

Exported classes from the C++ side can be used an instantiated from NodeJS. Node Addon API is responsible for the glue code that ties to two together (ie. calling a function on the JS object calls the appropriate function in C++). The JS instance is a reference to the instance inside C++. The C++ instance is able to refer instantiate any other classes or allocate and access as much memory as needed.

When an instance is garbage collected on the TS-side, the destructor is called on the C++ side.

### Passing data between NodeJS and C++

The `Napi` namespace on the C++ contains helper classes to deal with JS primitive values. Strings, numbers, bigints, buffers, arrays, typed arrays and even functions can be freely passed between the two environments.

More complex data structures must be serialized/deserialized. We will msgpack for this as it's already implemented in the C++ code

[`Napi::Value` documentation](https://github.com/nodejs/node-addon-api/blob/cc06369aa4dd29e585600b8b47839c1297df962d/doc/value.md)

### Message passing

Instead of exporting a functions for each operation on the world state, we could instead leverage the existing message passing interface, only instead sending the message across the TS/C++ boundary. This would simplify the module initialization code on the C++ side (only requiring we export a single function) and we'd benefit from easily serializing data types with msgpack.

### Async code

The C++ code gets executed on the main Nodejs thread. Care has to be taken not to block the thread since that would prevent other JS code from running until the callback is finished.

Running normal async code on the main thread is not supported:

```cpp
Napi::Value WorldStateAddon::getMetaData(const Napi::CallbackInfo& info)
{
  Napi::Promise::Deferred deferred(env);
  bb::crypto::merkle_tree::Signal signal(1);

  // getting the meta data directly from a merkle tree using callbacks
  auto completion = [&](const std::string&, uint32_t, const bb::crypto::merkle_tree::index_t&, const bb::fr& r) -> void
  {
    deferred.Resolve(Napi::String::New(env, format(r)));
    signal.signal_level(0);
  };

  _notes_tree->get_meta_data(false, completion);
  signal.wait_for_level(0);

  return deferred.Promise();
}
```

In the context of running inside the Nodejs runtime the code above has undefined behavior. It could segfault or hang indefinitely.

The correct way of running async operations is to wrap the code in an [AsyncWorker](https://github.com/nodejs/node-addon-api/blob/cc06369aa4dd29e585600b8b47839c1297df962d/doc/async_worker.md) so that the Nodejs runtime can track its execution properly:

```cpp
using tree_op_callback = std::function<bb::fr()>;
class TreeOp : public AsyncWorker {
  public:
    TreeOp(Napi::Env env, Promise::Deferred& deferred, tree_op_callback& callback)
        : AsyncWorker(env)
        , _callback(callback)
        , _deferred(deferred)
        , _result(0)
    {}

    ~TreeOp() override = default;

    void Execute() override
    {
        try {
            _result = _callback();
        } catch (const std::exception& e) {
            SetError(e.what());
        }
    }

    void OnOK() override { _deferred.Resolve(String::New(Env(), format(_result))); }
    void OnError(const Napi::Error& e) override { _deferred.Reject(e.Value()); }

  private:
    tree_op_callback _callback;
    Promise::Deferred _deferred;
    bb::fr _result;
}
```

`AsyncWorker.Queue` enqueues the execution of the worker at a later time on a thread managed by Node's libuv runtime.

> [!IMPORTANT]
> Inside `Execute()` code _must not_ access the JavaScript environment. This means everything that's needed to complete the operation _must_ be copied from the JS environment to memory owned by C++ before the task is queued up.
> This also means that `Execute()` _can not_ create instances of `Napi::Value` since it does not have access to a `Napi::Env`.

The `Execute` function runs on a separate libuv thread. The code is then able to fan out work to other system threads. Once the async code finishes executing on the worker thread, one of the two event callbacks gets run on _the main NodeJS thread_. At this point the result of the async operation must be turned into a `Napi::Value` and returned back to the NodeJS code.

AsyncWorker instances have to be pointers otherwise they'd get destroyed as soon as the sync function that created them finishes executing. Enqueueing a worker makes N-API/libuv responsible for clean up after the worker reports its result back to NodeJS.

On the NodeJS side, C++ code wrapped in an `AsyncWorker` runs independent of the event loop. This means that the event loop is able to continue executing other queued up work while the C++ runs in the background to resolve its promise.

### Memory limit

NodeJS has a heap limit of about 4GB by default. This limit does not apply to the C++ module. The following code was used to allocate 40GB of RAM inside of a NodeJS process:

```cpp
// world_state_addon.hpp
class WorldStateAddon : public Napi::ObjectWrap<WorldStateAddon> {
  // ...
  private:
    std::vector<std::vector<std::byte>> _data;
}

// world_state_addon.cpp
WorldStateAddon::WorldStateAddon(const Napi::CallbackInfo& info)
    : ObjectWrap(info)
{
  // 40 * 1GB chunks
  size_t chunks = 40;
  for (size_t i = 0; i < chunks; i++) {
    this->_data.emplace_back(1024 * 1024 * 1024);
  }
}
```

![40GB RAM](../images/node40gb.png)

### Error handling

Unhandled exceptions in the C++ code will crash the NodeJS process. Errors must be propagated correctly to the JS side if they can not be handled in C++.

The C++ exceptions flag will be turned on at compile time so exception bubble naturally to the JS side. For async code errors should be returned by rejecting the associated promises.

[Error handling documentation](https://github.com/nodejs/node-addon-api/blob/cc06369aa4dd29e585600b8b47839c1297df962d/doc/error_handling.md)

### Build changes

The Node Addon API is distributed as an npm package (even though it contains C++ code). The new `world_state_napi` module would need to have a small `package.json` specifying the right version of the library:

```json
{
  "name": "@aztec/world_state_napi",
  "version": "0.0.0",
  "dependencies": {
    "node-addon-api": "^8.0.0",
    "node-api-headers": "^1.1.0"
  },
  "binary": {
    "napi_versions": [9]
  }
}
```

The CMake build script for this module would then have to add the the code from `node_modules` to the module's dependency list:

```cmake
# the require command outputs the path with double quotes and new lines
execute_process(
  COMMAND node -p "require('node-addon-api').include"
  WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
  OUTPUT_VARIABLE NODE_ADDON_API_DIR
)

# strip the quotes and new lines
string(REGEX REPLACE "[\r\n\"]" "" NODE_ADDON_API_DIR ${NODE_ADDON_API_DIR})
target_include_directories(world_state_napi PRIVATE ${NODE_ADDON_API_DIR})

# similar for node-api-headers
```

### PIC

Position independent code (`-fPIC` compiler flag) has to be enabled for bb libraries since the `world_state_napi` will be a shared library.

## Change Set

Fill in bullets for each area that will be affected by this change.

- [ ] L1 Contracts
- [ ] Enshrined L2 Contracts
- [ ] Private Kernel Circuits
- [ ] Public Kernel Circuits
- [ ] Rollup Circuits
- [ ] Aztec.nr
- [ ] Noir
- [ ] AVM
- [x] Sequencer
- [ ] Fees
- [ ] P2P Network
- [ ] Cryptography
- [ ] DevOps

## Test Plan

The `world_state` module (pure C++ working directly with trees) will continue to be extensively unit tested. The `world_state_napi` (the node-addon-api wrapper) module will instead be tested as part of running the aztec-node.

## Documentation Plan

N/A

## Rejection Reason

N/A

## Abandonment Reason

N/A

## Implementation Deviations

N/A
