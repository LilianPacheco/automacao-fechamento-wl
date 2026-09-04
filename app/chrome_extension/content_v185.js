"use strict";

(function wlFechamentoReaderScope() {
if (globalThis.__WL_FECHAMENTO_READER_ACTIVE__) return;
globalThis.__WL_FECHAMENTO_READER_ACTIVE__ = true;

const WL_LOAD_OLDER =
  "Clique neste aviso para carregar mensagens mais antigas do seu celular.";
const WL_SYNCING =
  "Sincronizando mensagens mais antigas. Clique para ver o progresso.";
const WL_LOADING_RECENT = "carregar mensagens recentes...";

let wlRunningSession = "";
let wlAttachmentErrors = [];
let wlNavigationStage = "não iniciado";
let wlNavigationDateReached = false;

function wlSleep(milliseconds) {
  return new Promise((resolve) => setTimeout(resolve, milliseconds));
}

function wlNormalize(value) {
  return String(value || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/\s+/g, " ")
    .trim()
    .toLowerCase();
}

function wlMessageCaptionText(bubble, fallbackText = "") {
  const selectors = [
    ".selectable-text",
    '[data-testid="conversation-text"]',
    '[data-testid="msg-text"]',
  ];
  const values = Array.from(bubble?.querySelectorAll?.(selectors.join(",")) || [])
    .map((element) => (element.innerText || element.textContent || "").trim())
    .filter(Boolean);
  return values.length ? values.join("\n") : fallbackText;
}

function wlGroupMatches(value, groupName) {
  const candidate = wlNormalize(value);
  const expected = wlNormalize(groupName);
  if (!candidate) return false;
  if (candidate.includes(expected) || expected.includes(candidate)) return true;
  return ["awl", "expedicao", "prellog"].every((word) =>
    candidate.includes(word)
  );
}

function wlCurrentConversationTitle() {
  const header = document.querySelector("#main header");
  if (!header) return "";
  // In recent WhatsApp builds the visible text may contain only the presence
  // status (for example, "online"), while the conversation name lives in a
  // title/aria-label attribute. Keep every header representation so the group
  // matcher can still prove which conversation is open.
  const values = [
    header.innerText,
    header.textContent,
    document.querySelector('[data-testid="conversation-info-header-chat-title"]')
      ?.textContent,
    ...Array.from(header.querySelectorAll("[title], [aria-label]")).flatMap(
      (element) => [
        element.getAttribute("title"),
        element.getAttribute("aria-label"),
        element.textContent,
      ]
    ),
  ];
  return Array.from(new Set(values.map((value) => String(value || "").trim()).filter(Boolean)))
    .join(" ");
}

function wlExactElement(root, text) {
  return Array.from(root.querySelectorAll("span, div, button")).find(
    (element) =>
      element.children.length === 0 &&
      (element.textContent || "").trim() === text
  );
}

function wlLeafContaining(root, text) {
  const expected = wlNormalize(text);
  return Array.from(root.querySelectorAll("span, div, button")).find(
    (element) =>
      element.children.length === 0 &&
      wlNormalize(element.textContent || "").includes(expected)
  );
}

function wlHasDate(panel, label) {
  const normalizedText = wlNormalize(panel.innerText || panel.textContent || "");
  const direct = wlNormalize(label);
  if (normalizedText.includes(direct)) return true;
  const match = /^(\d{2})\/(\d{2})\/(\d{4})$/.exec(label);
  if (!match) return false;
  const months = [
    "janeiro", "fevereiro", "marco", "abril", "maio", "junho",
    "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
  ];
  const day = String(Number(match[1]));
  const month = months[Number(match[2]) - 1];
  const year = match[3];
  if (normalizedText.includes(`${day} de ${month} de ${year}`)) return true;

  const target = new Date(Number(year), Number(match[2]) - 1, Number(day), 12);
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate(), 12);
  const daysAgo = Math.round((today - target) / 86400000);
  if (daysAgo === 0 && /(^|\s)hoje($|\s)/.test(normalizedText)) return true;
  if (daysAgo === 1 && /(^|\s)ontem($|\s)/.test(normalizedText)) return true;
  if (daysAgo >= 2 && daysAgo <= 7) {
    const weekdays = [
      "domingo", "segunda-feira", "terca-feira", "quarta-feira",
      "quinta-feira", "sexta-feira", "sabado",
    ];
    return normalizedText.includes(weekdays[target.getDay()]);
  }
  return false;
}

function wlMessageScroller(panel) {
  const candidates = [];
  let current = panel;
  while (current && current !== document.body) {
    if (current.scrollHeight > current.clientHeight + 20) candidates.push(current);
    current = current.parentElement;
  }
  candidates.push(...Array.from(panel.querySelectorAll("div")).filter(
    (element) => element.scrollHeight > element.clientHeight + 20
  ));
  return candidates.find((element) => {
    const overflow = getComputedStyle(element).overflowY;
    return overflow === "auto" || overflow === "scroll";
  }) || candidates[0] || null;
}

function wlAccessibleText(element) {
  return `${element?.getAttribute?.("aria-label") || ""} ${element?.getAttribute?.("title") || ""} ${element?.innerText || element?.textContent || ""}`;
}

function wlRequestTrustedClick(element) {
  return new Promise((resolve) => {
    let finished = false;
    const finish = (value) => {
      if (finished) return;
      finished = true;
      clearTimeout(timeout);
      resolve(value);
    };
    const timeout = setTimeout(() => finish(false), 1200);
    const rectangle = element?.getBoundingClientRect?.();
    if (!rectangle || rectangle.width <= 0 || rectangle.height <= 0) {
      finish(false);
      return;
    }
    chrome.runtime.sendMessage({
      type: "WL_TRUSTED_CLICK",
      x: rectangle.left + (rectangle.width / 2),
      y: rectangle.top + (rectangle.height / 2),
    }, (response) => {
      void chrome.runtime.lastError;
      finish(Boolean(response?.ok));
    });
  });
}

function wlRequestTrustedPoint(x, y) {
  return new Promise((resolve) => {
    let finished = false;
    const finish = (value) => {
      if (finished) return;
      finished = true;
      clearTimeout(timeout);
      resolve(value);
    };
    const timeout = setTimeout(() => finish(false), 1800);
    chrome.runtime.sendMessage({ type: "WL_TRUSTED_CLICK", x, y }, (response) => {
      void chrome.runtime.lastError;
      finish(Boolean(response?.ok));
    });
  });
}

function wlRequestTrustedKey(key) {
  return new Promise((resolve) => {
    let finished = false;
    const finish = (value) => {
      if (finished) return;
      finished = true;
      clearTimeout(timeout);
      resolve(value);
    };
    const timeout = setTimeout(() => finish(false), 1800);
    chrome.runtime.sendMessage({ type: "WL_TRUSTED_KEY", key }, (response) => {
      void chrome.runtime.lastError;
      finish(Boolean(response?.ok));
    });
  });
}

function wlRequestTrustedText(text) {
  return new Promise((resolve) => {
    let finished = false;
    const finish = (value) => {
      if (finished) return;
      finished = true;
      clearTimeout(timeout);
      resolve(value);
    };
    const timeout = setTimeout(() => finish(false), 2500);
    chrome.runtime.sendMessage({ type: "WL_TRUSTED_TEXT", text }, (response) => {
      void chrome.runtime.lastError;
      finish(Boolean(response?.ok));
    });
  });
}

function wlStartTrustedSession(sessionId) {
  return new Promise((resolve) => {
    let finished = false;
    const finish = (value) => {
      if (finished) return;
      finished = true;
      clearTimeout(timeout);
      resolve(value);
    };
    const timeout = setTimeout(() => finish({
      claimed: true,
      trusted: false,
      owned: false,
      warning: "O clique avançado do Chrome não respondeu; seguindo em modo compatível.",
    }), 4000);
    chrome.runtime.sendMessage({
      type: "WL_TRUSTED_START",
      session_id: sessionId,
    }, (response) => {
      void chrome.runtime.lastError;
      finish({
        claimed: Boolean(response?.ok),
        trusted: Boolean(response?.trusted),
        owned: Boolean(response?.owned),
        warning: String(response?.warning || response?.error || ""),
      });
    });
  });
}

function wlCalendarCells(root) {
  return Array.from(
    root?.querySelectorAll?.('[role="gridcell"], button, [role="button"]') || []
  ).filter((element) => {
    const label = wlNormalize(
      `${element.getAttribute("aria-label") || ""} ` +
      `${element.getAttribute("title") || ""} ` +
      `${element.innerText || element.textContent || ""}`
    );
    return /^(?:[1-9]|[12]\d|3[01])$/.test(label) ||
      /\b(?:[1-9]|[12]\d|3[01])\s+de\s+[a-z]+\s+de\s+\d{4}\b/.test(label);
  });
}

function wlCalendarGrid() {
  // WhatsApp has used both an ARIA grid and a dialog made only of buttons.
  // Identify the calendar by its set of day controls instead of depending on
  // one transient role/test id.
  const selector = [
    '[role="grid"]',
    '[role="dialog"]',
    '[data-testid*="calendar" i]',
    '[aria-label*="calendar" i]',
    '[aria-label*="calend" i]',
  ].join(', ');
  const candidates = Array.from(document.querySelectorAll(selector));
  return candidates.find((candidate) => {
    const label = wlNormalize(
      `${candidate.getAttribute("aria-label") || ""} ` +
      `${candidate.getAttribute("title") || ""}`
    );
    const text = wlNormalize(candidate.innerText || candidate.textContent || "");
    const cells = wlCalendarCells(candidate);
    return cells.length >= 20 && (
      label.includes("escolher data") ||
      label.includes("calendar") ||
      label.includes("calendario") ||
      /\b(?:de\s+)?[a-z]+\s+de\s+\d{4}\b/.test(text)
    );
  }) || null;
}

function wlFindGotoDateButton(root = document) {
  return Array.from(root.querySelectorAll('button, [role="button"]')).find((button) => {
    const label = wlNormalize(wlAccessibleText(button));
    const icon = button.querySelector(
      '[data-icon*="calendar"], [data-testid*="calendar"], [aria-label*="calend"]'
    );
    return label.includes("ir para a data") ||
      label.includes("pesquisar por data") ||
      label.includes("buscar por data") ||
      label.includes("calendario") ||
      Boolean(icon);
  }) || null;
}

async function wlNavigateToDate(panel, config) {
  wlNavigationStage = "iniciando";
  wlNavigationDateReached = false;
  if (wlHasDate(panel, config.start_label)) {
    wlNavigationStage = "data já visível";
    wlNavigationDateReached = true;
    return true;
  }
  const main = document.querySelector("#main");
  if (!main) {
    wlNavigationStage = "painel principal ausente";
    return false;
  }
  const buttonSelector = 'button, [role="button"]';
  let gotoDateButton = wlFindGotoDateButton();
  if (!gotoDateButton) {
    const searchButton = Array.from(main.querySelectorAll(`header ${buttonSelector}`)).find(
      (button) => wlNormalize(wlAccessibleText(button)).includes("pesquisar")
    );
    if (!searchButton) {
      wlNavigationStage = "botão Pesquisar ausente";
      return false;
    }
    wlNavigationStage = "abrindo pesquisa";
    const trustedSearch = await wlRequestTrustedClick(searchButton);
    if (!trustedSearch) searchButton.click();
    for (let wait = 0; wait < 40 && !gotoDateButton; wait += 1) {
      await wlSleep(100);
      gotoDateButton = wlFindGotoDateButton();
    }
  }
  if (!gotoDateButton) {
    wlNavigationStage = "botão Ir para a data ausente";
    return false;
  }
  wlNavigationStage = "abrindo calendário";
  const trustedCalendar = await wlRequestTrustedClick(gotoDateButton);
  if (!trustedCalendar) gotoDateButton.click();
  for (let wait = 0; wait < 20; wait += 1) {
    if (wlCalendarGrid()) break;
    await wlSleep(100);
  }
  let calendarGrid = wlCalendarGrid();
  if (!calendarGrid) {
    wlNavigationStage = "calendário não abriu";
    return false;
  }

  const dateMatch = /^(\d{1,2})\/(\d{1,2})\/(\d{4})$/.exec(config.start_label);
  if (!dateMatch) {
    wlNavigationStage = "data inicial inválida";
    return false;
  }
  const day = String(Number(dateMatch[1]));
  const monthIndex = Number(dateMatch[2]) - 1;
  const year = Number(dateMatch[3]);
  const months = [
    "janeiro", "fevereiro", "marco", "abril", "maio", "junho",
    "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
  ];
  const desiredMonth = `${months[monthIndex]} de ${year}`;

  for (let attempt = 0; attempt < 36; attempt += 1) {
    // O WhatsApp substitui o calendário inteiro ao trocar de mês. Sempre
    // recupere a grade viva; consultar a grade anterior fazia agosto ser
    // procurado no DOM já removido de setembro.
    calendarGrid = wlCalendarGrid();
    if (!calendarGrid) {
      wlNavigationStage = "calendário desapareceu ao trocar de mês";
      return false;
    }
    const calendarRoot = calendarGrid.closest('[role="dialog"]') || document;
    const heading = Array.from(calendarRoot.querySelectorAll('[role="heading"], h2')).find(
      (element) => /\bde\s+\d{4}\b/.test(wlNormalize(element.textContent || ""))
    );
    const currentMonth = wlNormalize(
      `${heading?.textContent || ""} ${calendarGrid.innerText || calendarGrid.textContent || ""}`
    );
    if (currentMonth.includes(desiredMonth)) break;
    const previous = Array.from(calendarRoot.querySelectorAll(buttonSelector)).find(
      (button) => wlNormalize(wlAccessibleText(button)).includes("mes anterior")
    );
    if (!previous || previous.disabled) {
      wlNavigationStage = "mês desejado não disponível";
      return false;
    }
    const previousGrid = calendarGrid;
    previous.click();
    for (let wait = 0; wait < 20; wait += 1) {
      await wlSleep(100);
      const refreshedGrid = wlCalendarGrid();
      const refreshedRoot = refreshedGrid?.closest('[role="dialog"]') || document;
      const refreshedHeading = Array.from(
        refreshedRoot.querySelectorAll('[role="heading"], h2')
      ).find((element) =>
        /\bde\s+\d{4}\b/.test(wlNormalize(element.textContent || ""))
      );
      const refreshedMonth = wlNormalize(
        `${refreshedHeading?.textContent || ""} ` +
        `${refreshedGrid?.innerText || refreshedGrid?.textContent || ""}`
      );
      if (
        refreshedGrid &&
        (refreshedGrid !== previousGrid || refreshedMonth !== currentMonth)
      ) break;
    }
  }

  calendarGrid = wlCalendarGrid();
  if (!calendarGrid) {
    wlNavigationStage = "calendário indisponível para selecionar o dia";
    return false;
  }
  const desiredDate = `${day} de ${months[monthIndex]} de ${year}`;
  const dateElement = wlCalendarCells(calendarGrid).find(
    (element) => {
      const label = wlNormalize(
        `${element.getAttribute("aria-label") || ""} ` +
        `${element.getAttribute("title") || ""} ` +
        `${element.innerText || element.textContent || ""}`
      );
      // The new calendar exposes some days only as a numeric button. The
      // month was already verified above, so an exact day number is safe.
      return label.includes(desiredDate) || label === day;
    }
  );
  if (!dateElement) {
    wlNavigationStage = "dia não encontrado no calendário";
    return false;
  }
  wlNavigationStage = "selecionando dia";
  wlNavigationDateReached = true;
  if (dateElement.disabled || dateElement.getAttribute("aria-disabled") === "true") {
    wlNavigationStage = "dia alcançado sem mensagens";
    return false;
  }
  const trustedClick = await wlRequestTrustedClick(dateElement);
  if (!trustedClick) dateElement.click();
  const found = await new Promise((resolve) => {
    const check = () => {
      const refreshedPanel = document.querySelector('[data-testid="conversation-panel-messages"]');
      return Boolean(refreshedPanel && wlHasDate(refreshedPanel, config.start_label));
    };
    if (check()) {
      resolve(true);
      return;
    }
    const observer = new MutationObserver(() => {
      if (!check()) return;
      observer.disconnect();
      clearTimeout(timeout);
      resolve(true);
    });
    observer.observe(document.querySelector("#main") || document.body, {
      childList: true,
      subtree: true,
      characterData: true,
    });
    const timeout = setTimeout(() => {
      observer.disconnect();
      resolve(check());
    }, 20000);
  });
  wlNavigationStage = found ? "data encontrada" : "dia selecionado sem carregar histórico";
  return found;
}

function wlDateKey(value) {
  const match = /^(\d{1,2})\/(\d{1,2})\/(\d{4})$/.exec(value || "");
  if (!match) return 0;
  return Number(`${match[3]}${match[2].padStart(2, "0")}${match[1].padStart(2, "0")}`);
}

function wlVisibleChronologyDates(panel) {
  const labels = [];
  for (const metadata of panel.querySelectorAll("[data-pre-plain-text]")) {
    const plain = metadata.getAttribute("data-pre-plain-text") || "";
    const match = /^\[\d{1,2}:\d{2},\s*(\d{1,2}\/\d{1,2}\/\d{4})\]/.exec(plain);
    if (match) labels.push(match[1]);
  }
  for (const element of panel.querySelectorAll("span, div")) {
    if (element.children.length !== 0) continue;
    const text = (element.textContent || "").trim();
    if (/^\d{1,2}\/\d{1,2}\/\d{4}$/.test(text)) labels.push(text);
  }
  return Array.from(new Set(labels.map((label) => {
    const parts = label.split("/");
    return wlDateFromParts(Number(parts[0]), Number(parts[1]), Number(parts[2]));
  }).filter(Boolean)));
}

// A quinzena is a date interval, not a requirement that a message exists on
// its first calendar day. Sundays/holidays can have no group activity; in
// that case the first message on the next active day is the valid start.
function wlFirstPeriodDate(inventory, config) {
  const startKey = wlDateKey(config.start_label);
  const endKey = wlDateKey(config.end_label);
  return inventory
    .map((item) => item?.message_date || "")
    .filter((label) => {
      const key = wlDateKey(label);
      return key >= startKey && key <= endKey;
    })
    .sort((left, right) => wlDateKey(left) - wlDateKey(right))[0] || "";
}

function wlHasPeriodEvidence(inventory, config) {
  return Boolean(wlFirstPeriodDate(inventory, config));
}

function wlDateLabelsInRange(startLabel, endLabel) {
  const parse = (value) => {
    const match = /^(\d{1,2})\/(\d{1,2})\/(\d{4})$/.exec(value || "");
    return match
      ? new Date(Number(match[3]), Number(match[2]) - 1, Number(match[1]), 12)
      : null;
  };
  const start = parse(startLabel);
  const configuredEnd = parse(endLabel);
  if (!start || !configuredEnd) return [];
  const today = new Date();
  const currentDay = new Date(today.getFullYear(), today.getMonth(), today.getDate(), 12);
  const end = configuredEnd < currentDay ? configuredEnd : currentDay;
  const labels = [];
  for (const cursor = new Date(start); cursor <= end; cursor.setDate(cursor.getDate() + 1)) {
    labels.push(wlDateFromParts(cursor.getDate(), cursor.getMonth() + 1, cursor.getFullYear()));
  }
  return labels;
}

function wlSimpleHash(value) {
  let hash = 5381;
  for (const character of String(value || "")) {
    hash = ((hash << 5) + hash) ^ character.charCodeAt(0);
  }
  return (hash >>> 0).toString(16);
}

function wlDateFromParts(day, month, year) {
  return `${String(day).padStart(2, "0")}/${String(month).padStart(2, "0")}/${year}`;
}

function wlRelativeDate(label, _currentDate) {
  const normalized = wlNormalize(label);
  const today = new Date();
  if (normalized === "hoje") {
    return wlDateFromParts(today.getDate(), today.getMonth() + 1, today.getFullYear());
  }
  if (normalized === "ontem") {
    const yesterday = new Date(today.getFullYear(), today.getMonth(), today.getDate() - 1);
    return wlDateFromParts(yesterday.getDate(), yesterday.getMonth() + 1, yesterday.getFullYear());
  }
  const weekdayMap = {
    "domingo": 0,
    "segunda-feira": 1,
    "terca-feira": 2,
    "quarta-feira": 3,
    "quinta-feira": 4,
    "sexta-feira": 5,
    "sabado": 6,
  };
  if (!(normalized in weekdayMap)) return "";
  let daysBack = (today.getDay() - weekdayMap[normalized] + 7) % 7;
  if (daysBack === 0) daysBack = 7;
  const previous = new Date(today.getFullYear(), today.getMonth(), today.getDate() - daysBack);
  return wlDateFromParts(previous.getDate(), previous.getMonth() + 1, previous.getFullYear());
}

function wlCollectInventoryFromRows(panel, config, knownIds, dateState = null) {
  const startKey = wlDateKey(config.start_label);
  const endKey = wlDateKey(config.end_label);
  const records = [];
  let currentDate = dateState?.current_date || "";
  const elements = Array.from(panel.querySelectorAll('[role="row"], div, span'));

  for (const [index, element] of elements.entries()) {
    const isRow = element.getAttribute("role") === "row";
    if (!isRow) {
      if (element.children.length !== 0 || element.closest('[role="row"]')) continue;
      const label = (element.textContent || "").trim();
      if (/^\d{1,2}\/\d{1,2}\/\d{4}$/.test(label)) {
        const parts = label.split("/");
        currentDate = wlDateFromParts(Number(parts[0]), Number(parts[1]), Number(parts[2]));
      } else {
        const relative = wlRelativeDate(label, currentDate);
        if (relative) currentDate = relative;
      }
      continue;
    }
    if (element.parentElement?.closest('[role="row"]')) continue;
    const dateKey = wlDateKey(currentDate);
    if (!dateKey || dateKey < startKey || dateKey > endKey) continue;

    const text = element.innerText || element.textContent || "";
    const buttons = Array.from(element.querySelectorAll('button, [role="button"]'));
    const accessible = buttons.map(wlAccessibleText).join("\n");
    const normalized = wlNormalize(`${text}\n${accessible}`);
    const mediaButtons = buttons.filter((button) =>
      wlNormalize(wlAccessibleText(button)).includes("abrir imagem")
    );
    let imageCount = mediaButtons.length;
    const imageSources = Array.from(new Set(mediaButtons.flatMap((button) =>
      Array.from(button.querySelectorAll("img[src]"))
        .filter((image) => image.naturalWidth >= 200 && image.naturalHeight >= 200)
        .map((image) => image.currentSrc || image.getAttribute("src") || "")
    ))).filter((source) => /^(blob:|data:image\/|https:)/i.test(source));
    const albumMatch = /album de midias\s+(\d+)\s+fotos?/.exec(normalized);
    if (albumMatch) imageCount = Math.max(imageCount, Number(albumMatch[1]));
    if (!imageCount && /(^|\s)foto($|\s)/.test(normalized)) imageCount = 1;

    const pdfNames = Array.from(new Set(
      buttons.flatMap((button) =>
        ((button.innerText || button.textContent || "").match(/[^\n\r•]{1,100}\.pdf\b/gi) || [])
          .map((name) => name.trim().replace(/^PDF\s+/i, ""))
      )
    ));
    const stakeMatch = text.match(/\b\d+(?:\s*[x\u00d7]\s*\d+)+(?:\s*[+=]\s*\d+)\b/i);
    const stakeText = stakeMatch ? stakeMatch[0] : "";
    const quantityHint = imageCount && !stakeText
      ? globalThis.wlQuantityHint?.(wlMessageCaptionText(element, text)) ?? null
      : null;
    if (!imageCount && !pdfNames.length && !stakeText) continue;

    const timeMatch = text.match(/\b\d{1,2}:\d{2}\b/);
    const messageTime = timeMatch ? timeMatch[0] : "";
    const firstButton = buttons.find((button) => {
      const value = wlNormalize(wlAccessibleText(button));
      return value && !/abrir imagem|encaminhar|reacao|pdf|mostrar/.test(value);
    });
    const sender = (firstButton?.innerText || firstButton?.textContent || "").trim();
    const idElement = element.querySelector("[data-id]") || element.closest("[data-id]");
    const messageId = idElement?.getAttribute("data-id") ||
      `wl-${currentDate}-${messageTime}-${wlSimpleHash(`${sender}|${text}|${index}`)}`;
    const albumIdMatch = /^album-.*-(\d+)$/.exec(messageId);
    if (albumIdMatch) imageCount = Math.max(imageCount, Number(albumIdMatch[1]));
    if (knownIds.has(messageId)) continue;
    knownIds.add(messageId);
    records.push({
      message_id: messageId,
      message_date: currentDate,
      message_time: messageTime,
      sender,
      image_count: imageCount,
      image_sources: imageSources,
      media_elements: mediaButtons,
      pdf_names: pdfNames,
      stake_text: stakeText,
      quantity_hint: quantityHint,
      has_ok: accessible.includes("\u{1F197}"),
    });
  }
  if (dateState) dateState.current_date = currentDate;
  return records;
}

function wlCollectInventory(panel, config, options = {}) {
  const startKey = wlDateKey(config.start_label);
  const endKey = wlDateKey(config.end_label);
  const records = [];
  const seen = options.seen || new Set();
  const metadataElements = Array.from(panel.querySelectorAll("[data-pre-plain-text]"));

  for (const [index, metadata] of metadataElements.entries()) {
    const plain = metadata.getAttribute("data-pre-plain-text") || "";
    const parsed = /^\[(\d{1,2}:\d{2}),\s*(\d{1,2}\/\d{1,2}\/\d{4})\]\s*(.*?):\s*$/.exec(plain);
    if (!parsed) continue;
    const messageTime = parsed[1];
    const messageDate = parsed[2].split("/").map((part, partIndex) =>
      partIndex < 2 ? part.padStart(2, "0") : part
    ).join("/");
    const dateKey = wlDateKey(messageDate);
    if (!dateKey || dateKey < startKey || dateKey > endKey) continue;

    const sender = parsed[3].replace(/^~\s*/, "").trim();
    const bubble = metadata.closest('[role="row"]') || metadata.parentElement;
    if (!bubble) continue;
    const text = bubble.innerText || bubble.textContent || "";
    const buttons = Array.from(bubble.querySelectorAll('button, [role="button"]'));
    const accessible = buttons.map((button) =>
      `${button.getAttribute("aria-label") || ""} ${button.getAttribute("title") || ""} ${button.innerText || button.textContent || ""}`
    ).join("\n");
    const normalized = wlNormalize(`${text}\n${accessible}`);

    const mediaButtons = buttons.filter((button) =>
      wlNormalize(`${button.getAttribute("aria-label") || ""} ${button.getAttribute("title") || ""}`)
        .includes("abrir imagem")
    );
    let imageCount = mediaButtons.length;
    const imageSources = Array.from(new Set(mediaButtons.flatMap((button) =>
      Array.from(button.querySelectorAll("img[src]"))
        .filter((image) => image.naturalWidth >= 200 && image.naturalHeight >= 200)
        .map((image) => image.currentSrc || image.getAttribute("src") || "")
    ))).filter((source) => /^(blob:|data:image\/|https:)/i.test(source));
    const albumMatch = /album de midias\s+(\d+)\s+fotos?/.exec(normalized);
    if (albumMatch) imageCount = Math.max(imageCount, Number(albumMatch[1]));
    if (!imageCount && /(^|\s)foto($|\s)/.test(normalized)) imageCount = 1;

    const pdfNames = Array.from(new Set(
      buttons.flatMap((button) => {
        const buttonText = button.innerText || button.textContent || "";
        return (buttonText.match(/[^\n\r•]{1,100}\.pdf\b/gi) || [])
          .map((name) => name.trim().replace(/^PDF\s+/i, ""));
      })
    ));
    const stakeMatch = text.match(/\b\d+(?:\s*[x\u00d7]\s*\d+)+(?:\s*[+=]\s*\d+)\b/i);
    const stakeText = stakeMatch ? stakeMatch[0] : "";
    const quantityHint = imageCount && !stakeText
      ? globalThis.wlQuantityHint?.(wlMessageCaptionText(bubble, text)) ?? null
      : null;
    if (!imageCount && !pdfNames.length && !stakeText) continue;

    const idElement = metadata.closest("[data-id]") || bubble.querySelector("[data-id]");
    const messageId = idElement?.getAttribute("data-id") ||
      `wl-${messageDate}-${messageTime}-${wlSimpleHash(`${sender}|${text}|${index}`)}`;
    const albumIdMatch = /^album-.*-(\d+)$/.exec(messageId);
    if (albumIdMatch) imageCount = Math.max(imageCount, Number(albumIdMatch[1]));
    if (seen.has(messageId)) continue;
    seen.add(messageId);
    records.push({
      message_id: messageId,
      message_date: messageDate,
      message_time: messageTime,
      sender,
      image_count: imageCount,
      image_sources: imageSources,
      media_elements: mediaButtons,
      pdf_names: pdfNames,
      stake_text: stakeText,
      quantity_hint: quantityHint,
      has_ok: accessible.includes("\u{1F197}"),
    });
  }
  records.push(...wlCollectInventoryFromRows(panel, config, seen, options.date_state));
  return records;
}

function wlRemoveAlbumDuplicates(inventory) {
  const albumKeys = new Set(
    inventory
      .filter((item) => String(item.message_id || "").startsWith("album-"))
      .map((item) => `${item.message_date}|${item.message_time}|${item.sender}`)
  );
  return inventory.filter((item) => {
    if (String(item.message_id || "").startsWith("album-")) return true;
    if (!item.image_count) return true;
    const key = `${item.message_date}|${item.message_time}|${item.sender}`;
    return !albumKeys.has(key);
  });
}

function wlSummarizeInventory(inventory) {
  const uniqueInventory = wlRemoveAlbumDuplicates(inventory);
  const publicInventory = uniqueInventory.map(({
    image_sources: _sources,
    media_elements: _elements,
    ...item
  }) => item);
  const stakes = uniqueInventory.map((item) => item.stake_text).filter(Boolean);
  const incompleteAlbums = uniqueInventory
    .filter((item) =>
      item.image_count > 1 &&
      Number(item.album_captured_count || 0) < item.image_count
    )
    .map((item) => ({
      message_id: item.message_id,
      expected: item.image_count,
      captured: Number(item.album_captured_count || 0),
    }));
  return {
    visible_images: uniqueInventory.reduce((total, item) => total + item.image_count, 0),
    visible_pdfs: uniqueInventory.reduce((total, item) => total + item.pdf_names.length, 0),
    ok_reactions: uniqueInventory.filter((item) => item.has_ok).length,
    stake_messages: stakes.slice(0, 20),
    incomplete_albums: incompleteAlbums,
    evidences: publicInventory.slice(0, 1000),
    evidence_truncated: uniqueInventory.length > 1000,
  };
}

function wlBlobToBase64(blob) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(reader.error || new Error("Falha ao ler a foto."));
    reader.onload = () => {
      const value = String(reader.result || "");
      const comma = value.indexOf(",");
      if (comma < 0) reject(new Error("Foto sem conteudo reconhecido."));
      else resolve(value.slice(comma + 1));
    };
    reader.readAsDataURL(blob);
  });
}

function wlWithTimeout(promise, milliseconds, message) {
  return new Promise((resolve, reject) => {
    const timeout = setTimeout(() => reject(new Error(message)), milliseconds);
    Promise.resolve(promise).then(
      (value) => {
        clearTimeout(timeout);
        resolve(value);
      },
      (error) => {
        clearTimeout(timeout);
        reject(error);
      }
    );
  });
}

function wlAttachmentExtension(mimeType) {
  const normalized = String(mimeType || "").toLowerCase();
  if (normalized.includes("png")) return "png";
  if (normalized.includes("webp")) return "webp";
  if (normalized.includes("gif")) return "gif";
  return "jpg";
}

function wlSendAttachment(payload) {
  return new Promise((resolve) => {
    let finished = false;
    const finish = (value) => {
      if (finished) return;
      finished = true;
      clearTimeout(timeout);
      resolve(value);
    };
    const timeout = setTimeout(() => finish({ ok: false, error: "tempo limite ao enviar para o aplicativo local" }), 12000);
    chrome.runtime.sendMessage({ type: "WL_UPLOAD_ATTACHMENT", payload }, (response) => {
      const runtimeError = chrome.runtime.lastError;
      if (runtimeError) {
        finish({ ok: false, error: runtimeError.message || "falha de comunicação com a extensão" });
        return;
      }
      finish({ ok: Boolean(response?.ok), error: String(response?.error || response?.data?.error || "") });
    });
  });
}

async function wlUploadAttachment(config, item, source, sourceIndex) {
  const controller = new AbortController();
  const abortTimer = setTimeout(() => controller.abort(), 12000);
  let response;
  try {
    response = await fetch(source, { signal: controller.signal });
  } finally {
    clearTimeout(abortTimer);
  }
  if (!response.ok) throw new Error(`Foto indisponivel (${response.status}).`);
  const blob = await wlWithTimeout(
    response.blob(), 12000, "A foto demorou demais para carregar."
  );
  if (!blob.size || blob.size > 12_000_000) {
    throw new Error("Foto vazia ou acima do limite de 12 MB.");
  }
  const mimeType = blob.type || "image/jpeg";
  const base64 = await wlWithTimeout(
    wlBlobToBase64(blob), 12000, "A foto demorou demais para ser preparada."
  );
  const payload = {
    session_id: config.session_id,
    token: config.token,
    message_id: item.message_id,
    filename: `foto_${sourceIndex + 1}.${wlAttachmentExtension(mimeType)}`,
    mime_type: mimeType,
    base64,
  };
  const firstAttempt = await wlSendAttachment(payload);
  if (firstAttempt?.ok) return true;
  if (firstAttempt?.error) wlAttachmentErrors.push(firstAttempt.error);
  await wlSleep(250);
  const secondAttempt = await wlSendAttachment(payload);
  if (secondAttempt?.ok) return true;
  if (secondAttempt?.error) wlAttachmentErrors.push(secondAttempt.error);
  return false;
}

function wlLargestLoadedImage(root) {
  const focused = root?.querySelector?.('[data-testid="media-image"] img[src]');
  if (focused?.naturalWidth >= 200 && focused?.naturalHeight >= 200) return focused;
  return Array.from(root?.querySelectorAll?.("img[src]") || [])
    .filter((image) => image.naturalWidth >= 200 && image.naturalHeight >= 200)
    .sort((left, right) =>
      (right.naturalWidth * right.naturalHeight) -
      (left.naturalWidth * left.naturalHeight)
    )[0] || null;
}

function wlMediaViewerRoot(panel) {
  const mediaViewer = document.querySelector('[data-testid="media-viewer-modal"]');
  if (mediaViewer) return mediaViewer;
  const dialogs = Array.from(document.querySelectorAll('[role="dialog"]'));
  const animated = Array.from(document.querySelectorAll('[data-animate-modal-popup]'));
  return dialogs.find((dialog) => wlLargestLoadedImage(dialog)) ||
    animated.find((modal) => wlLargestLoadedImage(modal)) ||
    dialogs.find((dialog) => !panel?.contains?.(dialog)) ||
    null;
}

function wlViewerButton(root, words) {
  return Array.from(root?.querySelectorAll?.('button, [role="button"]') || []).find(
    (button) => words.some((word) =>
      wlNormalize(wlAccessibleText(button)).includes(word)
    )
  ) || null;
}

async function wlWaitForViewerImage(root, previousSource = "") {
  for (let wait = 0; wait < 45; wait += 1) {
    const currentRoot = wlMediaViewerRoot(null) || root;
    const image = wlLargestLoadedImage(currentRoot);
    const source = image?.currentSrc || image?.getAttribute?.("src") || "";
    if (source && source !== previousSource) return { image, source, root: currentRoot };
    await wlSleep(100);
  }
  return null;
}

function wlNextViewerButton(root) {
  const explicit = wlViewerButton(
    root, ["proximo", "proxima", "avancar", "seguinte", "next"]
  );
  if (explicit) return explicit;

  const icon = root?.querySelector?.(
    '[data-testid*="next"], [data-icon*="next"], [data-icon*="right"], ' +
    '[aria-label*="Próx"], [aria-label*="prox" i], [title*="Próx"], [title*="prox" i]'
  );
  if (icon) return icon.closest?.('button, [role="button"]') || icon;

  const candidates = Array.from(
    root?.querySelectorAll?.('button, [role="button"]') || []
  ).filter((button) => {
    const rectangle = button.getBoundingClientRect?.();
    if (!rectangle || rectangle.width <= 0 || rectangle.height <= 0) return false;
    const centerX = rectangle.left + (rectangle.width / 2);
    const centerY = rectangle.top + (rectangle.height / 2);
    return centerX > window.innerWidth * 0.65 &&
      centerY > window.innerHeight * 0.18 &&
      centerY < window.innerHeight * 0.85 &&
      rectangle.width <= 180 && rectangle.height <= 180;
  });
  return candidates.sort((left, right) => {
    const leftRect = left.getBoundingClientRect();
    const rightRect = right.getBoundingClientRect();
    return rightRect.left - leftRect.left;
  })[0] || null;
}

function wlPreviousViewerButton(root) {
  const explicit = wlViewerButton(
    root, ["anterior", "voltar", "previous", "prev"]
  );
  if (explicit) return explicit;
  const icon = root?.querySelector?.(
    '[data-testid*="prev"], [data-icon*="prev"], [data-icon*="left"], ' +
    '[aria-label*="Anterior" i], [title*="Anterior" i]'
  );
  return icon?.closest?.('button, [role="button"]') || icon || null;
}

async function wlRewindViewer(viewer, panel, maximumSteps) {
  for (let step = 0; step < maximumSteps; step += 1) {
    viewer = wlMediaViewerRoot(panel) || viewer;
    const image = wlLargestLoadedImage(viewer);
    const previousSource = image?.currentSrc || image?.getAttribute?.("src") || "";
    const previousButton = wlPreviousViewerButton(viewer);
    let moved = false;
    if (previousButton && !previousButton.disabled &&
        previousButton.getAttribute("aria-disabled") !== "true") {
      moved = await wlRequestTrustedClick(previousButton);
      if (!moved) previousButton.click();
    } else {
      moved = await wlRequestTrustedKey("ArrowLeft");
    }
    if (!moved) break;
    const loaded = await wlWaitForViewerImage(viewer, previousSource);
    if (!loaded) break;
    viewer = loaded.root || viewer;
  }
  return wlMediaViewerRoot(panel) || viewer;
}

async function wlAdvanceViewer(viewer, panel, previousSource) {
  for (let attempt = 0; attempt < 2; attempt += 1) {
    viewer = wlMediaViewerRoot(panel) || viewer;
    const nextButton = wlNextViewerButton(viewer);
    if (!nextButton) return null;
    const advanced = await wlRequestTrustedClick(nextButton);
    if (!advanced) nextButton.click();
    const loaded = await wlWaitForViewerImage(viewer, previousSource);
    if (loaded) return loaded;
  }
  const keyboardAdvanced = await wlRequestTrustedKey("ArrowRight");
  if (!keyboardAdvanced) {
    const target = document.activeElement || viewer || document.body;
    target.dispatchEvent(new KeyboardEvent("keydown", {
      key: "ArrowRight", code: "ArrowRight", bubbles: true,
    }));
    target.dispatchEvent(new KeyboardEvent("keyup", {
      key: "ArrowRight", code: "ArrowRight", bubbles: true,
    }));
  }
  return wlWaitForViewerImage(viewer, previousSource);
}

async function wlWaitForViewerToClose(viewer) {
  for (let wait = 0; wait < 40; wait += 1) {
    if (!document.contains(viewer)) return true;
    const rectangle = viewer.getBoundingClientRect?.();
    if (!rectangle || rectangle.width <= 0 || rectangle.height <= 0) return true;
    await wlSleep(100);
  }
  return false;
}

async function wlCloseExistingViewer() {
  const viewer = wlMediaViewerRoot(null);
  if (!viewer) return true;
  const closeButton = wlViewerButton(viewer, ["fechar", "close"]);
  if (closeButton) {
    const closed = await wlRequestTrustedClick(closeButton);
    if (!closed) closeButton.click();
  } else {
    const closed = await wlRequestTrustedKey("Escape");
    if (!closed) return false;
  }
  return wlWaitForViewerToClose(viewer);
}

async function wlCloseMessageSearch() {
  const heading = Array.from(document.querySelectorAll("h1, h2, h3, div, span")).find(
    (element) =>
      element.children.length === 0 &&
      wlNormalize(element.textContent || "") === "pesquisar mensagens"
  );
  if (!heading) return;
  let container = heading.parentElement;
  let closeButton = null;
  for (let level = 0; container && level < 8; level += 1) {
    closeButton = Array.from(container.querySelectorAll('button, [role="button"]')).find(
      (button) => wlNormalize(wlAccessibleText(button)) === "fechar"
    );
    if (closeButton) break;
    container = container.parentElement;
  }
  if (!closeButton) return;
  const closed = await wlRequestTrustedClick(closeButton);
  if (!closed) closeButton.click();
  await wlSleep(250);
}

async function wlCaptureAlbumAttachments(item, config, uploadedSources, panel) {
  await wlCloseMessageSearch();
  if (!(await wlCloseExistingViewer())) return 0;
  const opener = (item.media_elements || []).find((element) => {
    return element?.isConnected;
  });
  if (!opener) return 0;
  opener.scrollIntoView({ block: "center", inline: "nearest" });
  await wlSleep(350);
  const visibleOpener = (item.media_elements || []).find((element) => {
    const rectangle = element?.getBoundingClientRect?.();
    return rectangle && rectangle.width > 0 && rectangle.height > 0 &&
      rectangle.bottom > 0 && rectangle.top < window.innerHeight &&
      rectangle.right > 0 && rectangle.left < window.innerWidth;
  });
  if (!visibleOpener) return 0;
  const opened = await wlRequestTrustedClick(visibleOpener);
  if (!opened) visibleOpener.click();

  let viewer = null;
  for (let wait = 0; wait < 30 && !viewer; wait += 1) {
    viewer = wlMediaViewerRoot(panel);
    if (!viewer) await wlSleep(100);
  }
  if (!viewer) {
    visibleOpener.click();
    for (let wait = 0; wait < 30 && !viewer; wait += 1) {
      viewer = wlMediaViewerRoot(panel);
      if (!viewer) await wlSleep(100);
    }
  }
  if (!viewer) return 0;

  // Album previews may open on the fourth (or another) thumbnail. Always
  // rewind to the first photo before counting/copying the sequence.
  viewer = await wlRewindViewer(viewer, panel, item.image_count);

  let captured = 0;
  let previousSource = "";
  let prefetched = null;
  for (let position = 0; position < item.image_count; position += 1) {
    const loaded = prefetched || await wlWaitForViewerImage(viewer, previousSource);
    prefetched = null;
    if (!loaded) break;
    viewer = loaded.root || wlMediaViewerRoot(panel) || viewer;
    previousSource = loaded.source;
    wlNavigationStage = `galeria: preparando foto ${position + 1} de ${item.image_count}`;
    if (!uploadedSources.has(loaded.source)) {
      uploadedSources.add(loaded.source);
      try {
        wlNavigationStage = `galeria: enviando foto ${position + 1} de ${item.image_count}`;
        const uploaded = await wlWithTimeout(
          wlUploadAttachment(config, item, loaded.source, position),
          18000,
          `A foto ${position + 1} excedeu o tempo individual.`
        );
        if (uploaded) captured += 1;
        else uploadedSources.delete(loaded.source);
      } catch (error) {
        wlAttachmentErrors.push(String(error?.message || error));
        uploadedSources.delete(loaded.source);
      }
    }
    if (position + 1 >= item.image_count) break;
    wlNavigationStage = `galeria: avançando para foto ${position + 2} de ${item.image_count}`;
    prefetched = await wlAdvanceViewer(viewer, panel, previousSource);
    if (!prefetched) break;
  }

  wlNavigationStage = `galeria encerrada: ${captured} de ${item.image_count}`;

  const closeButton = wlViewerButton(viewer, ["fechar", "close"]);
  if (closeButton) {
    const closed = await wlRequestTrustedClick(closeButton);
    if (!closed) closeButton.click();
    await wlWaitForViewerToClose(viewer);
  } else {
    const closed = await wlRequestTrustedKey("Escape");
    if (!closed) {
      document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
    }
  }
  return captured;
}

async function wlUploadInventoryAttachments(items, config, uploadedSources) {
  const pending = [];
  const directCounts = new Map();
  for (const item of items) {
    if (item.image_count > 1) {
      const panel = document.querySelector('[data-testid="conversation-panel-messages"]');
      let captured = await wlCaptureAlbumAttachments(
        item, config, uploadedSources, panel
      );
      // A galeria do WhatsApp pode trocar o blob da miniatura enquanto
      // avança. Repetimos somente o álbum incompleto, preservando as fontes
      // já salvas, para recuperar fotos que falharam na primeira passagem.
      for (let retry = 0; retry < 2 && captured < item.image_count; retry += 1) {
        await wlSleep(500);
        captured += await wlCaptureAlbumAttachments(
          item, config, uploadedSources, panel
        );
      }
      item.album_captured_count = captured;
      if (captured > 0) continue;
    }
    for (const [sourceIndex, source] of (item.image_sources || []).entries()) {
      if (uploadedSources.has(source)) continue;
      uploadedSources.add(source);
      pending.push({ item, source, sourceIndex });
    }
  }
  let nextIndex = 0;
  const worker = async () => {
    while (nextIndex < pending.length) {
      const current = pending[nextIndex];
      nextIndex += 1;
      try {
        const uploaded = await wlUploadAttachment(
          config, current.item, current.source, current.sourceIndex
        );
        if (!uploaded) uploadedSources.delete(current.source);
        else directCounts.set(
          current.item.message_id,
          (directCounts.get(current.item.message_id) || 0) + 1
        );
      } catch (error) {
        wlAttachmentErrors.push(String(error?.message || error));
        uploadedSources.delete(current.source);
      }
    }
  };
  const workers = Array.from(
    { length: Math.min(6, pending.length) },
    () => worker()
  );
  await Promise.all(workers);
  for (const item of items) {
    const direct = directCounts.get(item.message_id) || 0;
    if (direct) {
      item.album_captured_count = Math.max(
        Number(item.album_captured_count || 0), direct
      );
    }
  }
}

function wlCollectEvidence(panel, config) {
  return wlSummarizeInventory(wlCollectInventory(panel, config));
}

async function wlCollectPeriodEvidence(panel, config, base) {
  const inventory = [];
  const seen = new Set();
  const dateState = { current_date: config.start_label };
  let unchangedSteps = 0;
  let recentWaits = 0;
  let scrollMoves = 0;
  let completedSteps = 0;
  let direction = 1;
  let directionChanges = 0;
  let jumpToRecent = false;
  let jumpButtonFound = false;
  let olderLoads = 0;
  let calendarAttempts = 0;
  let calendarDatesFound = 0;
  let calendarDatesReached = 0;
  const chronologyDates = new Set();
  let recentBoundaryReached = false;
  const uploadedSources = new Set();
  const startKey = wlDateKey(config.start_label);
  const endKey = wlDateKey(config.end_label);

  for (let step = 0; step < 300; step += 1) {
    completedSteps = step + 1;
    panel = document.querySelector('[data-testid="conversation-panel-messages"]') || panel;
    const batch = wlCollectInventory(panel, config, { seen, date_state: dateState });
    inventory.push(...batch);
    for (const label of wlVisibleChronologyDates(panel)) chronologyDates.add(label);
    await wlUploadInventoryAttachments(batch, config, uploadedSources);

    if (!jumpToRecent) {
      const jumpButton = Array.from(document.querySelectorAll('button, [role="button"]')).find(
        (element) =>
          wlNormalize(wlAccessibleText(element)).includes("deslizar para o fim da pagina")
      );
      jumpToRecent = true;
      if (jumpButton) {
        jumpButtonFound = true;
        jumpButton.click();
        recentBoundaryReached = true;
        dateState.current_date = "";
        await wlSleep(2000);
        continue;
      }
    }

    if (step > 0 && step % 12 === 0) {
      wlPost({
        ...base,
        final: false,
        group_found: true,
        start_date_found: true,
        ...wlSummarizeInventory(inventory),
        message: `Lendo toda a quinzena: ${inventory.length} mensagens com evidencias encontradas.`,
      });
    }

    const recentLoader = wlLeafContaining(panel, "carregar mensagens recentes");
    if (recentLoader && recentWaits < 45) {
      recentWaits += 1;
      unchangedSteps = 0;
      const recentAction = recentLoader.closest('button, [role="button"]') ||
        recentLoader.parentElement || recentLoader;
      recentAction.click();
      await wlSleep(1000);
      continue;
    }

    const olderRoot = document.querySelector("#main") || panel;
    const olderText = wlLeafContaining(olderRoot, "carregar mensagens mais antigas do seu celular");
    if (olderText && olderLoads < 40 && !wlHasDate(panel, config.start_label)) {
      const olderAction = olderText.closest('button, [role="button"]') || olderText;
      olderLoads += 1;
      olderAction.click();
      await wlSleep(1500);
      continue;
    }

    const scrollable = wlMessageScroller(panel);
    if (!scrollable) break;
    const beforeTop = scrollable.scrollTop;
    const distance = Math.max(300, Math.floor(scrollable.clientHeight * 0.72));
    const target = beforeTop + (direction * distance);
    scrollable.scrollTop = target;
    scrollable.dispatchEvent(new Event("scroll", { bubbles: true }));
    await wlSleep(300);

    const afterTop = scrollable.scrollTop;
    if (Math.abs(afterTop - beforeTop) < 1) {
      unchangedSteps += 1;
      if (direction > 0) recentBoundaryReached = true;
    } else {
      unchangedSteps = 0;
      scrollMoves += 1;
    }
    if (unchangedSteps >= 3) {
      if (directionChanges === 0) {
        direction *= -1;
        directionChanges = 1;
        unchangedSteps = 0;
      } else {
        break;
      }
    }
  }

  const periodLabels = wlDateLabelsInRange(config.start_label, config.end_label);
  for (const label of periodLabels) {
    panel = document.querySelector('[data-testid="conversation-panel-messages"]') || panel;
    calendarAttempts += 1;
    const dateFound = await wlNavigateToDate(panel, { ...config, start_label: label });
    if (dateFound) calendarDatesFound += 1;
    if (wlNavigationDateReached) calendarDatesReached += 1;
    await wlSleep(500);
    await wlCloseMessageSearch();
    panel = document.querySelector('[data-testid="conversation-panel-messages"]') || panel;
    dateState.current_date = dateFound ? label : "";
    const calendarBatch = wlCollectInventory(panel, config, { seen, date_state: dateState });
    inventory.push(...calendarBatch);
    await wlUploadInventoryAttachments(calendarBatch, config, uploadedSources);
    wlPost({
      ...base,
      final: false,
      group_found: true,
      start_date_found: true,
      ...wlSummarizeInventory(inventory),
      calendar_attempts: calendarAttempts,
      calendar_dates_found: calendarDatesFound,
      calendar_dates_reached: calendarDatesReached,
      message: `Calendário: ${label} (${calendarDatesFound} datas confirmadas).`,
    });
  }

  panel = document.querySelector('[data-testid="conversation-panel-messages"]') || panel;
  for (const label of wlVisibleChronologyDates(panel)) chronologyDates.add(label);
  inventory.push(...wlCollectInventory(panel, config, { seen, date_state: dateState }));
  const chronologyKeys = Array.from(chronologyDates).map(wlDateKey).filter(Boolean);
  const earliestChronologyKey = chronologyKeys.length ? Math.min(...chronologyKeys) : 0;
  const latestChronologyKey = chronologyKeys.length ? Math.max(...chronologyKeys) : 0;
  const crossedStartBoundary = earliestChronologyKey > 0 && earliestChronologyKey < startKey;
  // At the live/recent edge, the absence of messages through the selected end
  // date is itself evidence. This is important for weekends and quiet days.
  const crossedEndBoundary = latestChronologyKey > endKey || recentBoundaryReached;
  const continuousPeriodCovered = crossedStartBoundary && crossedEndBoundary;
  return {
    ...wlSummarizeInventory(inventory),
    start_date_observed: wlHasPeriodEvidence(inventory, config),
    first_period_date: wlFirstPeriodDate(inventory, config),
    scan_steps: completedSteps,
    recent_waits: recentWaits,
    scroll_moves: scrollMoves,
    direction_changes: directionChanges,
    jump_to_recent: jumpButtonFound,
    older_loads: olderLoads,
    calendar_attempts: calendarAttempts,
    calendar_dates_found: calendarDatesFound,
    calendar_dates_reached: calendarDatesReached,
    chronology_first_date: chronologyKeys.length
      ? Array.from(chronologyDates).sort((left, right) => wlDateKey(left) - wlDateKey(right))[0]
      : "",
    chronology_last_date: chronologyKeys.length
      ? Array.from(chronologyDates).sort((left, right) => wlDateKey(right) - wlDateKey(left))[0]
      : "",
    crossed_start_boundary: crossedStartBoundary,
    crossed_end_boundary: crossedEndBoundary,
    period_scan_complete: continuousPeriodCovered || (
      Boolean(periodLabels.length) &&
      calendarAttempts === periodLabels.length &&
      calendarDatesReached === periodLabels.length
    ),
  };
}

async function wlCollectCalendarPeriodEvidence(panel, config, base) {
  const inventory = [];
  const seen = new Set();
  const uploadedSources = new Set();
  const dateState = { current_date: "" };
  let calendarAttempts = 0;
  let calendarDatesFound = 0;
  let localScrollMoves = 0;

  for (const label of wlDateLabelsInRange(config.start_label, config.end_label)) {
    panel = document.querySelector('[data-testid="conversation-panel-messages"]') || panel;
    calendarAttempts += 1;
    const dateFound = await wlNavigateToDate(panel, { ...config, start_label: label });
    if (dateFound) calendarDatesFound += 1;
    await wlSleep(400);
    await wlCloseMessageSearch();
    panel = document.querySelector('[data-testid="conversation-panel-messages"]') || panel;
    if (!dateFound) {
      wlPost({
        ...base,
        final: false,
        group_found: true,
        start_date_found: inventory.some((item) => item.message_date === config.start_label),
        ...wlSummarizeInventory(inventory),
        calendar_attempts: calendarAttempts,
        calendar_dates_found: calendarDatesFound,
        message: `Calendário: ${label} não confirmado (${wlNavigationStage}); nenhuma foto desse dia foi copiada.`,
      });
      continue;
    }
    dateState.current_date = dateFound ? label : "";
    const initialVisible = wlCollectInventory(panel, config, { seen, date_state: dateState });
    for (const item of initialVisible) {
      if (item.message_date !== label) seen.delete(item.message_id);
    }
    const initialBatch = initialVisible.filter((item) => item.message_date === label);
    inventory.push(...initialBatch);
    await wlUploadInventoryAttachments(initialBatch, config, uploadedSources);

    if (dateFound) {
      for (let move = 0; move < 8; move += 1) {
        const scrollable = wlMessageScroller(panel);
        if (!scrollable) break;
        const beforeTop = scrollable.scrollTop;
        const distance = Math.max(220, Math.floor(scrollable.clientHeight * 0.55));
        scrollable.scrollTop = beforeTop + distance;
        scrollable.dispatchEvent(new Event("scroll", { bubbles: true }));
        await wlSleep(220);
        const afterTop = scrollable.scrollTop;
        panel = document.querySelector('[data-testid="conversation-panel-messages"]') || panel;
        const visibleBatch = wlCollectInventory(panel, config, { seen, date_state: dateState });
        const crossedIntoLaterDate = visibleBatch.some(
          (item) => wlDateKey(item.message_date) > wlDateKey(label)
        );
        for (const item of visibleBatch) {
          if (item.message_date !== label) seen.delete(item.message_id);
        }
        const scrollBatch = visibleBatch.filter((item) => item.message_date === label);
        inventory.push(...scrollBatch);
        await wlUploadInventoryAttachments(scrollBatch, config, uploadedSources);
        if (Math.abs(afterTop - beforeTop) >= 1 && !crossedIntoLaterDate) {
          localScrollMoves += 1;
          continue;
        }
        break;
      }
    }

    wlPost({
      ...base,
      final: false,
      group_found: true,
      start_date_found: inventory.some((item) => item.message_date === config.start_label),
      ...wlSummarizeInventory(inventory),
      calendar_attempts: calendarAttempts,
      calendar_dates_found: calendarDatesFound,
      message: `Calendário: ${label} (${calendarDatesFound} datas confirmadas).`,
    });
  }

  return {
    ...wlSummarizeInventory(inventory),
    start_date_observed: wlHasPeriodEvidence(inventory, config),
    first_period_date: wlFirstPeriodDate(inventory, config),
    calendar_attempts: calendarAttempts,
    calendar_dates_found: calendarDatesFound,
    local_scroll_moves: localScrollMoves,
    captured_sources: uploadedSources.size,
  };
}

async function wlCollectSequentialPeriodEvidence(panel, config, base) {
  const inventory = [];
  const seen = new Set();
  const uploadedSources = new Set();
  const dateState = { current_date: config.start_label };
  const targetLabels = wlDateLabelsInRange(config.start_label, config.end_label);
  const effectiveEnd = targetLabels[targetLabels.length - 1] || config.end_label;

  let startFound = await wlNavigateToDate(panel, config);
  await wlSleep(400);
  await wlCloseMessageSearch();
  panel = document.querySelector('[data-testid="conversation-panel-messages"]') || panel;
  // Try subsequent calendar days when the first day has no messages.
  // Example: 01/08 can be Sunday, so the first active day may be 02/08.
  if (!startFound) {
    for (const label of targetLabels.slice(1)) {
      startFound = await wlNavigateToDate(panel, { ...config, start_label: label });
      await wlSleep(300);
      await wlCloseMessageSearch();
      panel = document.querySelector('[data-testid="conversation-panel-messages"]') || panel;
      if (startFound) {
        dateState.current_date = label;
        break;
      }
    }
  }
  if (!startFound) {
    return {
      ...wlSummarizeInventory([]),
      start_date_observed: false,
      calendar_attempts: 1,
      calendar_dates_found: 0,
      local_scroll_moves: 0,
      captured_sources: 0,
    };
  }

  let scrollMoves = 0;
  let unchanged = 0;
  let direction = 1;
  let alternateDirectionTried = false;
  let recentLoads = 0;
  for (let move = 0; move < 240; move += 1) {
    panel = document.querySelector('[data-testid="conversation-panel-messages"]') || panel;
    const batch = wlCollectInventory(panel, config, { seen, date_state: dateState });
    inventory.push(...batch);
    await wlUploadInventoryAttachments(batch, config, uploadedSources);

    if (move % 2 === 0 || batch.length) {
      wlPost({
        ...base,
        final: false,
        group_found: true,
        start_date_found: true,
        ...wlSummarizeInventory(inventory),
        calendar_attempts: 1,
        calendar_dates_found: 1,
        scan_steps: move + 1,
        message: `Percorrendo ${dateState.current_date || config.start_label} até ${effectiveEnd}.`,
      });
    }

    if (wlDateKey(dateState.current_date) > wlDateKey(effectiveEnd)) break;
    const recentLoader = wlLeafContaining(panel, "carregar mensagens recentes");
    if (recentLoader && recentLoads < 60) {
      const recentAction = recentLoader.closest('button, [role="button"]') ||
        recentLoader.parentElement || recentLoader;
      recentLoads += 1;
      recentAction.click();
      await wlSleep(900);
      continue;
    }
    const scrollable = wlMessageScroller(panel);
    if (!scrollable) break;
    const beforeTop = scrollable.scrollTop;
    const distance = Math.max(300, Math.floor(scrollable.clientHeight * 0.72));
    scrollable.scrollTop = beforeTop + (direction * distance);
    scrollable.dispatchEvent(new Event("scroll", { bubbles: true }));
    await wlSleep(300);
    const afterTop = scrollable.scrollTop;
    if (Math.abs(afterTop - beforeTop) < 1) {
      if (!alternateDirectionTried) {
        direction *= -1;
        alternateDirectionTried = true;
        unchanged = 0;
        continue;
      }
      unchanged += 1;
      if (unchanged >= 3) break;
    } else {
      unchanged = 0;
      scrollMoves += 1;
    }
  }

  return {
    ...wlSummarizeInventory(inventory),
    start_date_observed: true,
    calendar_attempts: 1,
    calendar_dates_found: 1,
    local_scroll_moves: scrollMoves,
    recent_waits: recentLoads,
    captured_sources: uploadedSources.size,
  };
}

function wlPost(payload) {
  chrome.runtime.sendMessage({ type: "WL_POST", payload }, () => {
    void chrome.runtime.lastError;
  });
}

function wlGetConfig() {
  return new Promise((resolve) => {
    chrome.runtime.sendMessage({ type: "WL_GET_CONFIG" }, (response) => {
      void chrome.runtime.lastError;
      resolve(response?.ok ? response.data : null);
    });
  });
}

async function wlOpenGroup(groupName, base = null) {
  const searchRegion = () =>
    document.querySelector("#side") ||
    document.querySelector('[data-testid="chat-list"]')?.parentElement ||
    document.querySelector('[aria-label*="lista de conversas" i]') ||
    document;

  const findSearch = () => {
    const side = searchRegion();
    const selectors = [
      '[contenteditable="true"][role="textbox"]',
      '[contenteditable="true"][data-tab="3"]',
      'input[role="searchbox"]',
      'input[type="search"]',
      'input[placeholder*="Pesquisar" i]',
      'input[placeholder*="Search" i]',
      'input',
      '[aria-label*="Pesquisar" i]',
      '[aria-label*="Search" i]',
      '[data-lexical-editor="true"]',
    ];
    return Array.from(side.querySelectorAll(selectors.join(","))).find((element) => {
      const label = wlNormalize(wlAccessibleText(element));
      const rect = element.getBoundingClientRect();
      const outsideConversation = !element.closest("#main");
      const isOnlyChatListInput = element.matches("input") &&
        side.querySelectorAll("input").length === 1 && outsideConversation &&
        rect.width >= 80 && rect.height >= 16;
      return element.matches('input[type="search"], input[role="searchbox"]') ||
        isOnlyChatListInput ||
        label.includes("pesquis") || label.includes("search") ||
        (outsideConversation && rect.top < 260 && rect.left < window.innerWidth * 0.55);
    }) || null;
  };

  const openSearch = () => {
    const side = searchRegion();
    const controls = Array.from(side.querySelectorAll(
      'button, [role="button"], [data-icon], [data-testid]'
    ));
    const trigger = controls.find((element) => {
      const label = wlNormalize(wlAccessibleText(element));
      const icon = wlNormalize(
        `${element.getAttribute("data-icon") || ""} ` +
        `${element.getAttribute("data-testid") || ""}`
      );
      const rect = element.getBoundingClientRect();
      const inChatListHeader = rect.top < 260 && rect.left < window.innerWidth * 0.55;
      return label.includes("pesquisar") || label.includes("search") ||
        ((icon === "search" || icon.includes("chat-list-search")) && inChatListHeader);
    });
    const clickable = trigger?.closest('button, [role="button"]') || trigger;
    if (!clickable) return false;
    clickable.click();
    return true;
  };

  const domSummary = () => {
    const region = searchRegion();
    return [
      `estado=${document.readyState}`,
      `lateral=${Boolean(document.querySelector("#side"))}`,
      `conversa=${Boolean(document.querySelector("#main"))}`,
      `editaveis=${region.querySelectorAll('[contenteditable="true"]').length}`,
      `campos=${region.querySelectorAll("input").length}`,
      `botoes=${region.querySelectorAll('button, [role="button"]').length}`,
    ].join(", ");
  };

  const replaceSearchText = async (search, value) => {
    search.focus();
    let trusted = false;
    if (search instanceof HTMLInputElement || search instanceof HTMLTextAreaElement) {
      search.select();
      trusted = await wlRequestTrustedText(value);
      if (trusted) return true;
      const prototype = search instanceof HTMLTextAreaElement
        ? HTMLTextAreaElement.prototype
        : HTMLInputElement.prototype;
      const setter = Object.getOwnPropertyDescriptor(prototype, "value")?.set;
      if (setter) setter.call(search, value);
      else search.value = value;
    } else {
      document.execCommand("selectAll", false, null);
      trusted = await wlRequestTrustedText(value);
      if (trusted) return true;
      if (!document.execCommand("insertText", false, value)) {
        search.textContent = value;
      }
    }
    search.dispatchEvent(new InputEvent("input", {
      bubbles: true,
      inputType: "insertText",
      data: value,
    }));
    search.dispatchEvent(new Event("change", { bubbles: true }));
    search.dispatchEvent(new KeyboardEvent("keyup", { bubbles: true, key: "a" }));
    return false;
  };

  let search = null;
  for (let wait = 0; wait < 40; wait += 1) {
    if (wlGroupMatches(wlCurrentConversationTitle(), groupName)) return true;
    search = findSearch();
    if (search) break;
    if (wait === 0 || wait % 10 === 0) openSearch();
    if (base && wait > 0 && wait % 10 === 0) {
      wlPost({
        ...base,
        final: false,
        group_found: false,
        start_date_found: false,
        message: `Localizando o grupo no WhatsApp (tentativa ${wait / 10 + 1}; ${domSummary()}).`,
      });
    }
    await wlSleep(500);
  }
  if (!search) return false;

  const trustedSearch = await replaceSearchText(search, groupName);
  if (base) {
    wlPost({
      ...base,
      final: false,
      group_found: false,
      start_date_found: false,
      message: `Busca do grupo preenchida (digitação real=${trustedSearch ? "sim" : "não"}; tamanho=${String(search.value || search.textContent || "").length}).`,
    });
  }
  let title = null;
  for (let wait = 0; wait < 30 && !title; wait += 1) {
    const side = searchRegion();
    const titles = Array.from(side.querySelectorAll(
      '[data-testid="cell-frame-title"], [title], [aria-label], [role="listitem"] span, [role="row"] span, span, div'
    ));
    title = titles.find(
      (element) =>
        element.offsetParent !== null &&
        element !== search &&
        wlGroupMatches(
          `${element.getAttribute?.("title") || ""} ` +
          `${element.getAttribute?.("aria-label") || ""} ` +
          `${element.textContent || ""}`,
          groupName
        )
    );
    if (!title) await wlSleep(500);
  }
  if (!title) {
    const side = searchRegion();
    const searchRect = search.getBoundingClientRect();
    const resultRows = Array.from(side.querySelectorAll(
      '[role="row"], [role="listitem"], [data-testid*="cell" i], [tabindex="-1"]'
    )).filter((element) => {
      const rect = element.getBoundingClientRect();
      return element !== search && rect.width >= 160 && rect.height >= 28 &&
        rect.top >= searchRect.bottom + 2 && rect.top < window.innerHeight;
    }).sort((left, right) =>
      left.getBoundingClientRect().top - right.getBoundingClientRect().top
    );
    if (resultRows.length) {
      await wlRequestTrustedClick(resultRows[0]);
      for (let wait = 0; wait < 20; wait += 1) {
        if (wlGroupMatches(wlCurrentConversationTitle(), groupName)) return true;
        await wlSleep(300);
      }
    } else if (searchRect.width > 0) {
      await wlRequestTrustedPoint(
        searchRect.left + (searchRect.width / 2),
        Math.min(window.innerHeight - 30, searchRect.bottom + 65)
      );
      for (let wait = 0; wait < 20; wait += 1) {
        if (wlGroupMatches(wlCurrentConversationTitle(), groupName)) return true;
        await wlSleep(300);
      }
    }
    // Some current builds keep the result text outside the accessible DOM.
    // With the full group name already typed, keyboard selection opens the
    // first filtered result; the header is still verified before accepting it.
    search.focus();
    const trustedDown = await wlRequestTrustedKey("ArrowDown");
    const trustedEnter = await wlRequestTrustedKey("Enter");
    if (!trustedDown) search.dispatchEvent(new KeyboardEvent("keydown", {
      bubbles: true, key: "ArrowDown", code: "ArrowDown",
    }));
    if (!trustedEnter) search.dispatchEvent(new KeyboardEvent("keydown", {
      bubbles: true, key: "Enter", code: "Enter",
    }));
    for (let wait = 0; wait < 30; wait += 1) {
      if (wlGroupMatches(wlCurrentConversationTitle(), groupName)) return true;
      await wlSleep(500);
    }
    return false;
  }
  const row = title.closest(
    '[data-testid="cell-frame-container"], [role="listitem"], [role="row"], [tabindex="-1"]'
  ) || title;
  row.click();
  for (let wait = 0; wait < 40; wait += 1) {
    if (wlGroupMatches(wlCurrentConversationTitle(), groupName)) return true;
    if (
      document.querySelector('[data-testid="conversation-panel-messages"]') &&
      wlGroupMatches(title.getAttribute?.("title") || title.textContent, groupName)
    ) return true;
    await wlSleep(500);
  }
  return false;
}

async function wlRunTargetAlbumTest(panel, config, base) {
  const targetDate = String(config.target_test_date || "");
  const targetSize = Number(config.target_album_size || 0);
  const targetMessageId = String(config.target_album_message_id || "");
  wlPost({
    ...base,
    final: false,
    group_found: true,
    start_date_found: false,
    message: `Teste direcionado iniciado para ${targetDate}.`,
  });
  const dateFound = await wlNavigateToDate(panel, {
    ...config,
    start_label: targetDate,
  });
  await wlSleep(500);
  await wlCloseMessageSearch();
  panel = document.querySelector('[data-testid="conversation-panel-messages"]') || panel;

  const seen = new Set();
  const dateState = { current_date: dateFound ? targetDate : "" };
  const inventory = [];
  let target = null;
  let direction = 1;
  let reversed = false;

  for (let move = 0; move < 24 && !target; move += 1) {
    const batch = wlCollectInventory(panel, config, { seen, date_state: dateState });
    inventory.push(...batch);
    const matchesTarget = (item) => targetMessageId
      ? item.message_id === targetMessageId
      : item.image_count === targetSize;
    target = batch.find(matchesTarget) || inventory.find(matchesTarget) || null;
    if (target) break;
    const scrollable = wlMessageScroller(panel);
    if (!scrollable) break;
    const before = scrollable.scrollTop;
    const distance = Math.max(220, Math.floor(scrollable.clientHeight * 0.55));
    scrollable.scrollTop = before + (direction * distance);
    scrollable.dispatchEvent(new Event("scroll", { bubbles: true }));
    await wlSleep(250);
    if (Math.abs(scrollable.scrollTop - before) < 1) {
      if (reversed) break;
      direction = -1;
      reversed = true;
    }
    panel = document.querySelector('[data-testid="conversation-panel-messages"]') || panel;
  }

  if (!target) {
    wlPost({
      ...base,
      final: true,
      group_found: true,
      start_date_found: false,
      visible_images: 0,
      visible_pdfs: 0,
      ok_reactions: 0,
      stake_messages: [],
      evidences: [],
      incomplete_albums: [],
      message: `Teste direcionado: álbum ${targetMessageId || `de ${targetSize} fotos`} não localizado em ${targetDate}.`,
    });
    return;
  }

  const uploadedSources = new Set();
  const captured = await wlCaptureAlbumAttachments(
    target, config, uploadedSources, panel
  );
  target.album_captured_count = captured;
  wlPost({
    ...base,
    final: true,
    group_found: true,
    start_date_found: false,
    ...wlSummarizeInventory([target]),
    target_album_expected: targetSize,
    target_album_captured: captured,
    attachment_errors: wlAttachmentErrors.slice(-20),
    message: `Teste direcionado do álbum: ${captured} de ${targetSize} fotos capturadas.`,
  });
}

async function wlAnalyze(config) {
  const base = {
    session_id: config.session_id,
    token: config.token,
    connected: true,
    group_name: config.group_name,
    start_date: config.start_label,
    load_attempts: 0,
    sync_waits: 0,
    sync_in_progress: false,
  };

  wlNavigationStage = "abrindo grupo";
  const groupFound = await wlOpenGroup(config.group_name, base);
  if (!groupFound) {
    wlPost({
      ...base,
      final: true,
      group_found: false,
      start_date_found: false,
      message: `O grupo nao foi localizado. Conversa visivel: ${wlCurrentConversationTitle() || "nenhuma"}.`,
    });
    wlRunningSession = "";
    return;
  }

  wlNavigationStage = "preparando cliques do Chrome";
  const sessionState = await wlStartTrustedSession(config.session_id);
  if (!sessionState.claimed) return;
  wlPost({
    ...base,
    final: false,
    group_found: true,
    start_date_found: false,
    message: sessionState.trusted
      ? "Leitura iniciada no grupo correto."
      : "Leitura iniciada em modo compatível, sem clique avançado do Chrome.",
  });
  await wlSleep(600);

  wlNavigationStage = "aguardando painel de mensagens";
  let panel = null;
  for (let wait = 0; wait < 30 && !panel; wait += 1) {
    panel = document.querySelector('[data-testid="conversation-panel-messages"]');
    if (!panel) await wlSleep(500);
  }
  if (!panel) {
    wlPost({
      ...base,
      final: true,
      group_found: true,
      start_date_found: false,
      message: "O painel de mensagens não ficou disponível.",
    });
    return;
  }

  if (config.target_test_date && config.target_album_size) {
    await wlRunTargetAlbumTest(panel, config, base);
    return;
  }

  let loadAttempts = 0;
  let syncWaits = 0;
  let syncInProgress = false;
  let startDateFound = await wlNavigateToDate(panel, config);
  panel = document.querySelector('[data-testid="conversation-panel-messages"]') || panel;

  for (let attempt = 0; attempt < 8 && !startDateFound; attempt += 1) {
    startDateFound = wlHasDate(panel, config.start_label);
    if (startDateFound) break;

    syncInProgress = Boolean(wlExactElement(panel, WL_SYNCING));
    if (syncInProgress) {
      syncWaits += 1;
      if (attempt % 10 === 0) {
        wlPost({
          ...base,
          final: false,
          group_found: true,
          start_date_found: false,
          sync_in_progress: true,
          sync_waits: syncWaits,
          ...wlCollectEvidence(panel, config),
          message: "O Chrome ainda está sincronizando mensagens antigas.",
        });
      }
      await wlSleep(1000);
      continue;
    }

    const olderText = wlExactElement(panel, WL_LOAD_OLDER);
    const olderButton = olderText?.closest("button") || olderText;
    if (olderButton) {
      olderButton.click();
      loadAttempts += 1;
      await wlSleep(750);
      continue;
    }

    const scrollable = wlMessageScroller(panel);
    if (scrollable) {
      const before = scrollable.scrollTop;
      scrollable.scrollTop = 0;
      if (scrollable.scrollTop === before) {
        scrollable.scrollTop = -scrollable.scrollHeight;
      }
      scrollable.dispatchEvent(new Event("scroll", { bubbles: true }));
    }
    if (attempt % 10 === 0) {
      wlPost({
        ...base,
        final: false,
        group_found: true,
        start_date_found: false,
        load_attempts: loadAttempts,
        sync_waits: syncWaits,
        sync_in_progress: false,
        ...wlCollectEvidence(panel, config),
        message: `Subindo o histórico. Calendário: ${wlNavigationStage}.`,
      });
    }
    await wlSleep(250);
  }

  // Primeiro percorremos o histórico para carregar as mensagens antigas.
  // O calendário do WhatsApp pode limitar-se ao mês atualmente carregado;
  // tentar navegar por ele antes do carregamento deixava a leitura parada.
  const evidence = await wlCollectPeriodEvidence(panel, config, base);
  // A quinzena can begin with a day without messages. Use the first active
  // date found inside the interval instead of requiring the exact start day.
  const periodScanComplete = Boolean(evidence.period_scan_complete);
  startDateFound = periodScanComplete &&
    (startDateFound || Boolean(evidence.start_date_observed));
  const effectiveStart = evidence.first_period_date || config.start_label;
  wlPost({
    ...base,
    final: true,
    group_found: true,
    start_date_found: startDateFound,
    load_attempts: loadAttempts,
    sync_waits: syncWaits,
    sync_in_progress: syncInProgress && !startDateFound,
    ...evidence,
    period_scan_complete: periodScanComplete,
    attachment_errors: wlAttachmentErrors.slice(-20),
    message: !periodScanComplete
      ? "Leitura incompleta: nem todos os dias da quinzena foram percorridos. A revisão foi bloqueada."
      : startDateFound
      ? (effectiveStart === config.start_label
        ? `Histórico comprovado desde ${config.start_label}.`
        : `Sem movimento em ${config.start_label}; primeira evidência reconhecida em ${effectiveStart}.`)
      : `A data inicial ainda não apareceu. Calendário: ${wlNavigationStage}.`,
  });
}

async function wlCheckForSession() {
  try {
    const config = await wlGetConfig();
    if (!config) return;
    if (!config.session_id || config.session_id === wlRunningSession) return;
    wlRunningSession = config.session_id;
    wlPost({
      session_id: config.session_id,
      token: config.token,
      final: false,
      connected: true,
      group_name: config.group_name,
      start_date: config.start_label,
      group_found: false,
      start_date_found: false,
      message: "Leitor ativo; iniciando a abertura do grupo.",
    });
    try {
      // A quinzena pode conter álbuns grandes; 15 minutos interrompia a
      // leitura no meio da galeria. O limite operacional passa a 45 minutos.
      const maximumMilliseconds = config.target_test_date ? 150000 : 2700000;
      const outcome = await Promise.race([
        wlAnalyze(config).then(() => "completed"),
        wlSleep(maximumMilliseconds).then(() => "timeout"),
      ]);
      if (outcome === "timeout") {
        wlPost({
          session_id: config.session_id,
          token: config.token,
          final: true,
          connected: true,
          group_name: config.group_name,
          start_date: config.start_label,
          group_found: true,
          start_date_found: false,
          message: `A leitura atingiu o limite de segurança. Etapa: ${wlNavigationStage}.`,
        });
      }
    } catch (error) {
      wlPost({
        session_id: config.session_id,
        token: config.token,
        final: true,
        connected: true,
        group_name: config.group_name,
        start_date: config.start_label,
        group_found: true,
        start_date_found: false,
        message: `Erro interno da extensão: ${error?.message || String(error)}`,
      });
    }
  } catch (_error) {
    // O aplicativo local ainda não está aguardando uma leitura.
  }
}

setInterval(wlCheckForSession, 2000);
chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message?.type !== "WL_WAKE") return false;
  wlCheckForSession();
  sendResponse({ ok: true });
  return false;
});
wlCheckForSession();

})();
