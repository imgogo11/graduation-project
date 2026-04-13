<script setup lang="ts">
import { reactive, ref } from "vue";
import { RouterLink, useRouter } from "vue-router";

import { registerUser } from "@/api/auth";
import { useAuthStore } from "@/stores/auth";
import { getErrorMessage } from "@/utils/format";


const router = useRouter();
const auth = useAuthStore();
const loading = ref(false);
const error = ref("");
const form = reactive({
  username: "",
  password: "",
  confirmPassword: "",
});

async function submit() {
  if (form.password !== form.confirmPassword) {
    error.value = "两次输入的密码不一致。";
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
    router.replace("/overview");
  } catch (err) {
    error.value = getErrorMessage(err);
  } finally {
    loading.value = false;
  }
}
</script>

<template>
  <div class="auth-page">
    <section class="auth-card">
      <div class="auth-card__eyebrow">Register</div>
      <h1 class="auth-card__title">创建账号</h1>
      <p class="auth-card__subtitle">
        v1 采用简单账号体系。注册成功后会直接登录，并进入你的个人交易数据总览。
      </p>

      <el-alert
        v-if="error"
        title="注册失败"
        type="error"
        :description="error"
        show-icon
        :closable="false"
      />

      <el-form class="auth-form" label-position="top" @submit.prevent="submit">
        <el-form-item label="用户名">
          <el-input v-model="form.username" autocomplete="username" />
        </el-form-item>
        <el-form-item label="密码">
          <el-input v-model="form.password" type="password" show-password autocomplete="new-password" />
        </el-form-item>
        <el-form-item label="确认密码">
          <el-input v-model="form.confirmPassword" type="password" show-password autocomplete="new-password" />
        </el-form-item>
        <el-button type="primary" :loading="loading" @click="submit">注册并登录</el-button>
      </el-form>

      <p class="auth-card__footer">
        已有账号？
        <RouterLink to="/login">返回登录</RouterLink>
      </p>
    </section>
  </div>
</template>
