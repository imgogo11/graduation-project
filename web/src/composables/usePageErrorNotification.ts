import type { Ref } from "vue";
import { watch } from "vue";

import { useNotification } from "naive-ui";

interface UsePageErrorNotificationOptions {
  duration?: number;
}

export function usePageErrorNotification(
  error: Ref<string>,
  title: string,
  options: UsePageErrorNotificationOptions = {}
) {
  const notification = useNotification();

  watch(
    error,
    (value, previousValue) => {
      if (!value || value === previousValue) {
        return;
      }

      notification.error({
        title,
        content: value,
        duration: options.duration ?? 6000,
        keepAliveOnHover: true,
      });
    },
    { flush: "post" }
  );
}
