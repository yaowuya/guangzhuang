import { ref } from 'vue'
import { ApiError } from '../api/client'
import type { ApiClient } from '../api/client'
import type { AuthOut } from '../api/contracts'

export type SessionStatus = 'unknown' | 'loading' | 'authenticated' | 'anonymous' | 'expired'

/**
 * 将单人服务端会话暂存于当前页面内存。服务器才决定有效期与权限；
 * 不保存密码、CSRF 或写操作，不在重新登录后重放失败的操作。
 */
export function createSession(api: ApiClient) {
  const auth = ref<AuthOut | null>(null)
  const status = ref<SessionStatus>('unknown')
  let pendingEnsure: Promise<AuthOut | null> | null = null
  let revision = 0
  let authMutation: Promise<void> = Promise.resolve()

  /** 登录和退出都会改变浏览器 Cookie；串行发送才能让 Cookie 与内存状态保持相同顺序。 */
  function serializeAuth<T>(action: () => Promise<T>): Promise<T> {
    const result = authMutation.catch(() => undefined).then(action)
    authMutation = result.then(() => undefined, () => undefined)
    return result
  }

  function clear(reason: 'anonymous' | 'expired' = 'anonymous') {
    revision += 1
    auth.value = null
    status.value = reason
  }

  function ensure(): Promise<AuthOut | null> {
    if (pendingEnsure) return pendingEnsure
    status.value = 'loading'
    const hadSession = auth.value !== null
    const checkingRevision = revision
    const work = api.getSession().then((confirmed) => {
      if (checkingRevision !== revision) return auth.value
      auth.value = confirmed
      status.value = 'authenticated'
      return confirmed
    }).catch((error: unknown) => {
      // 较早的 GET 不得把后来已成功登录的会话误判过期。
      if (checkingRevision !== revision) return auth.value
      if (error instanceof ApiError && error.status === 401) {
        clear(hadSession ? 'expired' : 'anonymous')
        return null
      }
      status.value = hadSession ? 'authenticated' : 'unknown'
      throw error
    })
    pendingEnsure = work.finally(() => { pendingEnsure = null })
    return pendingEnsure
  }

  function login(password: string): Promise<AuthOut> {
    return serializeAuth(async () => {
      try {
        const confirmed = await api.login(password)
        revision += 1
        auth.value = confirmed
        status.value = 'authenticated'
        return confirmed
      } catch (error) {
        if (error instanceof ApiError && error.status === 401 && !auth.value) clear()
        throw error
      }
    })
  }

  function logout(): Promise<void> {
    return serializeAuth(async () => {
      if (!auth.value) throw new ApiError(401, 'unauthenticated', '登录已失效', '')
      const currentRevision = revision
      const csrf = auth.value.csrf_token
      try {
        await api.logout(csrf)
        if (currentRevision === revision) clear()
      } catch (error) {
        // 403 不代表退出成功；认证写串行后仍用 revision 防止其它本地清理改变归属。
        if (currentRevision === revision && error instanceof ApiError && error.status === 401) {
          clear('expired')
        }
        throw error
      }
    })
  }

  async function protect<T>(action: (csrf: string) => Promise<T>): Promise<T> {
    if (!auth.value) throw new ApiError(401, 'unauthenticated', '请先登录', '')
    const currentRevision = revision
    const csrf = auth.value.csrf_token
    try {
      return await action(csrf)
    } catch (error) {
      if (currentRevision === revision && error instanceof ApiError && error.status === 401) {
        clear('expired')
      }
      throw error
    }
  }

  return { auth, status, ensure, login, logout, protect, clear }
}

export type SessionState = ReturnType<typeof createSession>
