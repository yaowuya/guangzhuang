import { it, expect } from 'vitest'
import { mkdtempSync, mkdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join, resolve } from 'node:path'
import { spawnSync } from 'node:child_process'

/** 验证交给静态网关的工程入口不是旧演示页或开发代理。 */
it('builds a local Vue entry for the gateway, not the prototype', () => {
  const main = readFileSync('src/app/main.ts', 'utf8')
  expect(main).toContain('createApp')
  expect(main).not.toContain('prototype')

  const vite = readFileSync('vite.config.ts', 'utf8')
  expect(vite).toContain("outDir: 'dist'")
  expect(vite).not.toContain('proxy:')
})

/** UNIT_ONLY：构造静态构建工具的文件输入，不是业务数据或浏览器 E2E。 */
function artifactProject() {
  const root = mkdtempSync(join(tmpdir(), 'beauty-artifact-'))
  mkdirSync(join(root, 'dist', 'assets'), { recursive: true })
  writeFileSync(
    join(root, 'dist', 'index.html'),
    '<!doctype html><div id="app"></div><script type="module" src="/assets/app.js"></script>',
  )
  // 框架正常使用 Object.prototype，不能把这个单词误判为原型页面泄漏。
  writeFileSync(join(root, 'dist', 'assets', 'app.js'), 'console.log(Object.prototype.toString.call({}));')
  return root
}

it('rejects references to the old demonstration page in build output', () => {
  const checker = resolve('scripts/check-artifact.mjs')
  const project = artifactProject()
  try {
    writeFileSync(join(project, 'dist', 'assets', 'app.js'), 'const preview = "/prototype.html?sample=licensed";')
    const result = spawnSync(process.execPath, [checker], { cwd: project, encoding: 'utf8' })
    expect(result.status).not.toBe(0)
    expect(result.stderr).toContain('原型')
  } finally {
    rmSync(project, { recursive: true, force: true })
  }
})

it('rejects server credential markers in the public static artifact', () => {
  const checker = resolve('scripts/check-artifact.mjs')
  const project = artifactProject()
  try {
    // 仅为公开工具的拒绝样例，不包含真实密钥。
    writeFileSync(join(project, 'dist', 'assets', 'app.js'), 'const marker = "-----BEGIN PRIVATE KEY-----";')
    const result = spawnSync(process.execPath, [checker], { cwd: project, encoding: 'utf8' })
    expect(result.status).not.toBe(0)
    expect(result.stderr).toContain('凭据')
  } finally {
    rmSync(project, { recursive: true, force: true })
  }
})

it('only accepts a self-contained static artifact for the gateway', () => {
  const checker = resolve('scripts/check-artifact.mjs')
  const project = artifactProject()
  const run = () => spawnSync(process.execPath, [checker], { cwd: project, encoding: 'utf8' })
  try {
    const valid = run()
    expect(valid.status, valid.stderr).toBe(0)
    const report = JSON.parse(valid.stdout)
    expect(report.buildIdentity).toMatch(/^[a-f0-9]{64}$/)
    expect(report.assets).toEqual(['assets/app.js'])

    rmSync(join(project, 'dist', 'assets', 'app.js'))
    const broken = run()
    expect(broken.status).not.toBe(0)
    expect(broken.stderr).toContain('assets/app.js')
  } finally {
    rmSync(project, { recursive: true, force: true })
  }
})
