import { createApi } from '../shared/api/client'
import { createSession } from '../features/auth/session'

/** 单页共享一次 HTTP 与会话实例；模块导入不发请求、不启动后台任务。 */
export const api = createApi()
export const session = createSession(api)
