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

async function call(path, options = {}) {
  let res;
  try {
    res = await fetch(API + path, {
      ...options,
      headers: { ...HEADERS, ...(options.headers || {}) },
    });
  } catch (e) {
    throw new Error("Helper not running. Double-click start-beatgrab.bat first.");
  }
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || "HTTP " + res.status);
  return data;
}

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

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
