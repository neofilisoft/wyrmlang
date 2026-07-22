# Wyrm Programming Guide

Wyrm (`.wyr`) is a C-inspired scripting language, currently interpreted (tree-walking + a
bytecode/VM path), with an ongoing roadmap toward becoming a native systems language.
This guide documents the language **as currently implemented** (`lexer.py`, `parser.py`,
`ast.py`, `interpreter.py` - spec v1.2).

---

## 1. Running Wyrm code

```bash
# Python interpreter (tree-walking)
python -m wyrm path/to/file.wyr

# REPL
python -m wyrm

# Native C11 VM runner (bytecode path)
./wyrmc.exe path/to/file.wyr

# In the browser (online compiler, GitHub Pages build)
# just paste code into the editor and click Run
```

`main()`, if defined, is called automatically once after the top-level script
finishes running, so you don't have to call it yourself (see Section 9).

---

## 2. Comments and statement terminators

```wyrm
// single-line comment
/* multi-line
   comment */
/// doc-style comment (still just a comment)

x = 1      // no semicolon needed
y = 2;     // semicolon optional, purely cosmetic
```

All three C-style comment forms are supported. Semicolons at the end of a
statement are **always optional**.

---

## 3. Variables and declarations

Wyrm has three ways to bind a name to a value:

| Form | Meaning | Reassignable? |
|---|---|---|
| `name = expr` | plain (dynamic) assignment, creates the variable in the current scope if it doesn't exist yet | Yes |
| `var name = expr` | explicit mutable declaration | Yes |
| `dec name = expr` | constant declaration | **No**, reassigning raises a runtime error |

```wyrm
var age = 25
dec PI = 3.14159
count = 0          // plain assignment also works, no keyword required

count = count + 1  // OK
PI = 3.0           // RuntimeError: Cannot assign to constant 'PI'
```

Compound assignment operators are supported: `+=`, `-=`, `*=`, `/=`, `%=`
(also work on array elements: `arr[i] += 1`).

`var`/`dec` are optional style; plain `x = expr` behaves like an implicit `var`
the first time it's used in a scope. Use `dec` whenever a value must never change.

---

## 4. Data types

| Type | Example | Notes |
|---|---|---|
| int | `42` | |
| float | `3.14` | |
| str | `"hello"` | escape sequences supported (e.g. `\n`, `\t`, `\"`, `\\`) |
| bool | `true` / `false` | |
| null | `null` | Wyrm's "no value" |
| list (array) | `[1, 2, 3]` | can hold mixed types |

Type conversion / query built-ins: `int(x)`, `float(x)`, `str(x)`, `type(x)`.

```wyrm
print(type(42))       // "int"
print(type(3.14))     // "float"
print(type("hi"))     // "str"
print(type([1,2]))    // "list"
print(type(null))     // "null"
```

Wyrm has **no implicit numeric-to-string coercion**: `"x = " + 5` is an error;
you must write `"x = " + str(5)`. Arithmetic operators (`+ - * / // %`) otherwise follow
familiar Python-like numeric semantics (`/` is true division, `//` is floor division).

---

## 5. Operators

```wyrm
// Arithmetic
+  -  *  /  //  %

// Comparison
==  !=  <  >  <=  >=

// Logical (symbol form and word form are interchangeable aliases)
&&  ||  !
and or  not

// Assignment
=  +=  -=  *=  /=  %=
```

`&&`/`and`, `||`/`or`, `!`/`not` are exact aliases of each other; pick whichever
reads better in context.

---

## 6. Strings and printing

```wyrm
name = "Aran"
print("Hello, " + name + "!")       // string concatenation with +
print("Hello,", name)               // multi-arg print, space-separated
print name, "is", 25, "years old"   // print also works without parentheses

// strings support indexing, like a read-only array of characters
first_char = name[0]
print(len(name))                    // string length via len()
```

`print` accepts either `print(a, b, c)` or bare `print a, b, c`; both forms are
valid statements, and multiple arguments are joined with a single space, same as `print()`
in most scripting languages.

---

## 7. Control flow

```wyrm
if score >= 90 {
    grade = "A"
} elif score >= 80 {
    grade = "B"
} else {
    grade = "F"
}
```

No `then`/`do` keyword between the condition and `{`. `elif`/`else` are optional
and can be chained.

---

## 8. Loops

Wyrm has **one** loop construct: `repeat { ... } til (condition)`, a post-condition
loop (like `do { } while(!condition)` in C), which always runs the body **at least once**.

```wyrm
i = 0
repeat {
    print(i)
    i = i + 1
} til (i >= 5)          // parentheses around the condition are required
```

`break` exits the loop immediately; `continue` skips to the `til` check for the next
iteration:

```wyrm
i = 0
repeat {
    i = i + 1
    if i == 3 { continue }   // skip printing 3
    if i >= 5 { break }
    print(i)
} til (i >= 10)
```

There is currently no `while` or `for` keyword; every loop is written as a
`repeat/til`. For a "loop zero or more times" pattern, guard the body with an `if`,
or put the exit condition first inside the loop with `break`.

---

## 9. Functions

```wyrm
fn add(a, b) {
    return a + b
}

fn factorial(n) {
    if n <= 1 {
        return 1
    } else {
        return n * factorial(n - 1)   // recursion works
    }
}

fn main() {
    print("5 + 3 =", add(5, 3))
    print("5! =", factorial(5))
}
```

Functions are first-class values with lexical closures: a function captures the
environment it was defined in, so nested functions can read (and, through `set`
semantics, write) variables from an enclosing scope. Missing arguments are bound to
`null` rather than raising an error. A function with no `return` implicitly returns
`null`. `main()`, if present, is auto-invoked once after the script's top-level
statements finish, so you generally don't need to call it explicitly (unlike some of the
older example files in this repo, which call `main()` a second time out of habit).

---

## 10. Arrays

```wyrm
numbers = [1, 2, 3, 4, 5]
numbers[0] = 10          // index assignment
numbers[0] += 5           // compound assignment on an element

mixed = [1, "hello", 3.14, true]   // arrays can hold mixed types

append(numbers, 99)       // add to the end
last = pop(numbers)       // remove & return the last element

print("length:", len(numbers))
```

Arrays are zero-indexed. `append`/`pop` mutate the array in place. There is
currently no array slicing (`arr[1:3]`) or negative indexing.

---

## 11. Built-in functions

| Function | Purpose |
|---|---|
| `print(...)` | print values, space-separated |
| `input(prompt)` | read a line from stdin |
| `int(x)` / `float(x)` / `str(x)` | type conversion |
| `len(x)` | length of a string or array |
| `type(x)` | returns the type name as a string |
| `abs(x)` | absolute value |
| `min(...)` / `max(...)` | minimum / maximum of the given arguments |
| `round(x)` | round to nearest integer |
| `pow(x, y)` | x raised to the power y |
| `append(list, value)` | push a value to the end of a list |
| `pop(list)` | remove and return the last element |

---

## 12. Modules

```wyrm
use math_helpers.wyr;   // semicolon optional
use math_helpers.wyr

fn main() {
    print(add_nums(1, 2))   // functions/consts defined in math_helpers.wyr are now visible
}
```

`use` loads and executes another `.wyr` file (resolved relative to the current
script's directory), pulling its top-level functions and variables into scope, similar
to a simple `#include`. There's no namespacing/aliasing yet; everything lands in the
same global scope.

---

## 13. Errors

Common runtime errors you may encounter while developing:

| Situation | Error |
|---|---|
| Using an undeclared variable | `Undefined variable: 'x'` |
| Reassigning a `dec` constant | `Cannot assign to constant 'PI'` |
| Dividing by zero | `Division by zero` |
| Mixing types in `+` (e.g. `str + int`) | Python-level `TypeError`, wrap with `str()` |

---

## 14. Full example

```wyrm
// average.wyr - averages an array of scores and prints the grade

dec PASS_MARK = 50

fn average(scores) {
    total = 0
    i = 0
    repeat {
        total = total + scores[i]
        i = i + 1
    } til (i >= len(scores))
    return total / len(scores)
}

fn main() {
    scores = [85, 92, 78, 96, 60]
    avg = average(scores)

    print("Average score:", avg)

    if avg >= PASS_MARK {
        print("Result: PASS")
    } else {
        print("Result: FAIL")
    }
}
```

---

## 15. What's not here yet

Per the project roadmap (`TODO_SYSTEM_LANGUAGE.md`), things not yet implemented
include: `while`/`for` loops, structs/classes, array slicing/negative indexing, string
formatting helpers, a standard library beyond the builtins above, and the planned
ownership/`unsafe {}` systems-programming features. Check `TODO_SYSTEM_LANGUAGE.md` and
`implementation_plan.md` in the repo for the current roadmap before relying on anything
not documented here.
