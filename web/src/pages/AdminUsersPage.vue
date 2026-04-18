<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";

import {
  NButton,
  NForm,
  NFormItem,
  NInput,
  NModal,
  NPagination,
  NSelect,
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
const activeFilter = ref<"all" | "active" | "inactive">("all");
const loading = ref(false);
const saving = ref(false);
const error = ref("");
usePageErrorNotification(error, "User Management Error");
const dialogVisible = ref(false);
const users = ref<AdminManagedUserRead[]>([]);
const editingUser = ref<AdminManagedUserRead | null>(null);
const rowLoading = reactive<Record<number, boolean>>({});

const form = reactive({
  username: "",
  password: "",
  is_active: true,
});

const activeCount = computed(() => users.value.filter((item) => item.is_active).length);
const adminCount = computed(() => users.value.filter((item) => item.role === "admin").length);
const filteredUsers = computed(() =>
  users.value.filter((item) => {
    if (activeFilter.value === "active") {
      return item.is_active;
    }
    if (activeFilter.value === "inactive") {
      return !item.is_active;
    }
    return true;
  })
);

const usersPager = useTablePager(filteredUsers, {
  initialPageSize: 10,
  pageSizes: [10, 20, 50],
  resetTriggers: [search, activeFilter],
});

const activeFilterOptions = [
  { label: "全部状态", value: "all" },
  { label: "仅启用", value: "active" },
  { label: "仅禁用", value: "inactive" },
];

function isReadonlyUser(user: AdminManagedUserRead) {
  return user.role !== "user";
}

function openDialog(user: AdminManagedUserRead) {
  if (isReadonlyUser(user)) {
    message.warning("管理员账号仅支持查看，不支持在此页编辑");
    return;
  }
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
  if (isReadonlyUser(editingUser.value)) {
    message.warning("管理员账号仅支持查看，不支持在此页修改");
    closeDialog();
    return;
  }

  saving.value = true;
  error.value = "";

  try {
    const updated = await updateAdminUser(editingUser.value.id, {
      username: form.username.trim(),
      password: form.password.trim() || undefined,
      is_active: form.is_active,
    });
    const targetIndex = users.value.findIndex((item) => item.id === updated.id);
    if (targetIndex >= 0) {
      users.value.splice(targetIndex, 1, updated);
    }
    message.success("用户信息已更新");
    closeDialog();
  } catch (err) {
    error.value = getErrorMessage(err);
  } finally {
    saving.value = false;
  }
}

async function toggleUserActive(user: AdminManagedUserRead, nextValue: boolean) {
  if (isReadonlyUser(user)) {
    message.warning("管理员账号不支持在此页启停");
    return;
  }
  if (user.is_active === nextValue) {
    return;
  }

  rowLoading[user.id] = true;
  error.value = "";
  try {
    const updated = nextValue ? await enableAdminUser(user.id) : await disableAdminUser(user.id);
    const targetIndex = users.value.findIndex((item) => item.id === updated.id);
    if (targetIndex >= 0) {
      users.value.splice(targetIndex, 1, updated);
    }
    message.success(nextValue ? `已启用用户 ${updated.username}` : `已禁用用户 ${updated.username}`);
  } catch (err) {
    error.value = getErrorMessage(err);
  } finally {
    rowLoading[user.id] = false;
  }
}

async function removeUser(user: AdminManagedUserRead) {
  if (isReadonlyUser(user)) {
    message.warning("管理员账号不支持在此页删除");
    return;
  }
  if (!window.confirm(`确认删除用户 ${user.username} 吗？`)) {
    return;
  }

  rowLoading[user.id] = true;
  error.value = "";
  try {
    await deleteAdminUser(user.id);
    users.value = users.value.filter((item) => item.id !== user.id);
    message.success(`已删除用户 ${user.username}`);
  } catch (err) {
    error.value = getErrorMessage(err);
  } finally {
    rowLoading[user.id] = false;
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
        <div class="page__eyebrow">Admin / Users</div>
        <h2 class="page__title">管理员用户管理</h2>
        <p class="page__subtitle">
          页面以后台运维交互为主：支持用户名筛选、启停切换、账号编辑与删除。管理员账号会显示在列表中，但仅支持查看，不在此页执行修改。
        </p>
      </div>
      <div class="page__actions">
        <span class="pill">总用户 {{ users.length }}</span>
        <span class="pill">启用数 {{ activeCount }}</span>
        <span class="pill">admin {{ adminCount }}</span>
        <n-button type="primary" :loading="loading" @click="loadUsers">刷新</n-button>
      </div>
    </section>
<PanelCard title="用户列表" description="筛选、启停、编辑、删除集中在一张后台表格中">
      <n-form inline class="toolbar-row" style="margin-bottom: 16px;">
        <n-form-item label="用户">
          <n-input v-model:value="search" clearable placeholder="输入用户名关键字" @keyup.enter="loadUsers" />
        </n-form-item>
        <n-form-item label="状态">
          <n-select v-model:value="activeFilter" :options="activeFilterOptions" style="min-width: 150px;" />
        </n-form-item>
        <n-button :loading="loading" @click="loadUsers">搜索</n-button>
      </n-form>

      <div v-if="usersPager.total.value" class="data-table-wrap">
        <n-table class="data-table" striped size="small" :single-line="false">
          <thead>
            <tr>
              <th>用户</th>
              <th>角色</th>
              <th>是否启用</th>
              <th>业务数据</th>
              <th>创建时间</th>
              <th>最后登录</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="user in usersPager.pagedRows.value" :key="user.id">
              <td>{{ user.username }}</td>
              <td>
                <n-tag :type="user.role === 'admin' ? 'warning' : 'info'" round size="small">{{ user.role }}</n-tag>
              </td>
              <td>
                <n-switch
                  :value="user.is_active"
                  :disabled="isReadonlyUser(user)"
                  :loading="Boolean(rowLoading[user.id])"
                  @update:value="(value) => toggleUserActive(user, value)"
                >
                  <template #checked>启用</template>
                  <template #unchecked>禁用</template>
                </n-switch>
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
                  <n-button text type="primary" :disabled="isReadonlyUser(user)" @click="openDialog(user)">编辑</n-button>
                  <n-button
                    text
                    type="error"
                    :disabled="user.has_business_data || isReadonlyUser(user)"
                    :loading="Boolean(rowLoading[user.id])"
                    @click="removeUser(user)"
                  >
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
        title="没有匹配用户"
        description="当前筛选条件下没有可展示的用户" />
    </PanelCard>

    <n-modal v-model:show="dialogVisible">
      <div class="modal-card">
        <div class="modal-card__header">
          <h3 class="modal-card__title">编辑用户</h3>
        </div>
        <div class="modal-card__body">
          <n-form class="form-grid" label-placement="top">
            <n-form-item label="用户" class="form-grid--wide">
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
          <n-button type="primary" :loading="saving" @click="saveUser">保存</n-button>
        </div>
      </div>
    </n-modal>
  </div>
</template>

