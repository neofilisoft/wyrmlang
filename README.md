# Wyrm v3.2.0 Online Playground & Language Guide

[![License: MIT](https://img.shields.io/badge/License-MIT-333333.svg)](LICENSE)
[![Version](https://img.shields.io/badge/version-3.2.0-B10C1A)](https://github.com/neofilisoft/wyrm/releases)

Wyrm (`.wyr`) is a static systems programming language with a self-hosted compiler and gradual static typing. This repository powers the **browser-based Online Compiler & Playground** using Pyodide (WebAssembly), mirroring the features of the native Wyrm v3.2.0 toolchain.

---

## 1. Running Wyrm Code

- **In the Browser**: Paste code into the editor, select a preset example chip, and click **Run** (or press `Ctrl+Enter` / `Cmd+Enter`).
- **Interactive Input**: `input("Prompt: ")` is supported interactively in the terminal bar.
- **`main()` entry point**: If defined, `fn main()` is automatically invoked on program start.

---

## 2. Structs & Methods (v3.2.0)

Wyrm supports systems-style data structures with named fields, methods, and receiver `self` mutation:

```wyrm
struct Point {
    x: i32,
    y: i32

    fn distance_sq(self) {
        return self.x * self.x + self.y * self.y
    }

    fn translate(self, dx, dy) {
        self.x = self.x + dx
        self.y = self.y + dy
    }
}

fn main() {
    var p = Point(3, 4)
    print("Initial distance squared:", p.distance_sq())
    p.translate(10, 20)
    print("Point coordinates:", p.x, p.y)
    print("New distance squared:", p.distance_sq())
}
```

---

## 3. Variables & Gradual Static Types (v3.2.0)

Wyrm provides gradual static typing annotations:

```wyrm
fn add(a: i64, b: i64) -> i64 {
    return a + b
}

fn main() {
    var count: i64 = 1000000000
    var ratio: f32 = 3.14159
    var flag: bool = true
    var sum: i64 = add(count, 500000000)
    print("Sum:", sum)
}
```

Supported primitive types:
- `i32`, `i64`: 32-bit and 64-bit signed integers
- `u8`: 8-bit unsigned integer / byte
- `f32`, `f64`: 32-bit single and 64-bit double precision floats
- `bool`: boolean (`true` / `false`)

---

## 4. Standard Library Modules (v3.2.0)

Imported via `use std.<module>;`:

### `std.json`
```wyrm
use std.json;

fn main() {
    var text = "{\"name\": \"Wyrm\", \"version\": 3.1}"
    var obj = json_parse(text)
    print("Language:", obj["name"])
    obj["status"] = "released"
    print("JSON output:", json_encode(obj))
}
```

### `std.yaml`
```wyrm
use std.yaml;

fn main() {
    var text = "project: Wyrm\nversion: 3.1\nmode: release\n"
    var cfg = yaml_parse(text)
    print("Project:", cfg["project"])
    print("Mode:", cfg["mode"])
}
```

### `std.collections`
```wyrm
use std.collections;

fn main() {
    var m = map_new()
    map_set(m, "player", "WyrmMaster")
    map_set(m, "score", 9999)
    print("Player:", map_get(m, "player"))
    print("Has score?", map_has(m, "score"))
    print("Length:", map_len(m))

    var s = set_new()
    set_add(s, "apple")
    print("Has apple?", set_has(s, "apple"))
}
```

---

## 5. Control Flow

### `do ... til` and `repeat ... til`
The primary loop construct runs repeatedly until the condition evaluates to `true`:

```wyrm
fn main() {
    var i = 0
    do {
        i = i + 1
        if i == 2 {
            continue
        }
        if i == 5 {
            break
        }
        print("i =", i)
    } til i >= 10
}
```

---

## 6. Arena Memory Allocators

High-throughput region memory allocation with instantaneous bulk reset:

```wyrm
fn main() {
    arena buf(1024)
    var p1 = buf.alloc(64)
    var p2 = buf.alloc(128)
    print("Allocated in arena memory pool")
    buf.reset()
    print("Arena reset successfully for reuse")
}
```

---

## 7. License

MIT License - see LICENSE.
