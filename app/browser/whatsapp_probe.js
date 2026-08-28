"use strict";

const fs = require("fs");
const { chromium } = require("playwright");

function argument(name) {
  const index = process.argv.indexOf(name);
  return index >= 0 ? process.argv[index + 1] : "";
}

function displayDate(isoDate) {
  const [year, month, day] = isoDate.split("-");
  return `${day}/${month}/${year}`;
}

function emit(data) {
  process.stdout.write(`${JSON.stringify(data)}\n`);
}

function browserExecutable() {
  const candidates = [
    "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
    "C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe",
    "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
    "C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe",
  ];
  return candidates.find((candidate) => fs.existsSync(candidate));
}

async function main() {
  const groupName = argument("--group");
  const startDate = argument("--start");
  const endDate = argument("--end");
  const profile = argument("--profile");
  const startLabel = displayDate(startDate);
  const executablePath = browserExecutable();

  if (!groupName || !startDate || !endDate || !profile || !executablePath) {
    throw new Error("Configuração incompleta para abrir o WhatsApp.");
  }

  const context = await chromium.launchPersistentContext(profile, {
    executablePath,
    headless: false,
    viewport: null,
    args: ["--start-maximized"],
  });

  try {
    const pages = context.pages();
    const page = pages.length ? pages[0] : await context.newPage();
    await page.goto("https://web.whatsapp.com/", {
      waitUntil: "domcontentloaded",
      timeout: 90000,
    });

    const search = page.getByRole("textbox", {
      name: "Pesquisar ou começar uma nova conversa",
    });
    await search.waitFor({ state: "visible", timeout: 180000 });
    emit({ kind: "progress", stage: "connected" });

    await search.fill(groupName);
    const groupTitles = page
      .locator('[data-testid="cell-frame-title"]')
      .filter({ hasText: groupName });
    await groupTitles.first().waitFor({ state: "visible", timeout: 30000 });
    const groupCount = await groupTitles.count();
    if (!groupCount) {
      emit({
        kind: "result",
        connected: true,
        group_found: false,
        start_date_found: false,
        start_date: startLabel,
        group_name: groupName,
        message: "Grupo não encontrado.",
      });
      return;
    }
    await groupTitles.first().click();

    const panel = page.locator('[data-testid="conversation-panel-messages"]');
    await panel.waitFor({ state: "visible", timeout: 30000 });

    // A primeira sincronização de uma sessão nova pode abrir o grupo antes de
    // as mensagens e o aviso de histórico aparecerem. Aguarde esse conteúdo
    // em vez de concluir imediatamente que o histórico está vazio.
    await page.waitForTimeout(5000);

    let startDateFound = false;
    let loadAttempts = 0;
    let syncWaits = 0;
    let syncInProgress = false;
    const maxLoads = 24;
    // A primeira sincronização de grupos com muitos álbuns pode demorar. Não
    // encerre a janela no meio do processo, pois o WhatsApp retomaria a carga
    // na execução seguinte. O limite de 20 minutos vale apenas para essa carga.
    const maxSyncWaits = 400;
    const loadOlderText =
      "Clique neste aviso para carregar mensagens mais antigas do seu celular.";
    const syncingText =
      "Sincronizando mensagens mais antigas. Clique para ver o progresso.";

    for (let attempt = 0; attempt <= maxLoads + maxSyncWaits; attempt += 1) {
      startDateFound =
        (await panel.getByText(startLabel, { exact: true }).count()) > 0;
      if (startDateFound) break;

      const syncing = panel.getByText(syncingText, { exact: true });
      syncInProgress = (await syncing.count()) > 0;
      if (syncInProgress) {
        if (syncWaits >= maxSyncWaits) break;
        syncWaits += 1;
        await page.waitForTimeout(3000);
        continue;
      }

      const loadOlderButton = page.getByRole("button", {
        name: loadOlderText,
      });
      const loadOlderTextNode = page.getByText(loadOlderText, { exact: true });
      const buttonCount = await loadOlderButton.count();
      const textCount = await loadOlderTextNode.count();

      if (buttonCount === 1) {
        await loadOlderButton.click();
        loadAttempts += 1;
        syncWaits = 0;
        await page.waitForTimeout(2200);
        continue;
      }
      if (textCount === 1) {
        await loadOlderTextNode.click();
        loadAttempts += 1;
        syncWaits = 0;
        await page.waitForTimeout(2200);
        continue;
      }

      if (syncWaits >= maxSyncWaits) break;
      await panel.evaluate((element) => {
        const parents = [];
        let current = element;
        for (let level = 0; level < 4 && current; level += 1) {
          parents.push(current);
          current = current.parentElement;
        }
        const candidates = [...parents, ...element.querySelectorAll("div")];
        const scrollable = candidates
          .filter((item) => item.scrollHeight > item.clientHeight + 20)
          .sort((a, b) => b.scrollHeight - a.scrollHeight)[0];
        if (scrollable) scrollable.scrollTop = 0;
      });
      syncWaits += 1;
      await page.waitForTimeout(2500);
    }

    const evidence = await panel.evaluate((element) => {
      const text = element.textContent || "";
      const stakePattern = /\b\d+\s*[x×]\s*\d+\s*=\s*\d+\b/gi;
      return {
        visible_images: element.querySelectorAll(
          'button[aria-label="Abrir imagem"]'
        ).length,
        visible_pdfs: Array.from(element.querySelectorAll("button")).filter(
          (button) => /\.pdf\b/i.test(button.textContent || "")
        ).length,
        ok_reactions: Array.from(
          element.querySelectorAll("button[aria-label]")
        ).filter((button) =>
          (button.getAttribute("aria-label") || "").includes("🆗")
        ).length,
        stake_messages: Array.from(
          new Set(text.match(stakePattern) || [])
        ).slice(0, 20),
      };
    });

    emit({
      kind: "result",
      connected: true,
      group_found: true,
      start_date_found: startDateFound,
      start_date: startLabel,
      end_date: displayDate(endDate),
      group_name: groupName,
      load_attempts: loadAttempts,
      sync_waits: syncWaits,
      sync_in_progress: syncInProgress,
      visible_images: evidence.visible_images,
      visible_pdfs: evidence.visible_pdfs,
      ok_reactions: evidence.ok_reactions,
      stake_messages: evidence.stake_messages,
      message: startDateFound
        ? `Histórico comprovado até ${startLabel}.`
        : syncInProgress
          ? "O WhatsApp ainda está sincronizando as mensagens mais antigas."
            + " Mantenha o WhatsApp aberto no celular durante esta primeira sincronização."
          : `A data ${startLabel} ainda não apareceu no histórico carregado.`,
    });
  } finally {
    await context.close();
  }
}

main().catch((error) => {
  process.stderr.write(`${error && error.message ? error.message : error}\n`);
  process.exitCode = 1;
});
