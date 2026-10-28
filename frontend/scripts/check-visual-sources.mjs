import { createHash } from 'node:crypto'
import { lstatSync, readFileSync } from 'node:fs'
import { dirname, isAbsolute, relative, resolve, sep } from 'node:path'

/**
 * 校验用户批准的本地原型来源；不创建参考图，也不签发视觉通过结论。
 * 所有路径与摘要单独固定，防止映射文件改向运行截图后自行声称已批准。
 */
const change = 'fp-docs/changes/beauty-intelligence-mvp'
const approved = [
  ['R-P', 'approved-prototype', `${change}/prototype.html`, 'eaad55cbf304ccaa3c50d84e3f94e9e3ab1ed9354657490594236c90c1b7ed6c'],
  ['R-D', 'approved-static-screenshot', `${change}/.prototype-evidence/taste/inspect/desktop-fold.jpg`, 'e18dbdf9a49265a71a6ca7a386455ce83c8cfaa6b0e6e88cb7d9c7765357bad0', 1440, 900],
  ['R-T', 'approved-static-screenshot', `${change}/.prototype-evidence/taste/inspect/tablet-fold.jpg`, '789ef7e1ef243ff2ef854186c07459c6f5514fed1f8b51423a00a843c3fb8f85', 768, 1024],
  ['R-M', 'approved-static-screenshot', `${change}/.prototype-evidence/taste/inspect/mobile-fold.jpg`, '61947d7ee017a1876e47dbe60601d42e458cf4dc1889b54a1face23c0cd7b260', 390, 844],
  ['R-S', 'confirmed-ui-spec', `${change}/design/frontend.md`, 'e4f9c5c6aae0a2ba4df88416e2a8613ca933d8891a70f389effe8bf56af8b340'],
  ['R-F', 'licensed-font-assets', `${change}/.prototype-evidence/instrument-sans.ttf`, 'b24f1812584816958afcf22e22d08e44318c5e51651e25d2438efdde389b33b1'],
]
const fontLicense = {
  path: `${change}/.prototype-evidence/font-license.txt`,
  hash: '9e27a72ed30eb49a08678f6a5d6ed98ec7ba5368f541637ee0683ec9134ef966',
}

function fail(reason) {
  throw new Error(`批准的视觉来源校验失败：${reason}`)
}

function sourceBytes(projectRoot, sourcePath, expectedHash) {
  if (!sourcePath.startsWith(`${change}/`) || sourcePath.includes('\\') || sourcePath.includes('/../') || sourcePath.includes('/./')) {
    fail('来源不在批准的变更路径内')
  }
  const target = resolve(projectRoot, sourcePath)
  const rel = relative(projectRoot, target)
  if (isAbsolute(rel) || rel.startsWith(`..${sep}`) || rel === '..') fail('来源越过仓库边界')
  // lstat detects replacement by a symbolic link without dereferencing it.
  if (!lstatSync(target).isFile()) fail(`来源不是普通文件：${sourcePath}`)
  const bytes = readFileSync(target)
  const actual = createHash('sha256').update(bytes).digest('hex')
  if (actual !== expectedHash) fail(`来源 hash 摘要变化：${sourcePath}`)
  return bytes
}

/** 仅读 JPEG 的 SOF 标头，不加载图片库，不改变静态原图。 */
function dimensions(bytes) {
  if (bytes.length < 4 || bytes[0] !== 0xff || bytes[1] !== 0xd8) fail('静态图不是 JPEG')
  let i = 2
  while (i + 4 <= bytes.length) {
    if (bytes[i++] !== 0xff) fail('JPEG 标记损坏')
    while (bytes[i] === 0xff) i++
    const marker = bytes[i++]
    if (marker === 0xd9 || marker === 0xda) break
    if (marker === 0x01 || (marker >= 0xd0 && marker <= 0xd7)) continue
    if (i + 2 > bytes.length) break
    const length = bytes.readUInt16BE(i)
    if (length < 2 || i + length > bytes.length) fail('JPEG 片段长度非法')
    if ([0xc0, 0xc1, 0xc2, 0xc3, 0xc5, 0xc6, 0xc7, 0xc9, 0xca, 0xcb, 0xcd, 0xce, 0xcf].includes(marker)) {
      if (length < 7) fail('JPEG 图像尺寸缺失')
      // SOF 顺序为 precision、height、width；返回接口固定为 width、height。
      return [bytes.readUInt16BE(i + 5), bytes.readUInt16BE(i + 3)]
    }
    i += length
  }
  fail('JPEG 不含可验证的图像尺寸')
}

function verify(map, root) {
  if (map.schemaVersion !== 1 || map.override !== 'VS-001' || map.figma !== null || map.runtimeAsReference !== false) {
    fail('视觉来源范围或 Figma 边界被改写')
  }
  if (!Array.isArray(map.forbiddenBusinessFields) || !map.forbiddenBusinessFields.includes('summary')) {
    fail('旧摘要排除边界缺失')
  }
  if (!Array.isArray(map.sources) || map.sources.length !== approved.length) fail('来源清单不是批准版本')
  const inspected = []
  for (let n = 0; n < approved.length; n++) {
    const [key, kind, sourcePath, hash, width, height] = approved[n]
    const item = map.sources[n]
    if (item?.key !== key || item.kind !== kind) fail('来源键或类型不是批准版本')
    const recordedPath = key === 'R-F' ? item.files?.[0]?.path : item.path
    const recordedHash = key === 'R-F' ? item.files?.[0]?.sha256 : item.sha256
    if (recordedPath !== sourcePath || recordedHash !== hash) fail(`来源路径或 hash 摘要不属于批准版本：${key}`)
    let bytes
    try { bytes = sourceBytes(root, sourcePath, hash) }
    catch (error) { fail(error instanceof Error ? error.message : `来源无法读取：${key}`) }
    if (width !== undefined) {
      if (item.viewport?.width !== width || item.viewport?.height !== height) fail(`批准截图标注的视口不一致：${key}`)
      const [actualWidth, actualHeight] = dimensions(bytes)
      if (actualWidth !== width || actualHeight !== height) fail(`批准截图的实际尺寸不一致：${key}`)
    }
    inspected.push({ key, hash })
  }
  const font = map.sources[5]
  if (font.license !== 'SIL Open Font License 1.1' || font.files?.[1]?.path !== fontLicense.path || font.files?.[1]?.sha256 !== fontLicense.hash) {
    fail('本地字体与许可文件的配对不属于批准版本')
  }
  try { sourceBytes(root, fontLicense.path, fontLicense.hash) }
  catch (error) { fail(error instanceof Error ? error.message : '字体许可文件不存在') }
  return inspected
}

const args = process.argv.slice(2)
try {
  if (args.length !== 0 && (args.length !== 2 || args[0] !== '--map')) fail('仅支持可读映射路径 --map')
  const cwd = process.cwd()
  const projectRoot = cwd.endsWith(`${sep}frontend`) ? cwd : resolve(cwd, 'frontend')
  const mapFile = args[1] ? resolve(args[1]) : resolve(projectRoot, 'tests/visual/source-map.json')
  // Unit mutation changes only the map, not the fixed approved repository root.
  const sources = verify(JSON.parse(readFileSync(mapFile, 'utf8')), resolve(projectRoot, '..'))
  console.log(JSON.stringify({ visualSource: 'VS-001', verified: sources, runtimeVisualReviewed: false }))
} catch (error) {
  console.error(error instanceof Error ? error.message : '批准的来源校验失败')
  process.exitCode = 1
}
