<script setup lang="ts">
defineProps<{
  title: string;
  description?: string;
}>();
</script>

<template>
  <section class="panel-card">
    <header class="panel-card__header">
      <div>
        <h2 class="panel-card__title">
          <slot name="title">{{ title }}</slot>
        </h2>
        <p v-if="description" class="panel-card__description">{{ description }}</p>
      </div>
      <div v-if="$slots.actions" class="panel-card__actions">
        <slot name="actions" />
      </div>
    </header>
    <div class="panel-card__body">
      <slot />
    </div>
  </section>
</template>

<style scoped>
.panel-card {
  border: 1px solid var(--panel-border);
  border-radius: 24px;
  background: var(--panel-bg);
  box-shadow: var(--shadow-card);
  overflow: hidden;
}

.panel-card__header {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
  padding: 22px 22px 0;
  flex-wrap: wrap;
}

.panel-card__title {
  margin: 0;
  font-size: 20px;
}

.panel-card__description {
  margin: 8px 0 0;
  color: var(--text-secondary);
  font-size: 14px;
  line-height: 1.6;
}

.panel-card__actions {
  display: flex;
  gap: 8px;
  align-items: center;
}

.panel-card__body {
  padding: 22px;
}
</style>
