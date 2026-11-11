// The screen walked end to end against the stand-in model: `python -m dramatis --stub --no-browser`, then
// `node tests/walk/walk.mjs`. Each step waits for what a person would see and fails the walk when it does not come,
// or when the page logs an error. WALK_URL is the server (default http://127.0.0.1:8815); WALK_SHOTS, when set, is a
// folder for a screenshot of each step. WALK_README, when set, is where the README's picture of the form goes.
import { mkdirSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { chromium } from 'playwright'

const URL = process.env.WALK_URL || 'http://127.0.0.1:8815'
const SHOTS = process.env.WALK_SHOTS || ''
const errors = []
// Responses a step fails on purpose, which the browser logs as errors too.
const refusals = { left: 0 }

if (SHOTS) mkdirSync(SHOTS, { recursive: true })

async function shot(page, name) {
  if (SHOTS) await page.screenshot({ path: join(SHOTS, `${name}.png`), fullPage: true })
}

function watch(page) {
  page.on('console', (message) => {
    if (message.type() !== 'error') return
    if (refusals.left > 0 && message.text().startsWith('Failed to load resource')) { refusals.left -= 1; return }
    errors.push(`${page.url()}: ${message.text()}`)
  })
  page.on('pageerror', (error) => errors.push(`${page.url()}: ${error.message}`))
}

async function step(name, work) {
  try {
    await work()
    console.log(`ok   ${name}`)
  } catch (error) {
    console.error(`FAIL ${name}\n${error.message}`)
    throw error
  }
}

/** The quick start writes a whole character, Help me write proposes, Keep keeps, Save saves, a reload keeps it. */
async function character(page) {
  await step('the start screen opens', async () => {
    await page.goto(URL)
    await page.getByRole('heading', { name: 'A new character' }).waitFor()
    await shot(page, '01-start')
  })
  await step('Write them drafts the whole character into the form', async () => {
    await page.getByText('More options').click()
    await page.getByLabel('Who are they?').fill('a night nurse who holds grudges')
    await page.getByRole('button', { name: 'Write them' }).click()
    await page.getByRole('button', { name: 'Stop' }).waitFor()
    await page.locator('form.editor').waitFor()
    await page.getByRole('heading', { name: 'Dana Okafor' }).waitFor()
    await shot(page, '02-form')
  })
  await step('Help me write proposes, and Keep keeps it', async () => {
    await page.getByRole('button', { name: 'Help me write how they talk' }).click()
    // New words in How they talk settle the sliders again a moment later.
    const settled = page.waitForResponse((response) => response.url().endsWith('/api/sliders'))
    await page.getByLabel('What should change about how they talk').press('Enter')
    await page.getByRole('button', { name: 'Keep' }).first().waitFor()
    await shot(page, '03-proposal')
    await page.getByRole('button', { name: 'Keep' }).first().click()
    await settled
  })
  await step('Save writes them to the library', async () => {
    await page.getByRole('button', { name: 'Save to the library' }).click()
    await page.getByText('Saved Dana Okafor').waitFor()
  })
  await step('a reload keeps them in the library', async () => {
    await page.reload()
    await page.locator('aside').getByText('Dana Okafor').first().waitFor()
  })
  await step('a saved character opens with no unsaved changes', async () => {
    const settled = page.waitForResponse((response) => response.url().endsWith('/api/sliders'))
    await page.locator('aside').getByText('Dana Okafor').first().click()
    await settled
    await page.waitForTimeout(300)
    if (await page.getByRole('button', { name: 'Discard changes' }).count()) throw new Error('Opening them marked the form changed.')
  })
  await step('a reload stays on their form', async () => {
    if (!page.url().includes('#/character/')) throw new Error(`The address is ${page.url()}.`)
    await page.reload()
    await page.getByRole('heading', { name: 'Dana Okafor' }).waitFor()
  })
  await step('Back closes Models and leaves the form as it was', async () => {
    await page.getByRole('button', { name: /^Models/ }).click()
    await page.getByRole('heading', { name: 'Models' }).waitFor()
    if (!page.url().endsWith('#/models')) throw new Error(`The address is ${page.url()}.`)
    await page.goBack()
    await page.getByRole('heading', { name: 'Models' }).waitFor({ state: 'hidden' })
    await page.getByRole('heading', { name: 'Dana Okafor' }).waitFor()
  })
}

/** The README's picture: the character just saved, at twice the pixels. */
async function readme(browser) {
  const context = await browser.newContext({ viewport: { width: 1360, height: 860 }, deviceScaleFactor: 2 })
  const page = await context.newPage()
  await page.goto(URL)
  await page.locator('aside').getByText('Dana Okafor').first().click()
  await page.locator('form.editor').waitFor()
  await page.screenshot({ path: process.env.WALK_README })
  await context.close()
}

/** Bring a character: pasted text sorted into fields by the model. */
async function paste(page) {
  await step('Sort into fields splits pasted text', async () => {
    await page.getByRole('button', { name: 'New character' }).click()
    await page.getByLabel('Their character').fill('Dana, a night nurse in Baltimore. Dry, tired, early to everything.')
    await page.getByRole('button', { name: 'Sort into fields with my model' }).click()
    await page.locator('form.editor').waitFor()
    await page.getByRole('heading', { name: 'Dana Okafor' }).waitFor()
    await shot(page, '04-split')
  })
}

// A 1×1 PNG, for a portrait.
const PNG = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==', 'base64')

/** A new character's portrait that fails to save leaves them saved once; Save again sends the portrait, not a copy. */
async function portrait(page) {
  await step('a failed portrait never saves a second copy', async () => {
    const posts = []
    page.on('request', (request) => {
      if (request.method() === 'POST' && new globalThis.URL(request.url()).pathname === '/api/characters') posts.push(request.url())
    })
    let refused = false
    await page.route('**/api/characters/*/portrait', (route) => {
      if (route.request().method() !== 'PUT' || refused) return route.continue()
      refused = true
      refusals.left += 1
      return route.fulfill({ status: 500, contentType: 'application/json', body: JSON.stringify({ error: 'The disk is full.' }) })
    })
    await page.locator('form.editor input[type=file]').setInputFiles({ name: 'portrait.png', mimeType: 'image/png', buffer: PNG })
    await page.getByRole('button', { name: 'Save to the library' }).click()
    await page.getByText('Saved Dana Okafor, but not their portrait').waitFor()
    await page.getByRole('button', { name: 'Save', exact: true }).click()
    await page.getByText(/^Saved Dana Okafor\.$/).waitFor()
    await page.unroute('**/api/characters/*/portrait')
    if (posts.length !== 1) throw new Error(`Saving posted ${posts.length} new characters, not 1.`)
  })
}

/** The library finds people by their words, duplicates one, and a backup brings back one deleted since. */
async function library(page) {
  await step('search finds them by their words', async () => {
    const search = page.getByLabel('Search characters')
    await search.fill('zzzz nobody')
    await page.getByText('No one matches.').waitFor()
    await search.fill('grudges')
    await page.locator('aside').getByText('Dana Okafor').first().waitFor()
    await search.fill('')
  })
  await step('Duplicate opens a copy', async () => {
    await page.locator('aside').getByText('Dana Okafor').first().click()
    await page.getByRole('button', { name: 'Duplicate them' }).click()
    await page.getByRole('heading', { name: 'Dana Okafor (copy)' }).waitFor()
  })
  let backup = ''
  await step('Back up downloads the library', async () => {
    const download = page.waitForEvent('download')
    await page.getByRole('link', { name: 'Back up' }).click()
    backup = join(tmpdir(), `walk-backup-${Date.now()}.zip`)
    await (await download).saveAs(backup)
  })
  await step('a backup brings back the copy deleted since, and leaves the rest', async () => {
    let asked = ''
    page.once('dialog', (dialog) => { asked = dialog.message(); void dialog.accept() })
    await page.getByRole('button', { name: 'Delete them' }).click()
    await page.getByRole('heading', { name: 'A new character' }).waitFor()
    if (!asked.startsWith('Delete Dana Okafor (copy)')) throw new Error(`Delete asked: ${asked}`)
    await page.getByLabel('Backup file').setInputFiles(backup)
    const said = page.locator('.library-tools [role=status]')
    await said.waitFor()
    if (!/^Brought back 1 character\. \d+ already here were left as they are\.$/.test(await said.innerText())) throw new Error(`The backup said: ${await said.innerText()}`)
    await page.locator('aside').getByText('Dana Okafor (copy)').waitFor()
  })
}

/** A blank cast board opens, keeps through a reload, and Back and Forward move through the views. */
async function cast(page) {
  await step('a cast board starts', async () => {
    await page.getByRole('button', { name: 'New cast' }).click()
    await page.getByRole('button', { name: /Start (a blank|the) board/ }).click()
    await page.getByLabel('Title').fill('The Long Winter')
    await shot(page, '05-board')
  })
  await step('a board not saved yet survives a reload', async () => {
    await page.waitForTimeout(200)
    await page.reload()
    const title = page.getByLabel('Title')
    await title.waitFor()
    if (await title.inputValue() !== 'The Long Winter') throw new Error(`The title came back as "${await title.inputValue()}".`)
  })
  await step('Back and Forward move between views', async () => {
    await page.goBack()
    await page.getByRole('heading', { name: 'A new cast' }).waitFor()
    await page.goForward()
    await page.getByLabel('Title').waitFor()
  })
}

/** The start screen fits a phone with no sideways scroll. */
async function phone(browser) {
  const context = await browser.newContext({ viewport: { width: 390, height: 844 } })
  const page = await context.newPage()
  watch(page)
  await step('the start screen fits a phone', async () => {
    await page.goto(URL)
    await page.getByRole('heading', { name: 'A new character' }).waitFor()
    const wide = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)
    if (wide > 0) throw new Error(`The page scrolls sideways by ${wide}px.`)
    await shot(page, '06-phone')
  })
  await context.close()
}

const browser = await chromium.launch()
let failed = false
try {
  const context = await browser.newContext({ viewport: { width: 1360, height: 900 } })
  context.setDefaultTimeout(15000)
  const page = await context.newPage()
  watch(page)
  await character(page)
  if (process.env.WALK_README) await readme(browser)
  await paste(page)
  await portrait(page)
  await library(page)
  await cast(page)
  await phone(browser)
  if (errors.length) throw new Error(`The page logged errors:\n${errors.join('\n')}`)
} catch (error) {
  failed = true
  if (errors.length && !String(error.message).startsWith('The page logged')) console.error(errors.join('\n'))
  console.error(error.message)
} finally {
  await browser.close()
}
process.exit(failed ? 1 : 0)
