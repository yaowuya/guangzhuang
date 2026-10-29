import { createRouter, createWebHistory } from 'vue-router'

/** 工程入口的路由容器；认证任务负责注册实际业务路由与守卫。 */
const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [],
})

export default router
