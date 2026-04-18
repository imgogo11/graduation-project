<script setup lang="ts">
import { reactive, ref } from "vue";

import { NButton, NForm, NFormItem, NInput } from "naive-ui";
import { RouterLink, useRouter } from "vue-router";

import { registerUser } from "@/api/auth";
import { useAuthStore } from "@/stores/auth";
import { getErrorMessage } from "@/utils/format";
import { usePageErrorNotification } from "@/composables/usePageErrorNotification";


const router = useRouter();
const auth = useAuthStore();
const loading = ref(false);
const error = ref("");
usePageErrorNotification(error, "Register Error");
const form = reactive({
  username: "",
  password: "",
  confirmPassword: "",
});

async function submit() {
  if (form.password !== form.confirmPassword) {
    error.value = "两次输入的密码不一致";
    return;
  }

  loading.value = true;
  error.value = "";

  try {
    const response = await registerUser({
      username: form.username,
      password: form.password,
    });
    auth.applySession(response);
    await router.replace(response.user.role === "admin" ? "/admin/overview" : "/workbench");
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
          <div class="auth-shell__eyebrow">Create Account</div>
          <h1 class="auth-shell__title">快速创建研究账号</h1>
          <p class="auth-shell__subtitle">
            注册成功后会直接登录，并进入新的后台工作台，后续你可以导入交易文件、切换数据集并继续分析流程。
          </p>
        </div>

        <div class="auth-shell__cards">
          <div class="auth-shell__card">
            <div class="auth-shell__card-label">最少配置</div>
            <div class="auth-shell__card-value">用户名与密码即可开始使用</div>
          </div>
          <div class="auth-shell__card">
            <div class="auth-shell__card-label">自动登录</div>
            <div class="auth-shell__card-value">注册成功后直接进入后台，无需二次跳转</div>
          </div>
          <div class="auth-shell__card">
            <div class="auth-shell__card-label">数据隔离</div>
            <div class="auth-shell__card-value">账号继续绑定自己的导入批次与分析结果</div>
          </div>
        </div>
      </div>

      <div class="auth-shell__form">
        <div class="auth-shell__form-header">
          <h1>创建账号</h1>
          <p>当前版本保留轻量账户体系，注册成功后即可直接进入后台继续操作</p>
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
            <n-form-item label="确认密码">
              <n-input
                v-model:value="form.confirmPassword"
                type="password"
                show-password-on="click"
                placeholder="请再次输入密码" />
            </n-form-item>
          <n-button type="primary" :loading="loading" block attr-type="submit">注册并登录</n-button>
        </n-form>

        <p class="auth-footer">
          已有账号？<RouterLink to="/login">返回登录</RouterLink>
        </p>
      </div>
    </section>
  </div>
</template>


