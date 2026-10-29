import { Before, After, setDefaultTimeout } from '@cucumber/cucumber';
import { CustomWorld } from './world.js';

// Timeout generoso para transições assíncronas do pipeline e montagens visuais
setDefaultTimeout(40000);

Before(async function (this: CustomWorld, scenario) {
  this.currentScenarioName = scenario.pickle.name;
  this.writerCalled = false;
  this.dispatchedPostUrls = [];
  this.liveViolationCount = 0;
  this.liveViolations = [];
  this.liveRequests = [];
  this.trackedRequests = [];
  this.lastSourcesResponse = null;
  this.expectedDossierText = null;
  this.lastDownloadedContent = null;
  this.lastDownloadedFilename = null;
  this.lastWriterDossierBody = null;
});

After(async function (this: CustomWorld) {
  if ((this as any).pendingRouteResolvers && Array.isArray((this as any).pendingRouteResolvers)) {
    for (const resolveRoute of (this as any).pendingRouteResolvers) {
      try {
        await resolveRoute();
      } catch {
        // ignore
      }
    }
    (this as any).pendingRouteResolvers = [];
  }
  if (this.page || this.livePage) {
    await this.recordScenarioProvenance(this.currentScenarioName);
  }
  await this.close();
});
