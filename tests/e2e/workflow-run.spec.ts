import { test, expect } from '@playwright/test';

test('workflow run button dispatches task', async ({ page }) => {
  // Navigate to workflows page
  await page.goto('http://localhost:3000/workflows');
  
  // Wait for workflows to load
  await page.waitForSelector('.bg-white.rounded-lg', { timeout: 10000 });
  
  // Get the first workflow
  const workflowCard = page.locator('.bg-white.rounded-lg').first();
  await expect(workflowCard).toBeVisible();
  
  // Find and click the run button (Play icon)
  const runButton = workflowCard.locator('button[title="立即运行"]');
  await expect(runButton).toBeVisible();
  
  // Set up response listener before clicking
  const responsePromise = page.waitForResponse(
    response => response.url().includes('/api/workflows/') && response.url().includes('/run') && response.request().method() === 'POST'
  );
  
  // Click the run button
  await runButton.click();
  
  // Wait for the API response
  const response = await responsePromise;
  
  // Check response status
  expect(response.status()).toBe(200);
  
  // Check response body
  const body = await response.json();
  expect(body).toHaveProperty('message');
  expect(body).toHaveProperty('run_id');
  
  console.log('Run button test passed!');
});
