<script setup lang="ts">
import { reactive, ref } from "vue";
import { RouterLink, useRoute, useRouter } from "vue-router";

import { loginUser } from "@/api/auth";
import { useAuthStore } from "@/stores/auth";
import { getErrorMessage } from "@/utils/format";


const route = useRoute();
const router = useRouter();
const auth = useAuthStore();
const loading = ref(false);
const error = ref("");
const form = reactive({
  username: "",
  password: "",
});

async function submit() {
  loading.value = true;
  error.value = "";
  try {
    const response = await loginUser(form);
    auth.applySession(response);
    const redirect = typeof route.query.redirect === "string" ? route.query.redirect : "/overview";
    router.replace(redirect);
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
      <div class="auth-card__eyebrow">Login</div>
      <h1 class="auth-card__title">登录系统</h1>
      <p class="auth-card__subtitle">
        登录后即可上传自己的交易数据文件，查看个人导入历史和分析结果。管理员登录后还能查看全站数据。
      </p>

      <el-alert
        v-if="error"
        title="登录失败"
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
          <el-input v-model="form.password" type="password" show-password autocomplete="current-password" />
        </el-form-item>
        <el-button type="primary" :loading="loading" @click="submit">登录</el-button>
      </el-form>

      <p class="auth-card__footer">
        还没有账号？
        <RouterLink to="/register">去注册</RouterLink>
      </p>
    </section>
  </div>
</template>
