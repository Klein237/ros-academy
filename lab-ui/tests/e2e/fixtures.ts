import { test as base } from "@playwright/test";

export { expect, request, type APIRequestContext, type Page } from "@playwright/test";

/**
 * Chromium abandonne une navigation (net::ERR_NETWORK_CHANGED) quand une interface réseau de la
 * machine change : c'est le cas à chaque réseau Docker de lab créé ou supprimé par le Hub, sur la
 * machine qui exécute aussi le navigateur des tests. Un étudiant n'est pas concerné (son navigateur
 * est ailleurs). page.goto recommence alors, deux fois au plus ; toute autre erreur passe telle quelle.
 */
export const test = base.extend({
  page: async ({ page }, use) => {
    const goto = page.goto.bind(page);
    page.goto = async (url, options) => {
      for (let essai = 1; ; essai++) {
        try {
          return await goto(url, options);
        } catch (e) {
          if (essai >= 3 || !String(e).includes("ERR_NETWORK_CHANGED")) throw e;
          await page.waitForTimeout(1000);
        }
      }
    };
    await use(page);
  },
});
