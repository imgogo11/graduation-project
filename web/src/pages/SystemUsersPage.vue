<script setup lang="ts">
import { computed, h, onMounted, reactive, ref } from "vue";
import { CreateOutline, TrashOutline } from "@vicons/ionicons5";

import {
  NButton,
  NDataTable,
  NForm,
  NFormItem,
  NFormItemGi,
  NGrid,
  NIcon,
  NInput,
  NModal,
  NSwitch,
  NTag,
  useMessage,
  type DataTableColumns,
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
usePageErrorNotification(error, "用户管理加载失败");
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

const usersTableScrollX = 1120;
const usersTableMaxHeight = "min(48vh, 420px)";

const usersTableColumns: DataTableColumns<AdminManagedUserRead> = [
  {
    title: "用户",
    key: "username",
    width: 160,
  },
  {
    title: "状态",
    key: "is_active",
    width: 140,
    render(user) {
      return h(
        NTag,
        {
          type: user.is_active ? "success" : "info",
          round: true,
          size: "small",
        },
        { default: () => (user.is_active ? "启用" : "禁用") }
      );
    },
  },
  {
    title: "业务数据",
    key: "has_business_data",
    width: 170,
    render(user) {
      return h(
        NTag,
        {
          type: user.has_business_data ? "warning" : "success",
          round: true,
          size: "small",
        },
        { default: () => (user.has_business_data ? "已有数据" : "无业务数据") }
      );
    },
  },
  {
    title: "创建时间",
    key: "created_at",
    width: 250,
    render(user) {
      return formatDateTime(user.created_at);
    },
  },
  {
    title: "最近登录",
    key: "last_login_at",
    width: 220,
    render(user) {
      return formatDateTime(user.last_login_at);
    },
  },
  {
    title: "操作",
    key: "actions",
    width: 180,
    render(user) {
      return h("div", { class: "toolbar-row system-users-table__actions" }, [
        h(
          NButton,
          {
            text: true,
            type: "primary",
            onClick: () => openDialog(user),
          },
          {
            icon: () => h(NIcon, null, { default: () => h(CreateOutline) }),
            default: () => "编辑",
          }
        ),
        h(
          NButton,
          {
            text: true,
            type: user.is_active ? "warning" : "success",
            onClick: () => toggleUserActive(user),
          },
          { default: () => (user.is_active ? "禁用" : "启用") }
        ),
        h(
          NButton,
          {
            text: true,
            type: "error",
            disabled: user.has_business_data,
            onClick: () => removeUser(user),
          },
          {
            icon: () => h(NIcon, null, { default: () => h(TrashOutline) }),
            default: () => "删除",
          }
        ),
      ]);
    },
  },
];

const usersTablePagination = computed(() => ({
  page: usersPager.page.value,
  pageSize: usersPager.pageSize.value,
  itemCount: usersPager.total.value,
  pageSizes: usersPager.pageSizes,
  showSizePicker: true,
  onUpdatePage: usersPager.setPage,
  onUpdatePageSize: usersPager.setPageSize,
}));

function getUserRowKey(user: AdminManagedUserRead) {
  return user.id;
}

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

async function loadUsers(options: { notify?: boolean } = {}) {
  loading.value = true;
  error.value = "";

  try {
    users.value = await fetchAdminUsers({
      query: search.value.trim() || undefined,
    });
    if (options.notify) {
      message.success("搜索已完成");
    }
  } catch (err) {
    error.value = getErrorMessage(err);
    if (options.notify) {
      message.error(error.value);
    }
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
    message.error(error.value);
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
    message.error(error.value);
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
    message.error(error.value);
  }
}

onMounted(() => {
  void loadUsers();
});
</script>

<template>
  <div class="page">
    <PanelCard title="用户列表">
      <template #title>
        <span class="users-card__title">
          <span>用户列表</span>
          <span class="users-card__stats">
            <span class="pill users-card__pill">总用户 {{ users.length }}</span>
            <span class="pill users-card__pill">启用数 {{ activeCount }}</span>
          </span>
        </span>
      </template>
      <n-form label-placement="top" style="margin-bottom: 16px;">
        <n-grid :x-gap="16" :y-gap="0" cols="1 s:2 m:3 l:4 xl:5 2xl:6" responsive="screen">
          <n-form-item-gi label="用户">
            <n-input v-model:value="search" clearable placeholder="输入用户名关键字" @keyup.enter="loadUsers({ notify: true })" />
          </n-form-item-gi>
          <n-form-item-gi label=" ">
            <n-button
              type="warning"
              :loading="loading"
              @click="loadUsers({ notify: true })"
              style="width: 100%;"
            >
              搜索
            </n-button>
          </n-form-item-gi>
        </n-grid>
      </n-form>

      <n-data-table
        v-if="usersPager.total.value"
        class="system-users-table"
        :columns="usersTableColumns"
        :data="users"
        :pagination="usersTablePagination"
        :row-key="getUserRowKey"
        :max-height="usersTableMaxHeight"
        :scroll-x="usersTableScrollX"
        :scrollbar-props="{ trigger: 'none' }"
        :single-line="false"
        striped
        size="small"
      />
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
          <n-form label-placement="top">
            <n-grid :x-gap="16" :y-gap="0" cols="1">
              <n-form-item-gi label="用户名">
                <n-input v-model:value="form.username" placeholder="输入新的用户名" />
              </n-form-item-gi>
              <n-form-item-gi label="重置密码">
                <n-input
                  v-model:value="form.password"
                  type="password"
                  show-password-on="click"
                  placeholder="留空表示不重置密码" />
              </n-form-item-gi>
              <n-form-item-gi label="账号状态">
                <n-switch v-model:value="form.is_active">
                  <template #checked>启用</template>
                  <template #unchecked>禁用</template>
                </n-switch>
              </n-form-item-gi>
            </n-grid>
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

<style scoped>
.users-card__title {
  display: inline-flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.users-card__stats {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.users-card__pill {
  padding: 5px 10px;
  font-size: 12px;
}

.system-users-table {
  border-radius: 18px;
  overflow: visible;
}

:deep(.system-users-table .n-data-table-th) {
  color: var(--text-secondary);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  white-space: nowrap;
}

:deep(.system-users-table .n-data-table-td) {
  vertical-align: top;
}

:deep(.system-users-table .n-data-table__pagination) {
  padding: 0 12px 10px;
  border-top: 1px solid var(--panel-border);
  background: #fff;
}

.system-users-table__actions {
  flex-wrap: nowrap;
}
</style>
