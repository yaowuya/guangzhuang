import { it, expect, vi } from 'vitest'
import { createApi, ApiError } from '../../../../src/shared/api/client'
import { createSession } from '../../../../src/features/auth/session'
import { authFixture } from '../../fixtures'

/** UNIT_ONLY：HTTP 边界只用合成结果验证状态机，不代表真实登录或 E2E。 */
it('invalidates expired auth without replaying the protected action', async () => {
  const api = createApi(vi.fn<typeof fetch>())
  vi.spyOn(api, 'login').mockResolvedValue(authFixture())
  const session = createSession(api)
  await session.login('unit-password')
  const action = vi.fn().mockRejectedValue(new ApiError(401, 'unauthenticated', '已过期', 'unit-2'))
  await expect(session.protect(action)).rejects.toMatchObject({ status: 401 })
  expect(session.auth.value).toBeNull()
  expect(session.status.value).toBe('expired')
  await session.login('unit-password')
  expect(action).toHaveBeenCalledTimes(1)
})

it('does not allow an older session check to clear a newer successful login', async () => {
  const api = createApi(vi.fn<typeof fetch>())
  let rejectCheck!: (reason: unknown) => void
  vi.spyOn(api, 'getSession').mockReturnValue(new Promise((_, reject) => { rejectCheck = reject }))
  vi.spyOn(api, 'login').mockResolvedValue(authFixture())
  const session = createSession(api)
  const oldCheck = session.ensure()
  await session.login('unit-password')
  rejectCheck(new ApiError(401, 'unauthenticated', '旧检查已过期', 'unit-3'))
  await oldCheck
  expect(session.status.value).toBe('authenticated')
  expect(session.auth.value?.csrf_token).toBe('unit-csrf')
})

it('serializes concurrent logins so browser cookies and memory keep the same order', async () => {
  const api = createApi(vi.fn<typeof fetch>())
  let finishFirstLogin!: (value: ReturnType<typeof authFixture>) => void
  const login = vi.spyOn(api, 'login')
    .mockReturnValueOnce(new Promise((resolve) => { finishFirstLogin = resolve }))
    .mockResolvedValueOnce({ ...authFixture(), csrf_token: 'new-session-csrf' })
  const session = createSession(api)
  const first = session.login('old-password')
  const second = session.login('new-password')
  await vi.waitFor(() => expect(login).toHaveBeenCalledTimes(1))
  finishFirstLogin(authFixture())
  expect((await first).csrf_token).toBe('unit-csrf')
  expect((await second).csrf_token).toBe('new-session-csrf')
  expect(login).toHaveBeenCalledTimes(2)
  expect(session.auth.value?.csrf_token).toBe('new-session-csrf')
})

it('lets an in-flight login finish after a local clear to match the confirmed cookie', async () => {
  const api = createApi(vi.fn<typeof fetch>())
  let finishLogin!: (value: ReturnType<typeof authFixture>) => void
  vi.spyOn(api, 'login').mockReturnValue(new Promise((resolve) => { finishLogin = resolve }))
  const session = createSession(api)
  const pending = session.login('unit-password')
  session.clear()
  finishLogin(authFixture())
  await pending
  expect(session.auth.value?.csrf_token).toBe('unit-csrf')
  expect(session.status.value).toBe('authenticated')
})

it('queues a new login behind logout so late cookie deletion cannot erase it', async () => {
  const api = createApi(vi.fn<typeof fetch>())
  const login = vi.spyOn(api, 'login').mockResolvedValueOnce(authFixture())
    .mockResolvedValueOnce({ ...authFixture(), csrf_token: 'new-session-csrf' })
  let finishLogout!: (value: { authenticated: false }) => void
  vi.spyOn(api, 'logout').mockReturnValue(new Promise((resolve) => { finishLogout = resolve }))
  const session = createSession(api)
  await session.login('unit-password')
  const oldLogout = session.logout()
  const newLogin = session.login('unit-password')
  expect(login).toHaveBeenCalledTimes(1)
  finishLogout({ authenticated: false })
  await oldLogout
  await newLogin
  expect(login).toHaveBeenCalledTimes(2)
  expect(session.auth.value?.csrf_token).toBe('new-session-csrf')
  expect(session.status.value).toBe('authenticated')
})

it('does not let an old protected write invalidate a later login', async () => {
  const api = createApi(vi.fn<typeof fetch>())
  vi.spyOn(api, 'login').mockResolvedValueOnce(authFixture())
    .mockResolvedValueOnce({ ...authFixture(), csrf_token: 'new-session-csrf' })
  const session = createSession(api)
  await session.login('unit-password')
  let failOldWrite!: (reason: unknown) => void
  const action = vi.fn().mockReturnValue(new Promise((_, reject) => { failOldWrite = reject }))
  const pending = session.protect(action)
  await session.login('unit-password')
  failOldWrite(new ApiError(401, 'unauthenticated', '旧会话已撤销', 'unit-4'))
  await expect(pending).rejects.toMatchObject({ status: 401 })
  expect(session.auth.value?.csrf_token).toBe('new-session-csrf')
  expect(action).toHaveBeenCalledTimes(1)
})

it('shares one server verification between concurrent session checks', async () => {
  const api = createApi(vi.fn<typeof fetch>())
  let finish!: (value: ReturnType<typeof authFixture>) => void
  const getSession = vi.spyOn(api, 'getSession').mockReturnValue(new Promise((resolve) => { finish = resolve }))
  const session = createSession(api)
  const first = session.ensure()
  const second = session.ensure()
  expect(first).toBe(second)
  expect(getSession).toHaveBeenCalledTimes(1)
  finish(authFixture())
  expect((await second)?.csrf_token).toBe('unit-csrf')
  expect(session.status.value).toBe('authenticated')
})

it('keeps auth on rejected logout, but clears it after confirmed logout', async () => {
  const api = createApi(vi.fn<typeof fetch>())
  vi.spyOn(api, 'login').mockResolvedValue(authFixture())
  const logout = vi.spyOn(api, 'logout')
    .mockRejectedValueOnce(new ApiError(403, 'csrf_invalid', '不允许', 'unit-5'))
    .mockResolvedValueOnce({ authenticated: false })
  const session = createSession(api)
  await session.login('unit-password')
  await expect(session.logout()).rejects.toMatchObject({ status: 403 })
  expect(session.auth.value?.csrf_token).toBe('unit-csrf')
  await session.logout()
  expect(session.auth.value).toBeNull()
  expect(session.status.value).toBe('anonymous')
  expect(logout).toHaveBeenCalledTimes(2)
})

it('keeps CSRF and passwords out of browser storage', async () => {
  const writeStorage = vi.spyOn(Storage.prototype, 'setItem')
  const api = createApi(vi.fn<typeof fetch>())
  vi.spyOn(api, 'login').mockResolvedValue(authFixture())
  vi.spyOn(api, 'logout').mockResolvedValue({ authenticated: false })
  const session = createSession(api)
  await session.login('unit-password')
  await session.logout()
  expect(writeStorage).not.toHaveBeenCalled()
})
