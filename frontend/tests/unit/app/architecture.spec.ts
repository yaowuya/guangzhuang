import { readdirSync, readFileSync } from 'node:fs'
import { join, relative } from 'node:path'
import { expect, it } from 'vitest'

function sourceFiles(directory: string): string[] {
  return readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const path = join(directory, entry.name)
    return entry.isDirectory() ? sourceFiles(path) : /\.(?:ts|vue)$/.test(entry.name) ? [path] : []
  })
}

function imports(path: string): string[] {
  const text = readFileSync(path, 'utf8')
  const patterns = [
    /\bfrom\s+['"]([^'"]+)['"]/g,
    /\bimport\s+['"]([^'"]+)['"]/g,
    /\bimport\s*\(\s*['"]([^'"]+)['"]\s*\)/g,
  ]
  return patterns.flatMap((pattern) => [...text.matchAll(pattern)].map((match) => match[1]))
}

it('keeps shared and feature imports pointing inward', () => {
  for (const path of sourceFiles('src/shared')) {
    for (const target of imports(path)) {
      expect(target, `${relative('src', path)} -> ${target}`).not.toMatch(/(?:^|\/)features(?:\/|$)|(?:^|\/)app(?:\/|$)/)
    }
  }
  for (const path of sourceFiles('src/features')) {
    for (const target of imports(path)) {
      expect(target, `${relative('src', path)} -> ${target}`).not.toMatch(/(?:^|\/)app(?:\/|$)/)
    }
  }
})
