import { createApp } from "vue";

import App from "./App.vue";
import router from "./router";
import "./style.css";
import { APP_BRAND_NAME } from "@/constants/branding";

if (typeof document !== "undefined") {
  document.title = APP_BRAND_NAME;
}

createApp(App).use(router).mount("#app");
