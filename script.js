const EXAMPLES = [
  { label: "hello", code: 'fn main() {\n    print("Hello World")\n}' },
  { label: "if/elif", code: 'fn main() {\n    x = 7\n    if x > 10 {\n        print("big")\n    } elif x > 5 {\n        print("medium")\n    } else {\n        print("small")\n    }\n}' },
  { label: "repeat/til", code: 'fn main() {\n    i = 0\n    repeat {\n        print(i)\n        i = i + 1\n    } til (i == 5)\n}' },
  { label: "arrays", code: 'fn main() {\n    nums = [10, 20, 30]\n    print(nums[1])\n    print(len(nums))\n}' },
];

/* ---------- theme toggle ---------- */
const themeBtn = document.getElementById('theme-btn');
const THEME_KEY = 'wyrm-theme';

function applyTheme(theme) {
  document.documentElement.setAttribute('data-theme', theme);
}

function initTheme() {
  const saved = localStorage.getItem(THEME_KEY);
  if (saved === 'dark' || saved === 'light') {
    applyTheme(saved);
    return;
  }
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

const outputEl = document.getElementById('output');
const inputEl = document.getElementById('code-input');
const gutterEl = document.getElementById('gutter');
const runBtn = document.getElementById('run-btn');
const statusEl = document.getElementById('status');
const statusText = document.getElementById('status-text');
const examplesEl = document.getElementById('examples');
const clearBtn = document.getElementById('clear-btn');

function appendLine(text, cls) {
  const div = document.createElement('div');
  div.className = 'line-' + cls;
  div.textContent = text;
  outputEl.appendChild(div);
  outputEl.scrollTop = outputEl.scrollHeight;
}

/* ---------- line-number gutter ---------- */
function updateGutter() {
  const lineCount = inputEl.value.split('\n').length;
  let lines = '';
  for (let i = 1; i <= lineCount; i++) lines += i + '\n';
  gutterEl.textContent = lines;
}
inputEl.addEventListener('input', updateGutter);
inputEl.addEventListener('scroll', () => { gutterEl.scrollTop = inputEl.scrollTop; });
updateGutter();

/* ---------- example chips ---------- */
EXAMPLES.forEach((ex, i) => {
  const chip = document.createElement('span');
  chip.className = 'chip';
  chip.textContent = ex.label;
  chip.tabIndex = 0;
  chip.onclick = () => {
    inputEl.value = ex.code;
    updateGutter();
    inputEl.focus();
  };
  examplesEl.appendChild(chip);
  if (i === 0) { inputEl.value = ex.code; updateGutter(); }
});

clearBtn.onclick = () => { outputEl.innerHTML = ''; };

let pyodideReady = null;

async function boot() {
  try {
    const pyodide = await loadPyodide();
    const sources = JSON.parse(document.getElementById('wyrm-sources').textContent);

    pyodide.FS.mkdirTree('/wyrmpkg/wyrm');
    for (const [filename, content] of Object.entries(sources)) {
      pyodide.FS.writeFile('/wyrmpkg/wyrm/' + filename, content);
    }

    await pyodide.runPythonAsync(`
import sys
sys.path.insert(0, '/wyrmpkg')
import io
from wyrm.lexer import Lexer
from wyrm.parser import Parser
from wyrm.interpreter import Interpreter

def _input_unsupported(prompt=""):
    raise RuntimeError("input() is not available in the browser REPL")

def run_wyrm_source(code):
    buf = io.StringIO()
    old_stdout = sys.stdout
    sys.stdout = buf
    try:
        interpreter = Interpreter()
        interpreter.global_env.define("input", type(interpreter.global_env.get("print"))("input", lambda args: _input_unsupported(*args)))
        tokens = Lexer(code).tokenize()
        ast_nodes = Parser(tokens).parse()
        interpreter.execute(ast_nodes)
        ok = True
        err = ""
    except Exception as e:
        ok = False
        err = f"{type(e).__name__}: {e}"
    finally:
        sys.stdout = old_stdout
    return {"ok": ok, "output": buf.getvalue(), "error": err}
`);

    statusEl.classList.add('ready');
    statusText.textContent = 'พร้อมรัน';
    inputEl.disabled = false;
    runBtn.disabled = false;
    outputEl.innerHTML = '';
    appendLine('พร้อมใช้งาน - กด Run เพื่อรันโค้ด (Ctrl/Cmd+Enter)', 'sys');

    return pyodide;
  } catch (e) {
    statusEl.classList.add('error');
    statusText.textContent = 'โหลดไม่สำเร็จ: ' + e.message;
    appendLine('ไม่สามารถโหลด Python runtime ได้: ' + e.message, 'err');
    throw e;
  }
}

pyodideReady = boot();

async function runCode() {
  const code = inputEl.value;
  if (!code.trim()) return;
  const pyodide = await pyodideReady;

  outputEl.innerHTML = '';
  appendLine('$ running…', 'sys');
  runBtn.disabled = true;

  try {
    pyodide.globals.set('_wyrm_src', code);
    const result = await pyodide.runPythonAsync('run_wyrm_source(_wyrm_src)');
    const dict = result.toJs({ dict_converter: Object.fromEntries });
    outputEl.innerHTML = '';
    if (dict.output) appendLine(dict.output.replace(/\n$/, ''), 'out');
    if (!dict.ok) appendLine(dict.error, 'err');
    if (dict.ok && !dict.output) appendLine('(no output)', 'sys');
  } catch (e) {
    outputEl.innerHTML = '';
    appendLine('Runtime error: ' + e.message, 'err');
  } finally {
    runBtn.disabled = false;
  }
}

runBtn.addEventListener('click', runCode);
inputEl.addEventListener('keydown', (e) => {
  if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
    e.preventDefault();
    runCode();
  }
  // basic tab support
  if (e.key === 'Tab') {
    e.preventDefault();
    const start = inputEl.selectionStart, end = inputEl.selectionEnd;
    inputEl.value = inputEl.value.slice(0, start) + '    ' + inputEl.value.slice(end);
    inputEl.selectionStart = inputEl.selectionEnd = start + 4;
    updateGutter();
  }
});
