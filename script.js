const EXAMPLES = [
  {
    label: "hello",
    code: 'fn main() {\n    print("Hello, Wyrm v3.1.0!")\n}'
  },
  {
    label: "structs & methods",
    code: 'struct Point {\n    x: i32,\n    y: i32\n\n    fn distance_sq(self) {\n        return self.x * self.x + self.y * self.y\n    }\n\n    fn translate(self, dx, dy) {\n        self.x = self.x + dx\n        self.y = self.y + dy\n    }\n}\n\nfn main() {\n    var p = Point(3, 4)\n    print("Initial distance squared:", p.distance_sq())\n    p.translate(10, 20)\n    print("Translated Point:", p.x, p.y)\n    print("New distance squared:", p.distance_sq())\n}'
  },
  {
    label: "static types",
    code: 'fn add(a: i64, b: i64) -> i64 {\n    return a + b\n}\n\nfn main() {\n    var count: i64 = 1000000000\n    var ratio: f32 = 3.14159\n    var flag: bool = true\n    var sum: i64 = add(count, 500000000)\n    print("Static sum:", sum)\n    print("Ratio:", ratio)\n    print("Flag:", flag)\n}'
  },
  {
    label: "std.json",
    code: 'use std.json;\n\nfn main() {\n    var text = "{\\"language\\": \\"Wyrm\\", \\"version\\": 3.1, \\"fast\\": true}"\n    var obj = json_parse(text)\n    print("Language:", obj["language"])\n    print("Version:", obj["version"])\n    obj["author"] = "Neofilisoft"\n    print("Encoded JSON:", json_encode(obj))\n}'
  },
  {
    label: "std.yaml",
    code: 'use std.yaml;\n\nfn main() {\n    var text = "project: Wyrm\\nversion: 3.1\\nmode: release\\n"\n    var cfg = yaml_parse(text)\n    print("Project:", cfg["project"])\n    print("Version:", cfg["version"])\n    print("Mode:", cfg["mode"])\n}'
  },
  {
    label: "std.collections",
    code: 'use std.collections;\n\nfn main() {\n    var m = map_new()\n    map_set(m, "player", "WyrmMaster")\n    map_set(m, "score", 9999)\n    print("Player:", map_get(m, "player"))\n    print("Score:", map_get(m, "score"))\n    print("Has score?", map_has(m, "score"))\n    print("Map length:", map_len(m))\n\n    var s = set_new()\n    set_add(s, "wyrm")\n    print("Has wyrm in set?", set_has(s, "wyrm"))\n}'
  },
  {
    label: "do/til loops",
    code: 'fn main() {\n    var i = 0\n    print("--- Testing do ... til loop ---")\n    do {\n        i = i + 1\n        if i == 2 {\n            continue\n        }\n        if i == 5 {\n            break\n        }\n        print("Step:", i)\n    } til i >= 10\n    print("Done!")\n}'
  },
  {
    label: "arena memory",
    code: 'fn main() {\n    arena buf(1024)\n    var chunk1 = buf.alloc(64)\n    var chunk2 = buf.alloc(128)\n    print("Allocated 64 and 128 bytes from arena")\n    buf.reset()\n    print("Arena reset successfully for bulk reuse")\n}'
  },
  {
    label: "input demo",
    code: 'fn main() {\n    var name = input("Enter your name: ")\n    print("Welcome to Wyrm v3.1.0, " + name + "!")\n}'
  }
];

/* ---------- theme toggle ---------- */
const themeBtn = document.getElementById('theme-btn');
const THEME_KEY = 'wyrm-theme';

function applyTheme(theme) {
  document.documentElement.setAttribute('data-theme', theme);
}

function initTheme() {
  const saved = localStorage.getItem(THEME_KEY);
  if (saved === 'dark' || saved === 'light') { applyTheme(saved); return; }
  const prefersDark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
  applyTheme(prefersDark ? 'dark' : 'light');
}

themeBtn.addEventListener('click', () => {
  const current = document.documentElement.getAttribute('data-theme') === 'dark' ? 'dark' : 'light';
  const next = current === 'dark' ? 'light' : 'dark';
  applyTheme(next);
  localStorage.setItem(THEME_KEY, next);
});

initTheme();

const outputEl    = document.getElementById('output');
const inputEl     = document.getElementById('code-input');
const gutterEl    = document.getElementById('gutter');
const runBtn      = document.getElementById('run-btn');
const statusEl    = document.getElementById('status');
const statusText  = document.getElementById('status-text');
const examplesEl  = document.getElementById('examples');
const clearBtn    = document.getElementById('clear-btn');
const stdinBar    = document.getElementById('stdin-bar');
const stdinInput  = document.getElementById('stdin-input');
const stdinSend   = document.getElementById('stdin-send');
const stdinPrompt = document.getElementById('stdin-prompt');

/* ---------- output helpers ---------- */
function appendLine(text, cls) {
  const div = document.createElement('div');
  div.className = 'line-' + cls;
  div.textContent = text;
  outputEl.appendChild(div);
  outputEl.scrollTop = outputEl.scrollHeight;
}

function appendText(text, cls) {
  const span = document.createElement('span');
  span.className = 'line-' + cls;
  span.style.display = 'block';
  span.textContent = text;
  outputEl.appendChild(span);
  outputEl.scrollTop = outputEl.scrollHeight;
}

/* ---------- syntax highlighter ---------- */
const highlightBackdrop = document.getElementById('highlight-backdrop');

function highlightWyrm(code) {
  let html = code
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');

  const mainRegex = /(^|\n)([ \t]*\/\/\/?.*)|(\"(?:\\.|[^\"\\])*\"|'(?:\\.|[^'\\])*')|\b(fn|if|elif|else|do|repeat|til|break|continue|return|var|dec|owned|arena|struct|self|use|unsafe|and|or|not|i8|i16|i32|i64|u8|u16|u32|u64|f32|f64|bool|char|string)\b|\b(true|false|null)\b|\b(print|input|int|float|str|len|type|abs|max|min|round|pow|append|pop|split|join|trim|upper|lower|contains|replace|starts_with|ends_with|char_at|ord_val|chr_val|to_bytes|from_bytes|malloc|free|realloc|read_file|write_file|json_parse|json_encode|json_pretty|yaml_parse|yaml_encode|map_new|map_set|map_get|map_has|map_len|set_new|set_add|set_has)\b|(\b\d+(?:\.\d+)?\b)/g;

  html = html.replace(mainRegex, (match, lineStart, comment, str, keyword, constant, builtin, number) => {
    if (comment !== undefined) return `${lineStart}<span class="hl-comment">${comment}</span>`;
    if (str)      return `<span class="hl-string">${str}</span>`;
    if (keyword)  return `<span class="hl-keyword">${keyword}</span>`;
    if (constant) return `<span class="hl-constant">${constant}</span>`;
    if (builtin)  return `<span class="hl-builtin">${builtin}</span>`;
    if (number)   return `<span class="hl-number">${number}</span>`;
    return match;
  });

  return html;
}

function updateHighlight() {
  highlightBackdrop.innerHTML = highlightWyrm(inputEl.value) + "\n";
}

/* ---------- line-number gutter & highlight sync ---------- */
function updateGutter() {
  const lineCount = inputEl.value.split('\n').length;
  let lines = '';
  for (let i = 1; i <= lineCount; i++) lines += i + '\n';
  gutterEl.textContent = lines;
}

inputEl.addEventListener('input', () => { updateGutter(); updateHighlight(); });
inputEl.addEventListener('scroll', () => {
  gutterEl.scrollTop = inputEl.scrollTop;
  highlightBackdrop.scrollTop = inputEl.scrollTop;
  highlightBackdrop.scrollLeft = inputEl.scrollLeft;
});

updateGutter();
updateHighlight();

/* ---------- example chips ---------- */
EXAMPLES.forEach((ex, i) => {
  const chip = document.createElement('span');
  chip.className = 'chip';
  chip.textContent = ex.label;
  chip.tabIndex = 0;
  chip.onclick = () => {
    inputEl.value = ex.code;
    updateGutter();
    updateHighlight();
    inputEl.focus();
  };
  examplesEl.appendChild(chip);
  if (i === 0) { inputEl.value = ex.code; updateGutter(); updateHighlight(); }
});

clearBtn.onclick = () => { outputEl.innerHTML = ''; };

/* ---------- interactive stdin mechanism ---------- */
let pendingInputResolve = null;

function showStdinBar(prompt) {
  stdinPrompt.textContent = prompt;
  stdinInput.value = '';
  stdinBar.style.display = 'flex';
  stdinInput.focus();
}

function hideStdinBar() {
  stdinBar.style.display = 'none';
  stdinInput.value = '';
  stdinPrompt.textContent = '';
}

function submitStdin() {
  if (!pendingInputResolve) return;
  const val = stdinInput.value;
  appendText((stdinPrompt.textContent || '') + val, 'echo');
  hideStdinBar();
  const resolve = pendingInputResolve;
  pendingInputResolve = null;
  resolve(val);
}

stdinSend.addEventListener('click', submitStdin);
stdinInput.addEventListener('keydown', (e) => {
  if (e.key === 'Enter') { e.preventDefault(); submitStdin(); }
});

/* ---------- pyodide boot ---------- */
let pyodideReady = null;

async function boot() {
  try {
    const pyodide = await loadPyodide();
    const sourcesEl = document.getElementById('wyrm-sources');
    const sources = window.WYRM_SOURCES || (sourcesEl ? JSON.parse(sourcesEl.textContent) : {});

    pyodide.FS.mkdirTree('/wyrmpkg/wyrm');
    for (const [filename, content] of Object.entries(sources)) {
      pyodide.FS.writeFile('/wyrmpkg/wyrm/' + filename, content);
    }

    const jsInputHandler = async function(prompt) {
      return new Promise((resolve) => {
        pendingInputResolve = resolve;
        showStdinBar(String(prompt));
      });
    };
    pyodide.globals.set('_js_input_handler', jsInputHandler);

    await pyodide.runPythonAsync(`
import sys, io, re, asyncio
sys.path.insert(0, '/wyrmpkg')
from wyrm.lexer import Lexer, LexError
from wyrm.parser import Parser, ParseError
from wyrm.environment import WyrmRuntimeError
from wyrm.async_interpreter import AsyncInterpreter

_js_handler = _js_input_handler

async def _py_input_coro(prompt):
    result = await _js_handler(prompt)
    return str(result)

def _format_visual_error(e, code):
    msg = str(e)
    lines = code.splitlines()
    m = re.search(r"line\s+(\d+)(?:\s+col\s+(\d+))?", msg, re.IGNORECASE)
    if m:
        line_num = int(m.group(1))
        col_num = int(m.group(2)) if m.group(2) else 1
        snippet = lines[line_num - 1] if 0 <= line_num - 1 < len(lines) else ""
        pointer = " " * max(0, col_num - 1) + "^"
        err_code = "error[E0002]" if isinstance(e, ParseError) else ("error[E0001]" if isinstance(e, LexError) else "error[E0003]")
        return f"{err_code}: {msg}\n  --> main.wyr:{line_num}:{col_num}\n   |\n{line_num:2d} | {snippet}\n   | {pointer}"
    return f"error[E0003]: {type(e).__name__}: {msg}"

async def run_wyrm_source_async(code):
    buf = io.StringIO()
    old_stdout = sys.stdout
    sys.stdout = buf
    ok = True
    err = ""
    try:
        interp = AsyncInterpreter(input_coro=_py_input_coro)
        tokens = Lexer(code).tokenize()
        ast_nodes = Parser(tokens).parse()
        await interp.execute(ast_nodes)
    except Exception as e:
        ok = False
        err = _format_visual_error(e, code)
    finally:
        sys.stdout = old_stdout
    return {"ok": ok, "output": buf.getvalue(), "error": err}
`);

    statusEl.classList.add('ready');
    statusText.textContent = 'พร้อมรัน (v3.1.0 Ready)';
    inputEl.disabled = false;
    runBtn.disabled = false;
    outputEl.innerHTML = '';
    appendLine('Wyrm v3.1.0 Runtime loaded successfully.', 'sys');

    return pyodide;
  } catch (e) {
    statusEl.classList.add('error');
    statusText.textContent = 'โหลดไม่สำเร็จ: ' + e.message;
    appendLine('ไม่สามารถโหลด Wyrm runtime ได้: ' + e.message, 'err');
    throw e;
  }
}

pyodideReady = boot();

/* ---------- run code ---------- */
async function runCode() {
  const code = inputEl.value;
  if (!code.trim()) return;
  const pyodide = await pyodideReady;

  outputEl.innerHTML = '';
  appendLine('$ running…', 'sys');
  runBtn.disabled = true;
  hideStdinBar();

  try {
    pyodide.globals.set('_wyrm_src', code);
    const result = await pyodide.runPythonAsync('await run_wyrm_source_async(_wyrm_src)');
    const dict = result.toJs({ dict_converter: Object.fromEntries });
    outputEl.innerHTML = '';
    if (dict.output) {
      dict.output.replace(/\n$/, '').split('\n').forEach(line => appendLine(line, 'out'));
    }
    if (!dict.ok) {
      dict.error.split('\n').forEach(line => appendLine(line, 'err'));
    }
    if (dict.ok && !dict.output) appendLine('(no output)', 'sys');
  } catch (e) {
    outputEl.innerHTML = '';
    appendLine('Runtime error: ' + e.message, 'err');
  } finally {
    runBtn.disabled = false;
    hideStdinBar();
    pendingInputResolve = null;
  }
}

runBtn.addEventListener('click', runCode);
inputEl.addEventListener('keydown', (e) => {
  if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') { e.preventDefault(); runCode(); }
  if (e.key === 'Tab') {
    e.preventDefault();
    const start = inputEl.selectionStart, end = inputEl.selectionEnd;
    inputEl.value = inputEl.value.slice(0, start) + '    ' + inputEl.value.slice(end);
    inputEl.selectionStart = inputEl.selectionEnd = start + 4;
    updateGutter();
  }
});
