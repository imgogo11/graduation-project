<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";

import {
  NButton,
  NForm,
  NFormItem,
  NInput,
  NModal,
  NPagination,
  NSwitch,
  NTable,
  NTag,
  useMessage,
} from "naive-ui";

import {
  deleteAdminUser,
  disableAdminUser,
  enableAdminUser,
  fetchAdminUsers,
  updateAdminUser,
} from "@/api/auth";
import type { AdminManagedUserRead } from "@/api/types";
import EmptyState from "@/components/EmptyState.vue";
import PanelCard from "@/components/PanelCard.vue";
import { useTablePager } from "@/composables/useTablePager";
import { formatDateTime, getErrorMessage } from "@/utils/format";
import { usePageErrorNotification } from "@/composables/usePageErrorNotification";


const message = useMessage();
const search = ref("");
const loading = ref(false);
const saving = ref(false);
const error = ref("");
usePageErrorNotification(error, "User Management Error");
const dialogVisible = ref(false);
const users = ref<AdminManagedUserRead[]>([]);
const editingUser = ref<AdminManagedUserRead | null>(null);

const form = reactive({
  username: "",
  password: "",
  is_active: true,
});

const activeCount = computed(() => users.value.filter((item) => item.is_active).length);
const usersPager = useTablePager(users, {
  initialPageSize: 10,
  pageSizes: [10, 20, 50],
  resetTriggers: [search],
});

function openDialog(user: AdminManagedUserRead) {
  editingUser.value = user;
  form.username = user.username;
  form.password = "";
  form.is_active = user.is_active;
  dialogVisible.value = true;
}

function closeDialog() {
  dialogVisible.value = false;
  editingUser.value = null;
  form.username = "";
  form.password = "";
  form.is_active = true;
}

async function loadUsers() {
  loading.value = true;
  error.value = "";

  try {
    users.value = await fetchAdminUsers(search.value.trim() || undefined);
  } catch (err) {
    error.value = getErrorMessage(err);
  } finally {
    loading.value = false;
  }
}

async function saveUser() {
  if (!editingUser.value) {
    return;
  }

  saving.value = true;
  error.value = "";

  try {
    await updateAdminUser(editingUser.value.id, {
      username: form.username.trim(),
      password: form.password.trim() || undefined,
      is_active: form.is_active,
    });
    message.success("用户信息已更新");
    closeDialog();
    await loadUsers();
  } catch (err) {
    error.value = getErrorMessage(err);
  } finally {
    saving.value = false;
  }
}

async function toggleUserActive(user: AdminManagedUserRead) {
  error.value = "";

  try {
    if (user.is_active) {
      await disableAdminUser(user.id);
      message.success(`已禁用用户 ${user.username}`);
    } else {
      await enableAdminUser(user.id);
      message.success(`已启用用户 ${user.username}`);
    }
    await loadUsers();
  } catch (err) {
    error.value = getErrorMessage(err);
  }
}

async function removeUser(user: AdminManagedUserRead) {
  if (!window.confirm(`确认删除用户 ${user.username} 吗？`)) {
    return;
  }

  error.value = "";

  try {
    await deleteAdminUser(user.id);
    message.success(`已删除用户 ${user.username}`);
    await loadUsers();
  } catch (err) {
    error.value = getErrorMessage(err);
  }
}

onMounted(() => {
  void loadUsers();
});
</script>

<template>
  <div class="page">
    <section class="page__header">
      <div>
        <div class="page__eyebrow">System / 用户管理</div>
        <h2 class="page__title">管理员维护普通用户状态与基础资料</h2>
        <p class="page__subtitle">
          本页支持按用户名筛选普通用户，并提供编辑、启停和删除等账号管理操作。
        </p>
      </div>
      <div class="page__actions">
        <span class="pill">总用户 {{ users.length }}</span>
        <span class="pill">启用数 {{ activeCount }}</span>
        <n-button type="primary" :loading="loading" @click="loadUsers">刷新用户列表</n-button>
      </div>
    </section>
<PanelCard title="用户列表" description="支持按用户名筛选普通用户，并对账号进行编辑、启停和删除">
      <div class="toolbar-row" style="margin-bottom: 16px;">
        <n-input v-model:value="search" placeholder="输入用户名关键字" clearable />
        <n-button :loading="loading" @click="loadUsers">搜索</n-button>
      </div>

      <div v-if="usersPager.total.value" class="data-table-wrap">
        <n-table class="data-table" striped size="small" :single-line="false">
          <thead>
            <tr>
              <th>用户</th>
              <th>状态</th>
              <th>业务数据</th>
              <th>创建时间</th>
              <th>最近登录</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="user in usersPager.pagedRows.value" :key="user.id">
              <td>{{ user.username }}</td>
              <td>
                <n-tag :type="user.is_active ? 'success' : 'info'" round size="small">
                  {{ user.is_active ? "启用" : "禁用" }}
                </n-tag>
              </td>
              <td>
                <n-tag :type="user.has_business_data ? 'warning' : 'success'" round size="small">
                  {{ user.has_business_data ? "已有数据" : "无业务数据" }}
                </n-tag>
              </td>
              <td>{{ formatDateTime(user.created_at) }}</td>
              <td>{{ formatDateTime(user.last_login_at) }}</td>
              <td>
                <div class="toolbar-row">
                  <n-button text type="primary" @click="openDialog(user)">编辑</n-button>
                  <n-button text :type="user.is_active ? 'warning' : 'success'" @click="toggleUserActive(user)">
                    {{ user.is_active ? "禁用" : "启用" }}
                  </n-button>
                  <n-button text type="error" :disabled="user.has_business_data" @click="removeUser(user)">
                    删除
                  </n-button>
                </div>
              </td>
            </tr>
          </tbody>
        </n-table>
        <div class="table-pagination">
          <n-pagination
            :page="usersPager.page.value"
            :page-size="usersPager.pageSize.value"
            :item-count="usersPager.total.value"
            :page-sizes="usersPager.pageSizes"
            show-size-picker
            @update:page="usersPager.setPage"
            @update:page-size="usersPager.setPageSize"
          />
        </div>
      </div>
      <EmptyState
        v-else
        title="当前没有普通用户"
        description="如果没有符合筛选条件的普通用户，这里会保持空状态"
      />
    </PanelCard>

    <n-modal v-model:show="dialogVisible">
      <div class="modal-card">
        <div class="modal-card__header">
          <h3 class="modal-card__title">编辑普通用户</h3>
        </div>
        <div class="modal-card__body">
          <n-form class="form-grid" label-placement="top">
            <n-form-item label="用户名" class="form-grid--wide">
              <n-input v-model:value="form.username" placeholder="输入新的用户名" />
            </n-form-item>
            <n-form-item label="重置密码" class="form-grid--wide">
              <n-input
                v-model:value="form.password"
                type="password"
                show-password-on="click"
                placeholder="留空表示不重置密码" />
            </n-form-item>
            <n-form-item label="账号状态" class="form-grid--wide">
              <n-switch v-model:value="form.is_active">
                <template #checked>启用</template>
                <template #unchecked>禁用</template>
              </n-switch>
            </n-form-item>
          </n-form>
        </div>
        <div class="modal-card__footer">
          <n-button @click="closeDialog">取消</n-button>
          <n-button type="primary" :loading="saving" @click="saveUser">保存修改</n-button>
        </div>
      </div>
    </n-modal>
  </div>
</template>


