import { createHash } from 'node:crypto'
import { lstatSync, readFileSync, readdirSync } from 'node:fs'
import { dirname, extname, isAbsolute, join, relative, resolve, sep } from 'node:path'

/**
 * 检查当前项目 dist 的本地静态交接，并输出字节级 build identity。
 * 这里只读文件和校验引用，不运行应用，不证明业务、视觉或 E2E 已通过。
 */
const expectedNode = 'v24.21.0'

function artifactFiles(directory, root = directory) {
  const paths = []
  for (const entry of readdirSync(directory, { withFileTypes: true })) {
    const fullPath = join(directory, entry.name)
    if (entry.isSymbolicLink()) throw new Error('静态产物不能包含符号链接')
    if (entry.isDirectory()) paths.push(...artifactFiles(fullPath, root))
    else if (entry.isFile()) paths.push(relative(root, fullPath).split(sep).join('/'))
  }
  return paths.sort()
}

/** Caddy 的根相对地址映射到 dist；引用不得逃逸到项目文件或外站。 */
function localReference(reference, source, dist) {
  if (/^(?:[a-z][a-z\d+.-]*:|\/\/)/i.test(reference)) {
    throw new Error('静态资源必须使用本地产物地址')
  }
  const pathname = decodeURIComponent(reference.split(/[?#]/, 1)[0])
  if (!pathname) throw new Error('静态资源地址不能为空')
  const target = pathname.startsWith('/')
    ? resolve(dist, pathname.slice(1))
    : resolve(dist, dirname(source), pathname)
  const name = relative(dist, target)
  if (isAbsolute(name) || name === '..' || name.startsWith(`..${sep}`)) {
    throw new Error('静态资源引用越过 dist 边界')
  }
  try {
    if (!lstatSync(target).isFile()) throw new Error('not a file')
  } catch {
    throw new Error(`静态资源不存在：${name.split(sep).join('/')}`)
  }
}

function references(name, content) {
  if (extname(name) === '.html') {
    return [...content.matchAll(/<(?:script|link)\b[^>]*\b(?:src|href)=["']([^"']+)["'][^>]*>/gi)]
      .map((match) => match[1])
  }
  if (extname(name) === '.css') {
    return [...content.matchAll(/url\(\s*["']?([^"')]+)["']?\s*\)/gi)]
      .map((match) => match[1].trim())
  }
  if (extname(name) === '.js') {
    return [...content.matchAll(/\b(?:from|import)\s*(?:\(\s*)?["']([^"']+)["']/g)]
      .map((match) => match[1])
  }
  return []
}

try {
  if (process.version !== expectedNode) {
    throw new Error(`请使用已选 bundled Node ${expectedNode}`)
  }
  const dist = resolve(process.cwd(), 'dist')
  const files = artifactFiles(dist)
  if (!files.includes('index.html')) throw new Error('静态产物缺少 index.html')
  const html = readFileSync(join(dist, 'index.html'), 'utf8')
  if (!/\bid\s*=\s*["']app["']/.test(html)) throw new Error('入口缺少应用挂载点')
  if (!/<script\b[^>]*\bsrc=/i.test(html)) throw new Error('入口缺少构建后的脚本')

  const hash = createHash('sha256')
  for (const name of files) {
    const bytes = readFileSync(join(dist, name))
    hash.update(name).update('\0').update(bytes).update('\0')
    if (['.html', '.css', '.js'].includes(extname(name))) {
      const content = bytes.toString('utf8')
      // 仅拦截已知演示路径；Object.prototype 等正常框架代码必须允许。
      if (/(?:prototype\.html|\.prototype-evidence\/|sample=licensed)/i.test(content)) {
        throw new Error('构建产物包含旧原型或演示入口')
      }
      // 只能识别明确的服务端凭据标记，不能代替源码和发布秘密检查。
      if (/-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|\b(?:PASSWORD_HASH|CSRF_KEY)\b/.test(content)) {
        throw new Error('公开构建产物包含服务端凭据标记')
      }
      for (const ref of references(name, content)) localReference(ref, name, dist)
    }
  }
  console.log(JSON.stringify({
    entry: 'index.html',
    buildIdentity: hash.digest('hex'),
    assets: files.filter((name) => name !== 'index.html'),
  }))
} catch (error) {
  console.error(error instanceof Error ? error.message : '静态产物检查失败')
  process.exitCode = 1
}
