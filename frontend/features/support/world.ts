import { setWorldConstructor, World, IWorldOptions } from '@cucumber/cucumber';
import { Browser, BrowserContext, Page, chromium } from 'playwright';
import path from 'path';
import fs from 'fs';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

export interface ScenarioProvenanceRecord {
  scenarioName: string;
  baseUrl: string;
  timestamp: string;
  mode: string;
  loadedScripts: string[];
  loadedStyles: string[];
  screenshots: string[];
  liveViolations: number;
}

export class CustomWorld extends World {
  browser: Browser | null = null;
  context: BrowserContext | null = null;
  page: Page | null = null;

  // Contexto dedicado e estritamente isolado para o ensaio de replay live somente-leitura
  liveContext: BrowserContext | null = null;
  livePage: Page | null = null;

  baseUrl: string = process.env.BASE_URL || 'http://localhost:8011';
  // Diretório canônico oficial de evidências de aceitação Cucumber (docs/frontend/remediation/evidence/cucumber)
  evidenceDir: string = path.resolve(__dirname, '../../../docs/frontend/remediation/evidence/cucumber');

  currentScenarioName: string = 'unnamed-scenario';
  writerCalled: boolean = false;
  dispatchedPostUrls: string[] = [];
  liveViolationCount: number = 0;
  liveViolations: Array<{ method: string; url: string }> = [];
  liveRequests: Array<{ method: string; url: string }> = [];
  trackedRequests: Array<{ method: string; url: string }> = [];
  lastSourcesResponse: any = null;
  expectedDossierText: string | null = null;
  lastDownloadedContent: string | null = null;
  lastDownloadedFilename: string | null = null;
  capturedScreenshots: string[] = [];
  lastWriterDossierBody: string | null = null;

  constructor(options: IWorldOptions) {
    super(options);
    if (!fs.existsSync(this.evidenceDir)) {
      fs.mkdirSync(this.evidenceDir, { recursive: true });
    }
  }

  async init(viewport = { width: 1440, height: 900 }) {
    if (!this.browser) {
      this.browser = await chromium.launch({
        headless: true,
        args: [
          '--no-sandbox',
          '--disable-setuid-sandbox',
          '--disable-dev-shm-usage',
          '--disable-gpu',
        ],
      });
    }

    this.context = await this.browser.newContext({
      viewport,
      colorScheme: 'light',
      acceptDownloads: true,
      permissions: ['clipboard-read', 'clipboard-write'],
    });

    this.page = await this.context.newPage();

    // Rastreamento estrito de requisições de mutação e registro geral para validação de contratos
    this.page.on('request', (req) => {
      const method = req.method().toUpperCase();
      const url = req.url();
      this.trackedRequests.push({ method, url });
      if (['POST', 'PUT', 'PATCH', 'DELETE'].includes(method)) {
        this.dispatchedPostUrls.push(url);
      }
    });

    // Intercepta respostas de /api/v1/writer e /sources para capturar dados exatos retornados pelo backend
    this.page.on('response', async (res) => {
      const url = res.url();
      if (url.includes('/api/v1/writer') && res.status() === 200) {
        try {
          const data = await res.json();
          if (data && typeof data.dossier_final === 'string') {
            this.lastWriterDossierBody = data.dossier_final;
          }
          if (data && data.fontes) {
            this.lastSourcesResponse = data.fontes;
          }
        } catch {
          // ignore non-json
        }
      } else if (url.includes('/sources') && res.status() === 200) {
        try {
          this.lastSourcesResponse = await res.json();
        } catch {
          // ignore non-json
        }
      }
    });
  }

  /**
   * Inicializa contexto secundário estritamente isolado para o ensaio de replay live somente-leitura.
   * Não compartilha cookies, storage, abas ou memória com o contexto padrão.
   * Intercepta com context.route() ANTES do goto para abortar qualquer POST preventivamente.
   */
  async initIsolatedLiveContext(viewport = { width: 1440, height: 900 }) {
    if (!this.browser) {
      this.browser = await chromium.launch({
        headless: true,
        args: [
          '--no-sandbox',
          '--disable-setuid-sandbox',
          '--disable-dev-shm-usage',
          '--disable-gpu',
        ],
      });
    }

    this.liveContext = await this.browser.newContext({
      viewport,
      colorScheme: 'light',
      acceptDownloads: true,
      permissions: ['clipboard-read', 'clipboard-write'],
    });

    this.liveViolationCount = 0;
    this.liveViolations = [];
    this.liveRequests = [];

    // Barreira rígida preventiva via context.route: intercepta no nível de protocolo de rede
    // antes de qualquer pacote chegar ao servidor live.
    // Bloqueia todos métodos mutantes POST/PUT/PATCH/DELETE em rotas de API.
    await this.liveContext.route('**/*', (route, request) => {
      const method = request.method().toUpperCase();
      const url = request.url();

      if (['POST', 'PUT', 'PATCH', 'DELETE'].includes(method)) {
        this.liveViolationCount++;
        this.liveViolations.push({ method, url });
        // Aborta ativamente antes do handshake de envio ao servidor
        route.abort('blockedbyclient');
        return;
      }

      route.continue();
    });

    this.livePage = await this.liveContext.newPage();

    this.livePage.on('request', (req) => {
      const method = req.method().toUpperCase();
      const url = req.url();
      this.liveRequests.push({ method, url });
      if (['POST', 'PUT', 'PATCH', 'DELETE'].includes(method)) {
        this.dispatchedPostUrls.push(url);
      }
    });

    this.livePage.on('response', async (res) => {
      const url = res.url();
      if (url.includes('/sources') && res.status() === 200) {
        try {
          this.lastSourcesResponse = await res.json();
        } catch {
          // ignore non-json
        }
      }
    });

    return this.livePage;
  }

  async saveScreenshot(filename: string, useLivePage = false, locatorSelector?: string): Promise<string | null> {
    const targetPage = useLivePage ? this.livePage : this.page;
    if (targetPage) {
      const fullPath = path.join(this.evidenceDir, filename);
      if (locatorSelector) {
        const locator = targetPage.locator(locatorSelector).first();
        if (await locator.count() > 0) {
          await locator.screenshot({ path: fullPath });
        } else {
          await targetPage.screenshot({ path: fullPath });
        }
      } else {
        await targetPage.screenshot({ path: fullPath, fullPage: true });
      }
      if (!this.capturedScreenshots.includes(filename)) {
        this.capturedScreenshots.push(filename);
      }
      return fullPath;
    }
    return null;
  }

  /**
   * Lê a área de transferência do contexto headless ativo sem tocar no clipboard do SO.
   */
  async getContextClipboard(useLivePage = false): Promise<string> {
    const targetPage = useLivePage ? this.livePage : (this.page || this.livePage);
    if (!targetPage) return '';
    return await targetPage.evaluate(async () => {
      try {
        return await navigator.clipboard.readText();
      } catch {
        return '';
      }
    });
  }

  /**
   * Registra manifesto de proveniência único por cenário e atualiza o índice consolidado,
   * incluindo scripts, estilos, capturas, hashes e violações sem expor dados privados ou cookies.
   */
  async recordScenarioProvenance(scenarioName: string) {
    const activePage = this.page || this.livePage;
    if (!activePage) return;

    try {
      const scripts = await activePage.evaluate(() => {
        return Array.from(document.querySelectorAll('script[src]')).map((s) => (s as HTMLScriptElement).src);
      }).catch(() => []);

      const styles = await activePage.evaluate(() => {
        return Array.from(document.querySelectorAll('link[rel="stylesheet"]')).map((l) => (l as HTMLLinkElement).href);
      }).catch(() => []);

      const safeScenarioId = scenarioName
        .toLowerCase()
        .replace(/[^a-z0-9]/g, '-')
        .replace(/-+/g, '-')
        .slice(0, 60);

      const record: ScenarioProvenanceRecord = {
        scenarioName,
        baseUrl: this.baseUrl,
        timestamp: new Date().toISOString(),
        mode: process.env.NODE_ENV || 'test',
        loadedScripts: scripts,
        loadedStyles: styles,
        screenshots: [...this.capturedScreenshots],
        liveViolations: this.liveViolationCount,
      };

      // Grava arquivo único por cenário
      const scenarioRecordPath = path.join(this.evidenceDir, `provenance-${safeScenarioId}.json`);
      fs.writeFileSync(scenarioRecordPath, JSON.stringify(record, null, 2), 'utf-8');

      // Atualiza o sumário consolidado
      const summaryIndexPath = path.join(this.evidenceDir, 'summary-index.json');
      let summaryList: ScenarioProvenanceRecord[] = [];
      if (fs.existsSync(summaryIndexPath)) {
        try {
          summaryList = JSON.parse(fs.readFileSync(summaryIndexPath, 'utf-8'));
          if (!Array.isArray(summaryList)) summaryList = [];
        } catch {
          summaryList = [];
        }
      }
      summaryList.push(record);
      fs.writeFileSync(summaryIndexPath, JSON.stringify(summaryList, null, 2), 'utf-8');
    } catch {
      // Falha não-bloqueante no registro de manifesto
    }
  }

  async close() {
    if (this.page) {
      await this.page.close().catch(() => {});
      this.page = null;
    }
    if (this.context) {
      await this.context.close().catch(() => {});
      this.context = null;
    }
    if (this.livePage) {
      await this.livePage.close().catch(() => {});
      this.livePage = null;
    }
    if (this.liveContext) {
      await this.liveContext.close().catch(() => {});
      this.liveContext = null;
    }
    if (this.browser) {
      await this.browser.close().catch(() => {});
      this.browser = null;
    }
  }
}

setWorldConstructor(CustomWorld);
