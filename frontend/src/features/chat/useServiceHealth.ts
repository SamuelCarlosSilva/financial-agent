// Disponibilidade do serviço ao abrir a interface (FR-021).
import { useCallback, useEffect, useState } from 'react';

import { ApiRequestError, getHealth } from '../../api/client';
import type { ApiFailure } from '../../api/types';

/**
 * `degraded` (503) e qualquer falha na checagem, rede inclusive, viram "serviço indisponível":
 * para quem usa a interface a consequência é a mesma.
 */
function unavailable(error?: unknown): ApiFailure {
  const request_id = error instanceof ApiRequestError ? error.error.request_id : undefined;
  return {
    status: 503,
    error: { code: 'upstream_unavailable', message: '', ...(request_id ? { request_id } : {}) },
  };
}

/** `null` quando o serviço está ok. */
async function check(): Promise<ApiFailure | null> {
  try {
    const health = await getHealth();
    return health.status === 'ok' ? null : unavailable();
  } catch (error) {
    return unavailable(error);
  }
}

export function useServiceHealth() {
  const [down, setDown] = useState<ApiFailure | null>(null);

  useEffect(() => {
    let alive = true;
    void check().then((result) => {
      if (alive) setDown(result);
    });
    return () => {
      alive = false;
    };
  }, []);

  const recheck = useCallback(async () => setDown(await check()), []);

  return { down, recheck };
}
