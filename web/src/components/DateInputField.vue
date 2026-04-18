<script setup lang="ts">
withDefaults(
  defineProps<{
    modelValue?: string;
    placeholder?: string;
    disabled?: boolean;
    clearable?: boolean;
  }>(),
  {
    modelValue: "",
    placeholder: "",
    disabled: false,
    clearable: false,
  }
);

const emit = defineEmits<{
  (event: "update:modelValue", value: string): void;
}>();

function onInput(event: Event) {
  emit("update:modelValue", (event.target as HTMLInputElement).value);
}

function clearValue() {
  emit("update:modelValue", "");
}
</script>

<template>
  <div class="date-input-field">
    <input
      class="date-input-field__control"
      type="date"
      :value="modelValue || ''"
      :placeholder="placeholder"
      :disabled="disabled"
      @input="onInput"
    />
    <button v-if="clearable && modelValue" type="button" class="date-input-field__clear" @click="clearValue">×</button>
  </div>
</template>

<style scoped>
.date-input-field {
  position: relative;
  display: flex;
  align-items: center;
}

.date-input-field__control {
  width: 100%;
  min-height: 38px;
  padding: 0 34px 0 12px;
  border: 1px solid #d9dde8;
  border-radius: 12px;
  color: #2f3a4d;
  background: #ffffff;
  transition: border-color 0.2s ease, box-shadow 0.2s ease;
}

.date-input-field__control:focus {
  outline: none;
  border-color: #f05a28;
  box-shadow: 0 0 0 2px rgba(240, 90, 40, 0.16);
}

.date-input-field__control:disabled {
  cursor: not-allowed;
  color: #9aa8ba;
  background: #f5f7fb;
}

.date-input-field__clear {
  position: absolute;
  right: 10px;
  width: 20px;
  height: 20px;
  border: 0;
  border-radius: 50%;
  color: #7c8a9c;
  background: transparent;
  cursor: pointer;
  line-height: 1;
}

.date-input-field__clear:hover {
  color: #2f3a4d;
  background: rgba(47, 58, 77, 0.08);
}
</style>
