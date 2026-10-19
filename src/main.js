import { createApp } from 'vue'
import App from './App.vue'
import 'virtual:svg-icons-register'
import SvgIcon from './components/SvgIcon.vue'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'

const app = createApp(App)
app.component('SvgIcon', SvgIcon)
app.use(ElementPlus)
app.mount('#app')
