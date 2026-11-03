import { it, expect } from 'vitest'
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join, resolve } from 'node:path'
import { spawnSync } from 'node:child_process'

/** VS-001 的来源记录是测试输入，不是已通过的新界面视觉证据。 */
it('freezes approved static sources without pretending Figma exists', () => {
  const map = JSON.parse(readFileSync('tests/visual/source-map.json', 'utf8'))
  expect(map.override).toBe('VS-001')
  expect(map.figma).toBeNull()
  expect(map.sources.map((source: { key: string }) => source.key)).toEqual([
    'R-P', 'R-D', 'R-T', 'R-M', 'R-S', 'R-F',
  ])
  expect(map.forbiddenBusinessFields).toContain('summary')
  expect(map.runtimeAsReference).toBe(false)
})

/** UNIT_ONLY：临时映射只用于反例，不会改动已批准的原始图像或设计。 */
type SourceMapRecord = {
  sources: { key: string; path: string; sha256: string }[]
}

function checkMutation(mutate: (map: SourceMapRecord) => void) {
  const directory = mkdtempSync(join(tmpdir(), 'beauty-visual-source-'))
  const checker = resolve('scripts/check-visual-sources.mjs')
  try {
    const map = JSON.parse(readFileSync('tests/visual/source-map.json', 'utf8'))
    mutate(map)
    const path = join(directory, 'source-map.json')
    writeFileSync(path, JSON.stringify(map))
    return spawnSync(process.execPath, [checker, '--map', path], { cwd: resolve('..'), encoding: 'utf8' })
  } finally {
    rmSync(directory, { recursive: true, force: true })
  }
}

it('rejects a changed source digest instead of approving a new revision', () => {
  const result = checkMutation((map) => { map.sources[1].sha256 = '0'.repeat(64) })
  expect(result.status).not.toBe(0)
  expect(result.stderr).toMatch(/hash|摘要/)
})

it('rejects a runtime artifact masquerading as a reference', () => {
  const result = checkMutation((map) => {
    map.sources[1].path = 'fp-docs/changes/beauty-intelligence-mvp/.fp-execute/visual/runtime.png'
  })
  expect(result.status).not.toBe(0)
  expect(result.stderr).toMatch(/approved|批准|来源/)
})

it('rejects a missing approved image without replacing it with a fixture', () => {
  const result = checkMutation((map) => {
    map.sources[1].path = 'fp-docs/changes/beauty-intelligence-mvp/.prototype-evidence/taste/inspect/missing.jpg'
  })
  expect(result.status).not.toBe(0)
  expect(result.stderr).toMatch(/approved|批准|来源/)
})
