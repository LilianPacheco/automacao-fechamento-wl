"use strict";

const API_ROOT = "http://127.0.0.1:8765";
const wlAttachedTabs = new Set();
const wlDetachTimers = new Map();
const wlSessionOwners = new Map();

function wlWakeWhatsAppTabs() {
  chrome.tabs.query({ url: "https://web.whatsapp.com/*" }, (tabs) => {
    for (const tab of tabs) {
      if (!Number.isInteger(tab.id)) continue;
      chrome.tabs.sendMessage(tab.id, { type: "WL_WAKE" }, (response) => {
        const missingReceiver = chrome.runtime.lastError;
        // O content script já é carregado pelo manifest. Reinseri-lo aqui
        // criava duas cópias na mesma aba e interrompia a leitura. Se a aba
        // ainda estiver carregando, o próximo alarme tentará acordá-la.
        void missingReceiver;
        void response;
      });
    }
  });
}

chrome.alarms.create("wl-wake-reader", { periodInMinutes: 0.5 });
chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name === "wl-wake-reader") wlWakeWhatsAppTabs();
});
wlWakeWhatsAppTabs();

chrome.storage.local.get("wl_installed_version", (stored) => {
  const currentVersion = chrome.runtime.getManifest().version;
  if (stored?.wl_installed_version === currentVersion) return;
  chrome.storage.local.set({ wl_installed_version: currentVersion }, () => {
    chrome.tabs.query({ url: "https://web.whatsapp.com/*" }, (tabs) => {
      for (const tab of tabs) {
        if (Number.isInteger(tab.id)) chrome.tabs.reload(tab.id);
      }
    });
  });
});

function wlDebuggerAttach(target) {
  return new Promise((resolve, reject) => {
    chrome.debugger.attach(target, "1.3", () => {
      const error = chrome.runtime.lastError;
      if (error) reject(new Error(error.message));
      else resolve();
    });
  });
}

function wlDebuggerCommand(target, method, parameters) {
  return new Promise((resolve, reject) => {
    chrome.debugger.sendCommand(target, method, parameters, (result) => {
      const error = chrome.runtime.lastError;
      if (error) reject(new Error(error.message));
      else resolve(result);
    });
  });
}

function wlDebuggerDetach(target) {
  return new Promise((resolve) => {
    chrome.debugger.detach(target, () => {
      void chrome.runtime.lastError;
      resolve();
    });
  });
}

function wlScheduleDetach(tabId) {
  const previous = wlDetachTimers.get(tabId);
  if (previous) clearTimeout(previous);
  wlDetachTimers.set(tabId, setTimeout(async () => {
    wlDetachTimers.delete(tabId);
    if (!wlAttachedTabs.has(tabId)) return;
    await wlDebuggerDetach({ tabId });
    wlAttachedTabs.delete(tabId);
  }, 30000));
}

async function wlEnsureDebugger(tabId) {
  if (!wlAttachedTabs.has(tabId)) {
    await wlDebuggerAttach({ tabId });
    wlAttachedTabs.add(tabId);
  }
  wlScheduleDetach(tabId);
}

async function wlTrustedClick(tabId, x, y) {
  const target = { tabId };
  await wlEnsureDebugger(tabId);
  await wlDebuggerCommand(target, "Input.dispatchMouseEvent", {
    type: "mouseMoved", x, y,
  });
  await wlDebuggerCommand(target, "Input.dispatchMouseEvent", {
    type: "mousePressed", x, y, button: "left", clickCount: 1,
  });
  await wlDebuggerCommand(target, "Input.dispatchMouseEvent", {
    type: "mouseReleased", x, y, button: "left", clickCount: 1,
  });
  wlScheduleDetach(tabId);
}

async function wlTrustedKey(tabId, key) {
  const supported = {
    ArrowRight: { code: "ArrowRight", virtualKeyCode: 39 },
    ArrowLeft: { code: "ArrowLeft", virtualKeyCode: 37 },
    ArrowDown: { code: "ArrowDown", virtualKeyCode: 40 },
    Enter: { code: "Enter", virtualKeyCode: 13 },
    Escape: { code: "Escape", virtualKeyCode: 27 },
  };
  const descriptor = supported[String(key || "")];
  if (!descriptor) throw new Error("Tecla não permitida.");
  const target = { tabId };
  await wlEnsureDebugger(tabId);
  const parameters = {
    key,
    code: descriptor.code,
    windowsVirtualKeyCode: descriptor.virtualKeyCode,
    nativeVirtualKeyCode: descriptor.virtualKeyCode,
  };
  await wlDebuggerCommand(target, "Input.dispatchKeyEvent", {
    type: "keyDown", ...parameters,
  });
  await wlDebuggerCommand(target, "Input.dispatchKeyEvent", {
    type: "keyUp", ...parameters,
  });
  wlScheduleDetach(tabId);
}

async function wlTrustedText(tabId, text) {
  const target = { tabId };
  await wlEnsureDebugger(tabId);
  await wlDebuggerCommand(target, "Input.insertText", { text: String(text || "") });
  wlScheduleDetach(tabId);
}

chrome.debugger.onDetach.addListener((source) => {
  const tabId = source.tabId;
  if (!Number.isInteger(tabId)) return;
  wlAttachedTabs.delete(tabId);
  const timer = wlDetachTimers.get(tabId);
  if (timer) clearTimeout(timer);
  wlDetachTimers.delete(tabId);
});

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (!message) return false;

  if (message.type === "WL_GET_CONFIG") {
    fetch(`${API_ROOT}/config`, { cache: "no-store" })
      .then(async (response) => {
        const data = response.ok ? await response.json() : null;
        const runningVersion = chrome.runtime.getManifest().version;
        if (data?.extension_version && data.extension_version !== runningVersion) {
          sendResponse({ ok: false, reloading: true });
          setTimeout(() => chrome.runtime.reload(), 100);
          return;
        }
        sendResponse({ ok: response.ok, data });
      })
      .catch((error) => sendResponse({ ok: false, error: String(error) }));
    return true;
  }

  if (message.type === "WL_TRUSTED_CLICK") {
    const tabId = sender.tab?.id;
    if (!Number.isInteger(tabId)) {
      sendResponse({ ok: false, error: "A aba do WhatsApp não foi identificada." });
      return false;
    }
    wlTrustedClick(tabId, Number(message.x), Number(message.y))
      .then(() => sendResponse({ ok: true }))
      .catch((error) => sendResponse({ ok: false, error: String(error) }));
    return true;
  }

  if (message.type === "WL_TRUSTED_KEY") {
    const tabId = sender.tab?.id;
    if (!Number.isInteger(tabId)) {
      sendResponse({ ok: false, error: "A aba do WhatsApp não foi identificada." });
      return false;
    }
    wlTrustedKey(tabId, String(message.key || ""))
      .then(() => sendResponse({ ok: true }))
      .catch((error) => sendResponse({ ok: false, error: String(error) }));
    return true;
  }

  if (message.type === "WL_TRUSTED_TEXT") {
    const tabId = sender.tab?.id;
    if (!Number.isInteger(tabId)) {
      sendResponse({ ok: false, error: "A aba do WhatsApp não foi identificada." });
      return false;
    }
    wlTrustedText(tabId, String(message.text || ""))
      .then(() => sendResponse({ ok: true }))
      .catch((error) => sendResponse({ ok: false, error: String(error) }));
    return true;
  }

  if (message.type === "WL_TRUSTED_START") {
    const tabId = sender.tab?.id;
    if (!Number.isInteger(tabId)) {
      sendResponse({ ok: false, error: "A aba do WhatsApp não foi identificada." });
      return false;
    }
    const sessionId = String(message.session_id || "");
    const owner = wlSessionOwners.get(sessionId);
    if (sessionId && Number.isInteger(owner) && owner !== tabId) {
      sendResponse({ ok: false, owned: true, error: "Outra aba já está lendo esta sessão." });
      return false;
    }
    if (sessionId) wlSessionOwners.set(sessionId, tabId);
    wlEnsureDebugger(tabId)
      .then(() => sendResponse({ ok: true, trusted: true }))
      .catch((error) => sendResponse({
        ok: true,
        trusted: false,
        warning: String(error),
      }));
    return true;
  }

  if (message.type === "WL_UPLOAD_ATTACHMENT") {
    fetch(`${API_ROOT}/attachment`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(message.payload),
    })
      .then(async (response) => ({
        ok: response.ok,
        data: await response.json().catch(() => ({})),
      }))
      .then(sendResponse)
      .catch((error) => sendResponse({ ok: false, error: String(error) }));
    return true;
  }

  if (message.type !== "WL_POST") return false;

  fetch(`${API_ROOT}/result`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(message.payload),
  })
    .then((response) => sendResponse({ ok: response.ok }))
    .catch((error) => sendResponse({ ok: false, error: String(error) }));
  return true;
});
