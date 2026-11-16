const API = "http://127.0.0.1:9835";
const HEADERS = { "X-BeatGrab": "1" };
const POLL_MS = 1000;
const MAX_WAIT_MS = 15 * 60 * 1000;

const busyTabs = new Set();

function setBadge(tabId, text, color, title) {
  chrome.action.setBadgeBackgroundColor({ color, tabId });
  chrome.action.setBadgeText({ text, tabId });
  if (title) chrome.action.setTitle({ title, tabId });
}

function notify(title, message) {
  chrome.notifications.create({
    type: "basic",
    iconUrl: "icon128.png",
    title,
    message,
  });
}

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

// ---- Helper lifetime -------------------------------------------------------
// Chrome starts the helper (registered by install-beatgrab.bat) when we connect,
// and stops it when the connection closes, which happens when Chrome quits.
// An open connection also keeps this service worker alive.
const HOST = "com.beatgrab.helper";
const RETRY_MIN_MS = 2000;
const RETRY_MAX_MS = 5 * 60 * 1000;
let nativePort = null;
let hostMissing = false;
let retryDelay = RETRY_MIN_MS;
let retryTimer = null;

function connectHelper() {
  if (nativePort) return;
  clearTimeout(retryTimer);
  const connectedAt = Date.now();
  try {
    nativePort = chrome.runtime.connectNative(HOST);
  } catch (e) {
    nativePort = null;
    return;
  }
  nativePort.onDisconnect.addListener(() => {
    const error = (chrome.runtime.lastError && chrome.runtime.lastError.message) || "";
    nativePort = null;
    hostMissing = /not found|forbidden/i.test(error);
    if (hostMissing) return; // not installed: install-beatgrab.bat fixes it
    // The helper stopped. Start it again, backing off if it keeps failing.
    retryDelay = Date.now() - connectedAt > 60000 ? RETRY_MIN_MS : Math.min(retryDelay * 2, RETRY_MAX_MS);
    retryTimer = setTimeout(connectHelper, retryDelay);
  });
}

async function helperAnswers() {
  try {
    return (await fetch(API + "/ping")).ok;
  } catch (e) {
    return false;
  }
}

// Makes sure the helper is up, starting it if needed. Returns true when it answers.
async function ensureHelper() {
  if (await helperAnswers()) return true;
  hostMissing = false;
  retryDelay = RETRY_MIN_MS;
  connectHelper();
  for (let i = 0; i < 20; i++) {
    await sleep(500);
    if (await helperAnswers()) return true;
    if (hostMissing) return false;
  }
  return false;
}

function helperError() {
  return hostMissing
    ? "Helper not set up. Run install-beatgrab.bat once, then restart Chrome."
    : "Helper not running. Restart Chrome, or double-click start-beatgrab.bat.";
}

chrome.runtime.onStartup.addListener(connectHelper);
chrome.runtime.onInstalled.addListener(connectHelper);
connectHelper(); // also whenever this service worker wakes up

// ---- Talking to the helper -------------------------------------------------
async function call(path, options = {}) {
  const request = () => fetch(API + path, {
    ...options,
    headers: { ...HEADERS, ...(options.headers || {}) },
  });
  let res;
  try {
    res = await request();
  } catch (e) {
    // Nothing reached the helper, so it's safe to start it and try once more.
    if (!(await ensureHelper())) throw new Error(helperError());
    try {
      res = await request();
    } catch (e2) {
      throw new Error(helperError());
    }
  }
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || "HTTP " + res.status);
  return data;
}

// The helper answers straight away with a job id and we poll for the result.
// Short requests keep the service worker alive, however long the download takes.
async function download(url) {
  // MP3 or WAV, as chosen in the toolbar popup.
  const { format } = await chrome.storage.local.get({ format: "mp3" });
  const { job } = await call("/grab", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url, format }),
  });
  const deadline = Date.now() + MAX_WAIT_MS;
  while (Date.now() < deadline) {
    await sleep(POLL_MS);
    const status = await call("/status?job=" + encodeURIComponent(job));
    if (status.state === "done") return status.file;
    if (status.state === "error") throw new Error(status.error || "Download failed");
  }
  throw new Error("Timed out waiting for the download");
}

// Returns { ok: true, file } or { ok: false, error }.
async function grab(tab, url = tab && tab.url) {
  if (!tab || !tab.id || !url) return { ok: false, error: "No page to grab" };
  if (busyTabs.has(tab.id)) return { ok: false, error: "Already downloading this tab" };
  busyTabs.add(tab.id);
  setBadge(tab.id, "...", "#f59e0b", "Downloading...");
  let result;
  try {
    const file = await download(url);
    setBadge(tab.id, "OK", "#16a34a", "Saved: " + file);
    notify("Beat saved", file.split(/[\\/]/).pop());
    result = { ok: true, file };
  } catch (e) {
    setBadge(tab.id, "ERR", "#dc2626", e.message);
    notify("BeatGrab failed", e.message);
    result = { ok: false, error: e.message };
  } finally {
    busyTabs.delete(tab.id);
  }
  setTimeout(() => chrome.action.setBadgeText({ text: "", tabId: tab.id }), 6000);
  return result;
}

// Grab requests come from the in-page "Send to FL" button (content.js, which
// has sender.tab) or from the toolbar popup (popup.js, which passes tabId).
chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg && msg.type === "start-helper") {
    ensureHelper().then((ok) => sendResponse({ ok, error: ok ? null : helperError() }));
    return true;
  }
  if (!msg || msg.type !== "grab") return;
  const tab = sender.tab || (Number.isInteger(msg.tabId) ? { id: msg.tabId } : null);
  if (!tab) return;
  grab(tab, String(msg.url || "")).then(sendResponse);
  return true; // answer comes later
});

chrome.commands.onCommand.addListener(async (cmd) => {
  if (cmd !== "grab") return;
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  grab(tab);
});
