<script setup lang="ts">
import { computed, reactive, ref } from "vue";

import { NButton, NForm, NFormItem, NInput } from "naive-ui";
import { RouterLink, useRoute, useRouter } from "vue-router";

import { loginUser } from "@/api/auth";
import { useAuthStore } from "@/stores/auth";
import { getErrorMessage } from "@/utils/format";
import { usePageErrorNotification } from "@/composables/usePageErrorNotification";


const route = useRoute();
const router = useRouter();
const auth = useAuthStore();
const loading = ref(false);
const error = ref("");
usePageErrorNotification(error, "Login Error");
const form = reactive({
  username: "",
  password: "",
});

const highlights = computed(() => [
  {
    label: "统一后台骨架",
    value: "工作台、数据集管理、分析中心与算法雷达提供统一操作入口",
  },
  {
    label: "安全登录",
    value: "基于账号登录与会话鉴权保障访问安全",
  },
  {
    label: "研究型业务",
    value: "覆盖交易导入、统计分析区间算法与风险雷达",
  },
]);

async function submit() {
  loading.value = true;
  error.value = "";

  try {
    const response = await loginUser(form);
    auth.applySession(response);
    const fallback = response.user.role === "admin" ? "/admin/overview" : "/workbench";
    const redirect = typeof route.query.redirect === "string" ? route.query.redirect : fallback;
    await router.replace(redirect);
  } catch (err) {
    error.value = getErrorMessage(err);
  } finally {
    loading.value = false;
  }
}
</script>

<template>
  <div class="auth-page">
    <section class="auth-shell">
      <div class="auth-shell__visual">
        <div class="auth-shell__headline">
          <div class="auth-shell__eyebrow">Naive Admin Refresh</div>
          <h1 class="auth-shell__title">股票交易数据管理与分析系统</h1>
          <p class="auth-shell__subtitle">
            系统覆盖数据导入、统计分析、区间算法与风险雷达，支持完整研究流程。
          </p>
        </div>

        <div class="auth-shell__cards">
          <div v-for="item in highlights" :key="item.label" class="auth-shell__card">
            <div class="auth-shell__card-label">{{ item.label }}</div>
            <div class="auth-shell__card-value">{{ item.value }}</div>
          </div>
        </div>
      </div>

      <div class="auth-shell__form">
        <div class="auth-shell__form-header">
          <h1>登录系统</h1>
          <p>登录后可进入工作台，继续处理数据导入、数据集预览与分析任务</p>
        </div>
<n-form class="auth-form" label-placement="top" @submit.prevent="submit">
          <n-form-item label="用户">
            <n-input v-model:value="form.username" placeholder="请输入用户名" />
          </n-form-item>
          <n-form-item label="密码">
              <n-input
                v-model:value="form.password"
                type="password"
                show-password-on="click"
                placeholder="请输入密码" />
            </n-form-item>
          <n-button type="primary" :loading="loading" block attr-type="submit">登录</n-button>
        </n-form>

        <p class="auth-footer">
          还没有账号？
          <RouterLink to="/register">去注册</RouterLink>
        </p>
      </div>
    </section>
  </div>
</template>


