import type { AiRunResponse } from '@/lib/api';

export type AiOperatingLayerRun = {
  analysisMode: string;
  layeredOutput: {
    topLevel: {
      verdict: string;
      confidence: number;
    };
  };
  moduleStatus: {
    chartContext: {
      status: string;
      reason: string;
    };
  };
  chartContext: Record<string, unknown>;
  pineContext: Record<string, unknown>;
};

export function mapAiRun(run: AiRunResponse): AiOperatingLayerRun {
  const layeredOutput =
    (run.layered_output as Record<string, unknown> | undefined) ?? {};
  const topLevel =
    (layeredOutput.top_level as Record<string, unknown> | undefined) ?? {};
  const moduleStatus =
    (run.module_status as Record<string, unknown> | undefined) ?? {};
  const chartContextStatus =
    (moduleStatus.chart_context as Record<string, unknown> | undefined) ?? {};

  return {
    analysisMode: run.analysis_mode ?? 'shadow_pretrade',
    layeredOutput: {
      topLevel: {
        verdict:
          typeof topLevel.verdict === 'string' ? topLevel.verdict : 'unclear',
        confidence:
          typeof topLevel.confidence === 'number' ? topLevel.confidence : 0,
      },
    },
    moduleStatus: {
      chartContext: {
        status:
          typeof chartContextStatus.status === 'string'
            ? chartContextStatus.status
            : 'unknown',
        reason:
          typeof chartContextStatus.reason === 'string'
            ? chartContextStatus.reason
            : '',
      },
    },
    chartContext: run.chart_context ?? {},
    pineContext: run.pine_context ?? {},
  };
}
