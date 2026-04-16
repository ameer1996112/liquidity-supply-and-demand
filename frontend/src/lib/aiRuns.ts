import type { AiRunResponse, SetupEvidenceResponse } from '@/lib/api';

type SetupEvidence = {
  status: string;
  focusZone: Record<string, unknown> | null;
  focusImage: {
    path?: string | null;
    url?: string | null;
    region?: string | null;
  } | null;
  reason: string;
};

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
  chartContext: {
    status: string;
    reason: string;
    structured: {
      setupEvidence: SetupEvidence;
      zones: Array<Record<string, unknown>>;
      pineLabels: Array<Record<string, unknown>>;
    };
  };
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
  const chartContext =
    (run.chart_context as Record<string, unknown> | undefined) ?? {};
  const chartContextStructured =
    (chartContext.structured as Record<string, unknown> | undefined) ?? {};
  const setupEvidence =
    (chartContextStructured.setup_evidence as SetupEvidenceResponse | undefined) ??
    {};

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
    chartContext: {
      status:
        typeof chartContext.status === 'string' ? chartContext.status : 'unknown',
      reason:
        typeof chartContext.reason === 'string' ? chartContext.reason : '',
      structured: {
        setupEvidence: {
          status:
            typeof setupEvidence.status === 'string'
              ? setupEvidence.status
              : 'degraded',
          focusZone:
            setupEvidence.focus_zone &&
            typeof setupEvidence.focus_zone === 'object'
              ? setupEvidence.focus_zone
              : null,
          focusImage:
            setupEvidence.focus_image &&
            typeof setupEvidence.focus_image === 'object'
              ? setupEvidence.focus_image
              : null,
          reason:
            typeof setupEvidence.reason === 'string'
              ? setupEvidence.reason
              : 'Setup evidence unavailable',
        },
        zones: Array.isArray(chartContextStructured.zones)
          ? (chartContextStructured.zones as Array<Record<string, unknown>>)
          : [],
        pineLabels: Array.isArray(chartContextStructured.pine_labels)
          ? (chartContextStructured.pine_labels as Array<Record<string, unknown>>)
          : [],
      },
    },
    pineContext: run.pine_context ?? {},
  };
}
