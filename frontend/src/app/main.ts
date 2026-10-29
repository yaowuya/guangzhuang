import { createApp } from 'vue'
import App from './App.vue'
import router from './router'

/** 只挂载应用和路由；业务数据由受保护的接口提供。 */
createApp(App).use(router).mount('#app')
