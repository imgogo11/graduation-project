<script setup lang="ts">
import {
  dateZhCN,
  NConfigProvider,
  NDialogProvider,
  NGlobalStyle,
  NLoadingBarProvider,
  NMessageProvider,
  NNotificationProvider,
  zhCN,
} from "naive-ui";
import { RouterView, useRoute } from "vue-router";

import AppShell from "@/components/AppShell.vue";


const route = useRoute();
</script>

<template>
  <n-config-provider :locale="zhCN" :date-locale="dateZhCN">
    <n-global-style />
    <n-loading-bar-provider>
      <n-dialog-provider>
        <n-notification-provider>
          <n-message-provider :container-style="{ top: '18vh' }">
            <RouterView v-if="route.meta.layout === 'auth'" />
            <AppShell v-else />
          </n-message-provider>
        </n-notification-provider>
      </n-dialog-provider>
    </n-loading-bar-provider>
  </n-config-provider>
</template>
