import React from 'react';
import {
  ActivityIndicator,
  Pressable,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import AppCard from './AppCard';
import { ui } from '../../design/tokens';
import type { PipelineStage } from '../../design/pipelineStage';
import { pipelineStageCopy } from '../../design/pipelineStage';
import {
  AnalysisProgressStatus,
  progressCopy,
} from '../../design/analysisStatus';

export type { AnalysisProgressStatus } from '../../design/analysisStatus';

type Props = {
  status: AnalysisProgressStatus;
  stage?: PipelineStage;
  title?: string;
  count?: number;
  variant?: 'compact' | 'full';
  onOpen?: () => void;
};

type StepState = 'done' | 'active' | 'waiting' | 'error';

type ProgressStep = {
  label: string;
  state: StepState;
};

/** UI v2: Never infer a percentage or an internal STT/OCR/Gemini stage. */
function getSteps(status: AnalysisProgressStatus, stage?: PipelineStage): ProgressStep[] {
  const submitting = status === 'SUBMITTING' || status === 'UPLOADING';
  const analyzing = status === 'ANALYZING';
  const pending = status === 'PENDING';
  const completed = status === 'COMPLETED';
  const failed = status === 'FAILED';

  return [
    { label: submitting ? '저장 중' : '저장됨', state: submitting ? 'active' : 'done' },
    {
      label: pending ? '분석 대기' : failed ? '분석 실패' : analyzing ? pipelineStageCopy(stage).label : '내용 분석',
      state: submitting ? 'waiting' : failed ? 'error' : completed ? 'done' : 'active',
    },
    { label: '완료', state: completed ? 'done' : 'waiting' },
  ];
}

function StatusIcon({ status }: { status: AnalysisProgressStatus }) {
  if (status === 'FAILED') {
    return <Ionicons name="alert-circle-outline" size={19} color={ui.color.error} />;
  }
  if (status === 'COMPLETED') {
    return <Ionicons name="checkmark-circle-outline" size={19} color={ui.color.success} />;
  }
  if (status === 'PENDING') {
    return <Ionicons name="time-outline" size={19} color={ui.color.brand} />;
  }
  return <ActivityIndicator size="small" color={ui.color.brand} />;
}

function StepIndicator({ state }: { state: StepState }) {
  if (state === 'done') {
    return <Ionicons name="checkmark-circle" size={16} color={ui.color.success} />;
  }
  if (state === 'error') {
    return <Ionicons name="alert-circle" size={16} color={ui.color.error} />;
  }
  if (state === 'active') {
    return <ActivityIndicator size="small" color={ui.color.brand} />;
  }
  return <Ionicons name="ellipse-outline" size={16} color={ui.color.border} />;
}

/**
 * Compact home status and a concise inline save-screen panel.
 * Content status is persisted; stage is reported by the real FastAPI steps.
 */
export default function AnalysisProgress({
  status,
  stage,
  count = 1,
  variant = 'full',
  onOpen,
}: Props) {
  const originalCopy = progressCopy(status);
  const heading = count > 1 && variant === 'compact'
    ? `${count}개 영상을 정리하고 있어요`
    : originalCopy.heading;
  const description = status === 'ANALYZING'
    ? pipelineStageCopy(stage).description
    : status === 'PENDING'
      ? '저장됐어요. 분석 순서를 기다리고 있어요.'
      : status === 'COMPLETED'
        ? '저장된 영상에서 내용을 확인할 수 있어요.'
        : originalCopy.description;
  const steps = getSteps(status, stage);

  const content = (
    <AppCard style={variant === 'compact' ? styles.compactCard : styles.fullCard}>
      <View style={styles.header} accessibilityLiveRegion="polite">
        <View style={styles.iconCircle}>
          <StatusIcon status={status} />
        </View>
        <View style={styles.headerText}>
          <Text style={styles.heading} numberOfLines={1}>{heading}</Text>
          <Text style={styles.description} numberOfLines={2}>
            {count > 1 && variant === 'compact'
              ? '여러 영상을 정리하고 있어요. 한 영상의 세부 단계는 저장 화면에서 볼 수 있어요.'
              : description}
          </Text>
        </View>
        {variant === 'compact' && onOpen ? (
          <Ionicons name="chevron-forward" size={18} color={ui.color.secondaryText} />
        ) : null}
      </View>

      {variant === 'full' && (
        <>
          <View style={styles.stepRow} accessibilityLabel={steps.map(s => s.label).join(', ')}>
            {steps.map((step, index) => (
              <React.Fragment key={index}>
                {index > 0 && <View style={styles.stepDivider} />}
                <View style={styles.stepItem}>
                  <StepIndicator state={step.state} />
                  <Text
                    style={[
                      styles.stepLabel,
                      step.state === 'waiting' && styles.mutedStepLabel,
                      step.state === 'error' && styles.errorStepLabel,
                    ]}
                    numberOfLines={1}
                  >
                    {step.label}
                  </Text>
                </View>
              </React.Fragment>
            ))}
          </View>
          <View style={styles.footer}>
            <Text style={styles.footnote} numberOfLines={2}>
              {status === 'FAILED'
                ? '저장물에서 상태를 확인해 주세요.'
                : status === 'COMPLETED'
                  ? '정리가 끝났어요.'
                  : '다른 화면으로 이동해도 정리는 계속돼요.'}
            </Text>
            {onOpen && status !== 'SUBMITTING' && status !== 'UPLOADING' && (
              <Pressable
                onPress={onOpen}
                accessibilityRole="button"
                accessibilityLabel="저장물 보기"
                hitSlop={8}
                style={styles.openButton}
              >
                <Text style={styles.openText}>저장물 보기</Text>
                <Ionicons name="arrow-forward" size={13} color={ui.color.brand} />
              </Pressable>
            )}
          </View>
        </>
      )}
    </AppCard>
  );

  if (variant === 'compact' && onOpen) {
    return (
      <Pressable
        onPress={onOpen}
        accessibilityRole="button"
        accessibilityLabel={`저장한 영상의 정리 상태 확인. ${heading}`}
      >
        {content}
      </Pressable>
    );
  }

  return content;
}

const styles = StyleSheet.create({
  compactCard: { marginTop: ui.spacing.md, marginBottom: ui.spacing.md },
  fullCard: { marginTop: ui.spacing.sm, marginBottom: ui.spacing.sm },
  header: { flexDirection: 'row', alignItems: 'center', gap: ui.spacing.sm },
  iconCircle: {
    width: 34,
    height: 34,
    borderRadius: 17,
    backgroundColor: ui.color.brandSoft,
    alignItems: 'center',
    justifyContent: 'center',
  },
  headerText: { flex: 1, gap: 3 },
  heading: { color: ui.color.foreground, fontSize: ui.type.body, fontWeight: '800' },
  description: { color: ui.color.secondaryText, fontSize: ui.type.caption, lineHeight: 17 },
  stepRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 5,
    marginTop: ui.spacing.md,
  },
  stepItem: { flexDirection: 'row', alignItems: 'center', gap: 5 },
  stepDivider: { height: 1, backgroundColor: ui.color.border, flex: 1, minWidth: 5 },
  stepLabel: { fontSize: 10, color: ui.color.foreground, fontWeight: '700' },
  mutedStepLabel: { color: ui.color.secondaryText, fontWeight: '400' },
  errorStepLabel: { color: ui.color.error },
  footer: {
    marginTop: ui.spacing.sm,
    paddingTop: ui.spacing.sm,
    borderTopWidth: 1,
    borderTopColor: ui.color.border,
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    gap: ui.spacing.sm,
  },
  footnote: { flex: 1, color: ui.color.secondaryText, fontSize: 10, lineHeight: 14 },
  openButton: { flexDirection: 'row', alignItems: 'center', gap: 4, minHeight: 28 },
  openText: { color: ui.color.brand, fontSize: 11, fontWeight: '800' },
});

// save:on TRUE_PROGRESS_V1
