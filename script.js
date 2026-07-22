const EXAMPLES = [
  { label: "hello", code: 'fn main() {\n    print("Hello World")\n}' },
  { label: "input demo", code: 'fn main() {\n    var name = input("Enter your name: ")\n    print("Hello, " + name + "!")\n}' },
  { label: "if/elif", code: 'fn main() {\n    var x = 7\n    if x > 10 {\n        print("big")\n    } elif x > 5 {\n        print("medium")\n    } else {\n        print("small")\n    }\n}' },
  { label: "repeat/til", code: 'fn main() {\n    var i = 0\n    repeat {\n        print(i)\n        i += 1\n    } til (i == 5)\n}' },
  { label: "arrays", code: 'fn main() {\n    var nums = [10, 20, 30]\n    print(nums[1])\n    print(len(nums))\n}' },
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
  // append text without a trailing newline div (for inline prompt display)
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

  const mainRegex = /(\/\/.*)|(\"(?:\\.|[^\"\\])*\"|'(?:\\.|[^'\\])*')|\b(fn|if|elif|else|repeat|til|break|continue|return|var|dec|use)\b|\b(true|false|null)\b|\b(print|input|int|float|str|len|type|abs|max|min|round|pow|append|pop)\b|(\b\d+(?:\.\d+)?\b)/g;

  html = html.replace(mainRegex, (match, comment, str, keyword, constant, builtin, number) => {
    if (comment) return `<span class="hl-comment">${comment}</span>`;
    if (str)     return `<span class="hl-string">${str}</span>`;
    if (keyword) return `<span class="hl-keyword">${keyword}</span>`;
    if (constant) return `<span class="hl-constant">${constant}</span>`;
    if (builtin) return `<span class="hl-builtin">${builtin}</span>`;
    if (number)  return `<span class="hl-number">${number}</span>`;
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
// pendingInputResolve holds the resolve function of the current input Promise
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
  // Echo the user input in output pane (green, like a real terminal)
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

    // JS-side async input handler: called by Python, returns a JS Promise
    // that resolves when the user submits the stdin bar.
    // NOTE: there is no top-level `pyodide.createProxy()` API. Plain JS
    // functions assigned into pyodide.globals are automatically wrapped
    // as callable JsProxy objects on the Python side, and a Promise
    // returned from them is automatically awaitable from Python — so we
    // just hand the function over directly.
    const jsInputHandler = async function(prompt) {
      return new Promise((resolve) => {
        pendingInputResolve = resolve;
        showStdinBar(String(prompt));
      });
    };
    pyodide.globals.set('_js_input_handler', jsInputHandler);

    await pyodide.runPythonAsync(`
import sys, io, asyncio
sys.path.insert(0, '/wyrmpkg')
from wyrm.lexer import Lexer
from wyrm.parser import Parser
from wyrm.async_interpreter import AsyncInterpreter

_js_handler = _js_input_handler

async def _py_input_coro(prompt):
    # Await the JS Promise via Pyodide's JS<->Python bridge
    result = await _js_handler(prompt)
    return str(result)

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
    // Use the async runner which supports interactive input
    const result = await pyodide.runPythonAsync('await run_wyrm_source_async(_wyrm_src)');
    const dict = result.toJs({ dict_converter: Object.fromEntries });
    // Remove the "$ running..." line and show output
    outputEl.innerHTML = '';
    if (dict.output) {
      // Each line of output is a separate div
      dict.output.replace(/\n$/, '').split('\n').forEach(line => appendLine(line, 'out'));
    }
    if (!dict.ok) appendLine(dict.error, 'err');
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
